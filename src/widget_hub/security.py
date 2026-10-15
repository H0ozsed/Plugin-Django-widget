"""``safe_fetch()``: HTTP GET for user-supplied URLs, protected against SSRF.

Every hop (the URL and each redirect) is checked before connecting:

* scheme must be ``http`` or ``https``, the URL must not embed credentials;
* the host name is resolved once and **every** address must be public (no private, loopback,
  link-local, multicast, reserved or unspecified address, IPv4-mapped IPv6 included);
* the connection is made to the address that was checked, with the original host name in the
  ``Host`` header and in TLS SNI/certificate validation, so a DNS answer cannot change between
  the check and the connection (DNS rebinding);
* each socket operation times out, the whole call has a deadline, and the body is cut off past a
  size limit.

Failures raise :class:`SafeFetchError`, a :class:`~widget_hub.exceptions.WidgetError` whose
message is safe to show, so a widget can let it propagate.
"""

from __future__ import annotations

import contextlib
import http.client
import ipaddress
import json
import socket
import ssl
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode, urljoin, urlsplit

from . import __version__, conf
from .exceptions import WidgetError

REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


class SafeFetchError(WidgetError):
    """A URL was refused or could not be fetched safely; the message is user-facing."""


@dataclass(frozen=True)
class SafeResponse:
    """Response returned by :func:`safe_fetch`.

    :ivar status: HTTP status code of the final response.
    :ivar headers: response headers (lower-cased names).
    :ivar content: body bytes (at most ``max_bytes``).
    :ivar url: final URL after redirects.
    """

    status: int
    headers: dict[str, str] = field(repr=False)
    content: bytes = field(repr=False)
    url: str

    @property
    def text(self) -> str:
        """Body decoded with the charset announced in ``Content-Type`` (UTF-8 by default)."""
        charset = "utf-8"
        for part in self.headers.get("content-type", "").split(";")[1:]:
            name, _, value = part.strip().partition("=")
            if name.lower() == "charset" and value:
                charset = value.strip('"')
        try:
            return self.content.decode(charset, errors="replace")
        except LookupError:
            return self.content.decode("utf-8", errors="replace")

    def json(self) -> Any:
        """Body parsed as JSON; raises :class:`SafeFetchError` if it is not valid JSON."""
        try:
            return json.loads(self.content)
        except ValueError:
            raise SafeFetchError("The server did not return valid JSON.", 502) from None


_NAT64 = ipaddress.ip_network("64:ff9b::/96")


def _embedded_ipv4(ip: ipaddress.IPv6Address) -> list[ipaddress.IPv4Address]:
    """IPv4 addresses a 6to4, Teredo or NAT64 address carries, which a gateway may route to."""
    embedded: list[ipaddress.IPv4Address] = []
    if ip.sixtofour is not None:
        embedded.append(ip.sixtofour)
    if ip.teredo is not None:
        embedded.extend(ip.teredo)
    if ip in _NAT64:
        embedded.append(ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF))
    return embedded


def _is_public_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    # is_global alone differs between Python versions: also reject every special range explicitly.
    special = (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )
    return ip.is_global and not special


def is_public_address(address: str) -> bool:
    """True if ``address`` is a globally routable unicast IP address and, for IPv6, every IPv4
    address embedded in it (IPv4-mapped, 6to4, Teredo, NAT64) is public as well."""
    ip = ipaddress.ip_address(address.split("%", 1)[0])
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return _is_public_ip(ip.ipv4_mapped)
        if not all(_is_public_ip(v4) for v4 in _embedded_ipv4(ip)):
            return False
    return _is_public_ip(ip)


def resolve_public_address(host: str, port: int) -> str:
    """Resolve ``host`` and return one address, refusing the host if any address is not public."""
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError):
        raise SafeFetchError(f"Could not resolve {host}.", 502) from None
    addresses = [info[4][0] for info in infos]
    if not addresses or not all(is_public_address(a) for a in addresses):
        raise SafeFetchError("This URL points to a private or reserved address.", 400)
    return addresses[0]


def safe_fetch(
    url: str,
    *,
    params: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: float | None = None,
    max_bytes: int | None = None,
    max_redirects: int | None = None,
) -> SafeResponse:
    """GET ``url`` with SSRF protection, a timeout and a size limit.

    :param params: query-string parameters appended to ``url``.
    :param headers: extra request headers (API keys...). They are sent to the original origin
        only: a redirect to another scheme, host or port drops all of them.
    :param timeout: overall deadline in seconds (default ``SAFE_FETCH_TIMEOUT``).
    :param max_bytes: largest accepted body (default ``SAFE_FETCH_MAX_BYTES``).
    :param max_redirects: redirects followed (default ``SAFE_FETCH_MAX_REDIRECTS``).
    :raises SafeFetchError: refused URL, network error, timeout, too many redirects, body too big.
    """
    timeout = float(conf.get("SAFE_FETCH_TIMEOUT") if timeout is None else timeout)
    max_bytes = conf.get("SAFE_FETCH_MAX_BYTES") if max_bytes is None else max_bytes
    max_redirects = conf.get("SAFE_FETCH_MAX_REDIRECTS") if max_redirects is None else max_redirects
    deadline = time.monotonic() + timeout
    if params:
        url = f"{url}{'&' if urlsplit(url).query else '?'}{urlencode(params, doseq=True)}"
    default_headers = {"User-Agent": f"django-widget-hub/{__version__}", "Accept": "*/*"}
    request_headers = {**default_headers, **(headers or {})}
    first_origin = None
    for _ in range(max_redirects + 1):
        parts = _check_url(url)
        if first_origin is None:
            first_origin = origin(parts)
        elif origin(parts) != first_origin:
            request_headers = dict(default_headers)  # never forward caller headers elsewhere
        status, response_headers, body = _request_once(parts, request_headers, deadline, max_bytes)
        location = response_headers.get("location")
        if status in REDIRECT_STATUSES and location:
            url = urljoin(url, location)
            continue
        return SafeResponse(status, response_headers, body, url)
    raise SafeFetchError("Too many redirects.", 502)


