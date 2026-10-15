// Custom renderers for the demo widgets. Without them the generic renderer is used.
(function () {
  "use strict";

  function el(tag, text, attrs) {
    var node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    Object.keys(attrs || {}).forEach(function (key) {
      node.setAttribute(key, attrs[key]);
    });
    return node;
  }

  function linkList(items, label) {
    var list = el("ul");
    items.forEach(function (item) {
      var li = el("li");
      var href = /^https?:\/\//i.test(item.url || "") ? item.url : null;
      li.appendChild(
        href ? el("a", item.title, { href: href, target: "_blank", rel: "noopener noreferrer" }) : el("span", item.title)
      );
      if (item.extra) li.appendChild(el("small", " · " + item.extra));
      list.appendChild(li);
    });
    if (!items.length) list.appendChild(el("li", label));
    return list;
  }

  WidgetHub.registerRenderer("weather.current", function (element, data) {
    element.appendChild(el("p", data.city, { class: "demo-muted" }));
    element.appendChild(el("p", data.temperature, { class: "demo-big" }));
    element.appendChild(
      el("p", "Feels like " + data.feels_like + " · humidity " + data.humidity + " · wind " + data.wind)
    );
  });

  WidgetHub.registerRenderer("rss.latest", function (element, data) {
    element.appendChild(el("p", data.title, { class: "demo-muted" }));
    element.appendChild(
      linkList(
        data.items.map(function (item) {
          return { title: item.title || "(untitled)", url: item.link };
        }),
        "No article."
      )
    );
  });

  WidgetHub.registerRenderer("github.my_repositories", function (element, data) {
    element.appendChild(
      linkList(
        data.repositories.map(function (repo) {
          return { title: repo.name, url: repo.url, extra: "★ " + repo.stars };
        }),
        "No repository."
      )
    );
  });
})();
