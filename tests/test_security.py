import ipaddress
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import pytest
from django.test import override_settings

from widget_hub import security
from widget_hub.security import SafeFetchError, is_public_address, safe_fetch

PUBLIC_IP = "93.184.216.34"
OTHER_PUBLIC_IP = "93.184.216.35"
DNS = {
    "public.test": [PUBLIC_IP],
    "other.test": [OTHER_PUBLIC_IP],
    "internal.test": ["10.0.0.5"],
    "mixed.test": [PUBLIC_IP, "127.0.0.1"],
    "metadata.test": ["169.254.169.254"],
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, status, body=b"", headers=()):
        self.send_response(status)
        for name, value in headers:
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/json":
            body = json.dumps({"host": self.headers["Host"], "path": self.path}).encode()
            self._send(200, body, [("Content-Type", "application/json; charset=utf-8")])
        elif path == "/echo-auth":
            self._send(200, (self.headers.get("Authorization") or "none").encode())
        elif path == "/big":
            self.send_response(200)
            self.end_headers()  # no Content-Length: forces streaming
            self.wfile.write(b"x" * 5000)
        elif path == "/big-declared":
            self._send(200, b"x" * 5000)
        elif path == "/slow":
            time.sleep(1)
            self._send(200, b"late")
        elif path == "/to-json":
            self._send(302, headers=[("Location", "/json")])
        elif path == "/to-internal":
            self._send(302, headers=[("Location", "http://internal.test/json")])
        elif path == "/to-other":
            port = self.server.server_address[1]
            self._send(302, headers=[("Location", f"http://other.test:{port}/echo-auth")])
        elif path == "/echo-headers":
            names = ("Authorization", "X-Api-Key", "Cookie")
            self._send(200, json.dumps({n: self.headers.get(n) for n in names}).encode())
        elif path == "/to-other-headers":
            port = self.server.server_address[1]
            self._send(302, headers=[("Location", f"http://other.test:{port}/echo-headers")])
        elif path == "/drip-body":
            self.send_response(200)
            self.end_headers()
            for _ in range(40):  # one byte every 50 ms: each recv() is well under the timeout
                self.wfile.write(b"x")
                self.wfile.flush()
                time.sleep(0.05)
        elif path == "/drip-headers":
            self.wfile.write(b"HTTP/1.1 200 OK\r\n")
            for _ in range(40):
                self.wfile.write(b"X-Slow: 1\r\n")
                self.wfile.flush()
                time.sleep(0.05)
            self.wfile.write(b"\r\n")
        elif path == "/loop":
            self._send(302, headers=[("Location", "/loop")])
        elif path == "/not-json":
            self._send(200, b"<html>")
        else:
            self._send(404, b"missing")