def origin(parts: Any) -> tuple[str, str, int]:
    """The ``(scheme, host, port)`` origin of a split URL, with the default port filled in."""
    scheme = parts.scheme.lower()
    return scheme, (parts.hostname or "").lower(), parts.port or (443 if scheme == "https" else 80)


def _check_url(url: str) -> Any:
    try:
        parts = urlsplit(url)
        parts.port  # noqa: B018 - raises ValueError on an invalid port
    except ValueError:
        raise SafeFetchError("Invalid URL.", 400) from None
    if parts.scheme not in ("http", "https"):
        raise SafeFetchError("Only http and https URLs are allowed.", 400)
    if not parts.hostname:
        raise SafeFetchError("The URL has no host name.", 400)
    if parts.username or parts.password:
        raise SafeFetchError("URLs containing credentials are not allowed.", 400)
    return parts


def _request_once(
    parts: Any, headers: Mapping[str, str], deadline: float, max_bytes: int
) -> tuple[int, dict[str, str], bytes]:
    host = parts.hostname
    port = parts.port or (443 if parts.scheme == "https" else 80)
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise SafeFetchError(f"{host} did not answer in time.", 504)
    address = resolve_public_address(host, port)
    if parts.scheme == "https":
        conn: http.client.HTTPConnection = _PinnedHTTPSConnection(
            host, port, address, remaining, ssl.create_default_context()
        )
    else:
        conn = _PinnedHTTPConnection(host, port, address, remaining)
    path = parts.path or "/"
    if parts.query:
        path = f"{path}?{parts.query}"
    too_late = SafeFetchError(f"{host} did not answer in time.", 504)
    # Socket timeouts apply to each recv(): a server sending one byte at a time would never
    # trigger them. The watchdog shuts the socket down at the absolute deadline instead.
    expired = threading.Event()
    sockets: list[socket.socket] = []
    watchdog = threading.Timer(remaining, _expire, args=(sockets, expired))
    watchdog.daemon = True
    watchdog.start()
    try:
        conn.connect()
        # http.client drops conn.sock after getresponse() when the server will close the
        # connection, while the body is still read from it: keep our own reference.
        sockets.append(conn.sock)
        conn.request("GET", path, headers=dict(headers))
        response = conn.getresponse()
        body = _read_limited(response, max_bytes)
        if expired.is_set():  # a shut-down socket reads as EOF: never return a truncated body
            raise too_late
        response_headers = {k.lower(): v for k, v in response.getheaders()}
        return response.status, response_headers, body
    except SafeFetchError:
        raise
    except TimeoutError:
        raise too_late from None
    except (OSError, http.client.HTTPException) as exc:
        if expired.is_set():
            raise too_late from None
        if isinstance(exc, ssl.SSLError):
            raise SafeFetchError(f"TLS error while connecting to {host}.", 502) from None
        raise SafeFetchError(f"Could not reach {host}.", 502) from None
    finally:
        watchdog.cancel()
        conn.close()


def _expire(sockets: list[socket.socket], expired: threading.Event) -> None:
    expired.set()
    for sock in sockets:
        with contextlib.suppress(OSError):
            sock.shutdown(socket.SHUT_RDWR)


def _read_limited(response: http.client.HTTPResponse, max_bytes: int) -> bytes:
    length = response.getheader("content-length")
    if length and length.isdigit() and int(length) > max_bytes:
        raise SafeFetchError("The response is too large.", 502)
    chunks: list[bytes] = []
    received = 0
    while True:
        chunk = response.read(min(65536, max_bytes + 1 - received))
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        received += len(chunk)
        if received > max_bytes:
            raise SafeFetchError("The response is too large.", 502)


class _PinnedHTTPConnection(http.client.HTTPConnection):
    """HTTP connection to a pre-validated address; ``Host`` stays the original host name."""

    def __init__(self, host: str, port: int, address: str, timeout: float) -> None:
        super().__init__(host, port, timeout=timeout)
        self._address = address

    def connect(self) -> None:
        self.sock = socket.create_connection((self._address, self.port), self.timeout)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS connection to a pre-validated address; SNI and certificate check use the host name."""

    def __init__(
        self, host: str, port: int, address: str, timeout: float, context: ssl.SSLContext
    ) -> None:
        super().__init__(host, port, timeout=timeout, context=context)
        self._address = address
        self._ssl_context = context

    def connect(self) -> None:
        sock = socket.create_connection((self._address, self.port), self.timeout)
        self.sock = self._ssl_context.wrap_socket(sock, server_hostname=self.host)