@pytest.fixture
def server(monkeypatch):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, args=(0.01,), daemon=True)
    thread.start()
    connections = []
    real_create_connection = socket.create_connection

    real_getaddrinfo = socket.getaddrinfo

    def fake_getaddrinfo(host, port, *args, **kwargs):
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:  # IP literals resolve to themselves, as with real DNS
            return real_getaddrinfo(host, port, *args, **kwargs)
        if host not in DNS:
            raise socket.gaierror("unknown host")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port)) for ip in DNS[host]]

    def fake_create_connection(address, timeout=None, *args, **kwargs):
        connections.append(address)
        ip, port = address
        assert ip in (PUBLIC_IP, OTHER_PUBLIC_IP), f"connected to unvalidated address {ip}"
        return real_create_connection(("127.0.0.1", port), timeout)

    monkeypatch.setattr(security.socket, "getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(security.socket, "create_connection", fake_create_connection)
    yield f"http://public.test:{httpd.server_address[1]}", connections
    httpd.shutdown()


@pytest.mark.parametrize(
    ("address", "public"),
    [
        ("8.8.8.8", True),
        ("2606:4700:4700::1111", True),
        ("127.0.0.1", False),
        ("10.1.2.3", False),
        ("172.16.0.1", False),
        ("192.168.1.1", False),
        ("169.254.169.254", False),
        ("100.64.0.1", False),
        ("0.0.0.0", False),
        ("224.0.0.1", False),
        ("::1", False),
        ("fe80::1%eth0", False),
        ("fc00::1", False),
        ("::ffff:127.0.0.1", False),
        ("::ffff:8.8.8.8", True),
        ("64:ff9b::7f00:1", False),  # NAT64 for 127.0.0.1
        ("64:ff9b::a9fe:a9fe", False),  # NAT64 for 169.254.169.254
        ("2002:7f00:1::", False),  # 6to4 for 127.0.0.1
        ("2002:a00:1::", False),  # 6to4 for 10.0.0.1
        ("2001:0:4136:e378:8000:63bf:3fff:fdd2", False),  # Teredo
    ],
)
def test_is_public_address(address, public):
    assert is_public_address(address) is public


def test_fetch_json_and_headers(server):
    base, connections = server
    response = safe_fetch(f"{base}/json", params={"q": "a b"})
    assert response.status == 200
    assert response.json() == {"host": base.removeprefix("http://"), "path": "/json?q=a+b"}
    assert response.headers["content-type"].startswith("application/json")
    assert connections == [(PUBLIC_IP, int(base.rsplit(":", 1)[1]))]


def test_text_and_non_json(server):
    base, _ = server
    response = safe_fetch(f"{base}/not-json")
    assert response.text == "<html>"
    with pytest.raises(SafeFetchError, match="valid JSON"):
        response.json()


def test_non_2xx_is_returned_not_raised(server):
    base, _ = server
    assert safe_fetch(f"{base}/nope").status == 404


@pytest.mark.parametrize(
    ("url", "message", "status"),
    [
        ("ftp://public.test/", "Only http and https", 400),
        ("file:///etc/passwd", "Only http and https", 400),
        ("http:///path", "no host name", 400),
        ("http://user:pw@public.test/", "credentials", 400),
        ("http://public.test:99999/", "Invalid URL", 400),
        ("http://internal.test/", "private or reserved", 400),
        ("http://metadata.test/latest/meta-data", "private or reserved", 400),
        ("http://mixed.test/", "private or reserved", 400),
        ("http://127.0.0.1/", "private or reserved", 400),
        ("http://[::1]/", "private or reserved", 400),
        ("http://unknown.test/", "Could not resolve", 502),
    ],
)
def test_refused_urls(server, url, message, status):
    _, connections = server
    with pytest.raises(SafeFetchError, match=message) as info:
        safe_fetch(url)
    assert info.value.status == status
    assert connections == []


def test_redirects_are_followed_and_revalidated(server):
    base, connections = server
    assert safe_fetch(f"{base}/to-json").json()["path"] == "/json"
    with pytest.raises(SafeFetchError, match="private or reserved"):
        safe_fetch(f"{base}/to-internal")
    assert all(ip == PUBLIC_IP for ip, _ in connections)


def test_redirect_limit(server):
    base, _ = server
    with pytest.raises(SafeFetchError, match="Too many redirects"):
        safe_fetch(f"{base}/loop", max_redirects=2)


def test_authorization_is_dropped_on_cross_host_redirect(server):
    base, _ = server
    same = safe_fetch(f"{base}/echo-auth", headers={"Authorization": "Bearer t"})
    assert same.text == "Bearer t"
    other = safe_fetch(f"{base}/to-other", headers={"Authorization": "Bearer t"})
    assert other.text == "none"


def test_caller_headers_are_dropped_on_cross_origin_redirect(server):
    """Regression: API keys and cookies must not follow a redirect to another origin."""
    base, _ = server
    secrets = {"Authorization": "Bearer t", "X-Api-Key": "k", "Cookie": "s=1"}
    assert safe_fetch(f"{base}/echo-headers", headers=secrets).json() == {
        "Authorization": "Bearer t",
        "X-Api-Key": "k",
        "Cookie": "s=1",
    }
    assert safe_fetch(f"{base}/to-other-headers", headers=secrets).json() == {
        "Authorization": None,
        "X-Api-Key": None,
        "Cookie": None,
    }


@pytest.mark.parametrize(
    ("first", "second", "same"),
    [
        ("https://a.test/x", "https://A.test:443/y", True),
        ("https://a.test/", "http://a.test/", False),  # scheme downgrade
        ("https://a.test/", "https://a.test:8443/", False),
        ("https://a.test/", "https://b.test/", False),
    ],
)
def test_origin(first, second, same):
    assert (security.origin(urlsplit(first)) == security.origin(urlsplit(second))) is same


@pytest.mark.parametrize("path", ["/drip-body", "/drip-headers"])
def test_deadline_is_absolute_against_slow_drip(server, path):
    """Regression: a server trickling bytes must not keep the call alive past the deadline."""
    base, _ = server
    started = time.monotonic()
    with pytest.raises(SafeFetchError, match="did not answer in time") as info:
        safe_fetch(f"{base}{path}", timeout=0.3)
    assert info.value.status == 504
    assert time.monotonic() - started < 1.0


@pytest.mark.parametrize("path", ["/big", "/big-declared"])
def test_size_limit(server, path):
    base, _ = server
    with pytest.raises(SafeFetchError, match="too large"):
        safe_fetch(f"{base}{path}", max_bytes=1000)
    assert len(safe_fetch(f"{base}{path}", max_bytes=5000).content) == 5000


def test_timeout(server):
    base, _ = server
    started = time.monotonic()
    with pytest.raises(SafeFetchError, match="did not answer in time") as info:
        safe_fetch(f"{base}/slow", timeout=0.2)
    assert info.value.status == 504
    assert time.monotonic() - started < 0.9


@override_settings(WIDGET_HUB={"SAFE_FETCH_MAX_BYTES": 10})
def test_settings_provide_defaults(server):
    base, _ = server
    with pytest.raises(SafeFetchError, match="too large"):
        safe_fetch(f"{base}/big")


def test_connection_refused_is_a_generic_error(monkeypatch):
    monkeypatch.setattr(
        security.socket,
        "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (PUBLIC_IP, 80))],
    )

    def refuse(*args, **kwargs):
        raise ConnectionRefusedError("refused at 10.0.0.1:80 internal detail")

    monkeypatch.setattr(security.socket, "create_connection", refuse)
    with pytest.raises(SafeFetchError) as info:
        safe_fetch("http://public.test/")
    assert str(info.value) == "Could not reach public.test."
    assert info.value.status == 502


def test_https_connects_to_the_validated_address_with_sni(monkeypatch):
    calls = {}

    class FakeContext:
        def wrap_socket(self, sock, server_hostname):
            calls["sni"] = server_hostname
            raise OSError("stop here")

    def fake_create_connection(address, timeout=None):
        calls["address"] = address
        return object()

    monkeypatch.setattr(security.socket, "create_connection", fake_create_connection)
    conn = security._PinnedHTTPSConnection("api.example.com", 443, PUBLIC_IP, 1.0, FakeContext())
    with pytest.raises(OSError, match="stop here"):
        conn.connect()
    assert calls == {"address": (PUBLIC_IP, 443), "sni": "api.example.com"}
