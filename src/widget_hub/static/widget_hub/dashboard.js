/*
 * django-widget-hub built-in dashboard. No dependencies.
 *
 * Mounted on every `.wh-dashboard[data-wh-instances]` element rendered by {% dashboard %}.
 * Custom data rendering: WidgetHub.registerRenderer("service.widget", (element, data) => {...}).
 * Everything coming from the server is inserted with textContent / safe attributes only.
 */
(function (root) {
  "use strict";

  var COLUMNS = 12;
  var MAX_ROWS = 12;
  var DEFAULT_SIZE = { w: 4, h: 3 };
  var SAFE_METHODS = ["GET", "HEAD", "OPTIONS"];
  var renderers = {};

  /* ---------- pure helpers (unit-tested with node --test) ---------- */

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  /** Fill in a missing or partial grid position; new widgets flow left to right. */
  function normalizePosition(position, index) {
    var p = position || {};
    var w = clamp(Number.isInteger(p.w) ? p.w : DEFAULT_SIZE.w, 1, COLUMNS);
    var h = clamp(Number.isInteger(p.h) ? p.h : DEFAULT_SIZE.h, 1, MAX_ROWS);
    var perRow = Math.floor(COLUMNS / DEFAULT_SIZE.w);
    var x = Number.isInteger(p.x) ? p.x : (index % perRow) * DEFAULT_SIZE.w;
    var y = Number.isInteger(p.y) ? p.y : Math.floor(index / perRow) * DEFAULT_SIZE.h;
    return { x: clamp(x, 0, COLUMNS - w), y: Math.max(0, y), w: w, h: h };
  }

  function moveBy(position, dx, dy) {
    return {
      x: clamp(position.x + dx, 0, COLUMNS - position.w),
      y: Math.max(0, position.y + dy),
      w: position.w,
      h: position.h,
    };
  }

  function resizeBy(position, dw, dh) {
    return {
      x: position.x,
      y: position.y,
      w: clamp(position.w + dw, 1, COLUMNS - position.x),
      h: clamp(position.h + dh, 1, MAX_ROWS),
    };
  }

  /** CSS grid placement; ``order`` keeps reading order when small screens stack widgets. */
  function gridStyle(position) {
    return {
      gridColumn: position.x + 1 + " / span " + position.w,
      gridRow: position.y + 1 + " / span " + position.h,
      order: String(position.y * COLUMNS + position.x),
    };
  }

  /** "2 min ago"-style label for an age in seconds. */
  function relativeTime(seconds) {
    if (seconds < 45) return "just now";
    var minutes = Math.round(seconds / 60);
    if (minutes < 60) return minutes + " min ago";
    var hours = Math.round(minutes / 60);
    if (hours < 24) return hours + " h ago";
    var days = Math.round(hours / 24);
    return days + (days === 1 ? " day ago" : " days ago");
  }

  /** Short summary of an instance's text params (URLs shown as their host), for subtitles. */
  function summarizeParams(params, values) {
    var parts = [];
    (params || []).forEach(function (param) {
      var value = values ? values[param.name] : undefined;
      if (value === undefined || value === null || value === "") return;
      if (param.type === "url") {
        var match = /^https?:\/\/([^/?#:]+)/i.exec(String(value));
        parts.push(match ? match[1] : String(value));
      } else if (param.type === "string" || param.type === "choice") {
        parts.push(String(value));
      }
    });
    return parts.join(" · ");
  }

  function samePosition(a, b) {
    return a.x === b.x && a.y === b.y && a.w === b.w && a.h === b.h;
  }

  function overlaps(a, b) {
    return a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
  }

  function collides(position, others) {
    return others.some(function (other) {
      return overlaps(position, other);
    });
  }

  /** First free top-left slot (row by row) where a widget of the given size fits. */
  function firstFreeSlot(others, size) {
    var w = clamp(size.w, 1, COLUMNS);
    for (var y = 0; ; y++) {
      for (var x = 0; x + w <= COLUMNS; x++) {
        var candidate = { x: x, y: y, w: w, h: size.h };
        if (!collides(candidate, others)) return candidate;
      }
    }
  }

  /** Turn a widget param schema (Widget.schema()["params"]) into form field descriptors. */
  function fieldsFromSchema(params, values) {
    values = values || {};
    return params.map(function (param) {
      var field = {
        name: param.name,
        label: param.label || param.name,
        help: param.help_text || "",
        required: Boolean(param.required),
        attrs: {},
        options: null,
      };
      var current = Object.prototype.hasOwnProperty.call(values, param.name)
        ? values[param.name]
        : param["default"];
      if (param.type === "integer") {
        field.input = "number";
        field.attrs.step = "1";
        if (param.min_value !== undefined) field.attrs.min = String(param.min_value);
        if (param.max_value !== undefined) field.attrs.max = String(param.max_value);
      } else if (param.type === "boolean") {
        field.input = "checkbox";
        field.required = false;
      } else if (param.type === "choice") {
        field.input = "select";
        field.options = param.choices.slice();
      } else {
        field.input = param.type === "url" ? "url" : "text";
        if (param.min_length !== undefined) field.attrs.minlength = String(param.min_length);
        if (param.max_length !== undefined) field.attrs.maxlength = String(param.max_length);
      }
      field.value = current === undefined || current === null ? null : current;
      return field;
    });
  }

  /** Convert raw form values ({name: string|boolean}) to the JSON params payload. */
  function paramsFromForm(params, raw) {
    var out = {};
    params.forEach(function (param) {
      var value = raw[param.name];
      if (param.type === "boolean") {
        out[param.name] = Boolean(value);
        return;
      }
      if (value === undefined || value === null || String(value).trim() === "") return;
      if (param.type === "integer" && /^\s*-?\d+\s*$/.test(String(value))) {
        out[param.name] = parseInt(value, 10);
      } else {
        out[param.name] = value;
      }
    });
    return out;
  }

  function isHttpUrl(value) {
    return typeof value === "string" && /^https?:\/\/[^\s]+$/i.test(value);
  }

  function isImageUrl(value) {
    return isHttpUrl(value) && /\.(png|jpe?g|gif|webp|avif)(\?.*)?$/i.test(value);
  }

  function csrfHeaderName(dashboard) {
    return dashboard.getAttribute("data-wh-csrf-header") || "X-CSRFToken";
  }

  /* ---------- DOM helpers ---------- */

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (key) {
      var value = attrs[key];
      if (value === null || value === undefined || value === false) return;
      if (key === "text") node.textContent = value;
      else if (key === "className") node.className = value;
      else node.setAttribute(key, value === true ? "" : String(value));
    });
    (children || []).forEach(function (child) {
      if (child) node.appendChild(child);
    });
    return node;
  }

  var SVG_NS = "http://www.w3.org/2000/svg";
  // 24×24 stroke icons drawn for this file (no third-party icon set).
  var ICONS = {
    grip: [["circle", { cx: 9, cy: 6, r: 1 }], ["circle", { cx: 15, cy: 6, r: 1 }],
           ["circle", { cx: 9, cy: 12, r: 1 }], ["circle", { cx: 15, cy: 12, r: 1 }],
           ["circle", { cx: 9, cy: 18, r: 1 }], ["circle", { cx: 15, cy: 18, r: 1 }]],
    refresh: [["path", { d: "M20 12a8 8 0 1 1-2.34-5.66" }], ["path", { d: "M20 4v5h-5" }]],
    sliders: [["path", { d: "M4 7h10M18 7h2M4 17h4M12 17h8" }],
              ["circle", { cx: 16, cy: 7, r: 2 }], ["circle", { cx: 10, cy: 17, r: 2 }]],
    close: [["path", { d: "M6 6l12 12M18 6L6 18" }]],
    alert: [["circle", { cx: 12, cy: 12, r: 9 }], ["path", { d: "M12 7.5v5.5M12 16.5v.01" }]],
  }; // prettier-ignore

  function icon(name) {
    var svg = document.createElementNS(SVG_NS, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("class", "wh-icon");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");
    ICONS[name].forEach(function (shape) {
      var node = document.createElementNS(SVG_NS, shape[0]);
      Object.keys(shape[1]).forEach(function (key) {
        node.setAttribute(key, String(shape[1][key]));
      });
      svg.appendChild(node);
    });
    return svg;
  }

  function iconButton(name, label, extraClass) {
    var button = el("button", {
      type: "button",
      className: "wh-icon-button" + (extraClass ? " " + extraClass : ""),
      "aria-label": label,
      title: label,
    });
    button.appendChild(icon(name));
    return button;
  }

  function skeleton() {
    return el("div", { className: "wh-skeleton", "aria-hidden": "true" }, [
      el("span"),
      el("span"),
      el("span"),
    ]);
  }

  /** Generic, safe rendering of any JSON value. */
  function renderValue(value, depth) {
    depth = depth || 0;
    if (value === null || value === undefined) return el("span", { text: "—" });
    if (depth > 4) return el("span", { text: "…" });
    if (Array.isArray(value)) {
      var list = el("ul");
      value.slice(0, 50).forEach(function (item) {
        list.appendChild(el("li", {}, [renderValue(item, depth + 1)]));
      });
      if (value.length === 0) return el("span", { text: "(empty)" });
      return list;
    }
    if (typeof value === "object") {
      var dl = el("dl");
      Object.keys(value).forEach(function (key) {
        dl.appendChild(el("dt", { text: key.replace(/_/g, " ") }));
        dl.appendChild(el("dd", {}, [renderValue(value[key], depth + 1)]));
      });
      return dl;
    }
    if (isImageUrl(value)) return el("img", { src: value, alt: "", loading: "lazy" });
    if (isHttpUrl(value)) {
      return el("a", { href: value, target: "_blank", rel: "noopener noreferrer", text: value });
    }
    return el("span", { text: String(value) });
  }

  /* ---------- HTTP ---------- */

  function Client(dashboard) {
    var tokenInput = dashboard.querySelector("input[name=csrfmiddlewaretoken]");
    this.token = tokenInput ? tokenInput.value : "";
    this.header = csrfHeaderName(dashboard);
  }

  Client.prototype.request = function (method, url, body) {
    var headers = { Accept: "application/json" };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (SAFE_METHODS.indexOf(method) === -1) headers[this.header] = this.token;
    return fetch(url, {
      method: method,
      headers: headers,
      credentials: "same-origin",
      body: body === undefined ? undefined : JSON.stringify(body),
    }).then(function (response) {
      if (response.status === 204) return null;
      return response
        .json()
        .catch(function () {
          return null;
        })
        .then(function (payload) {
          if (response.ok) return payload;
          var info = (payload && payload.error) || {};
          var error = new Error(info.message || "Request failed (" + response.status + ").");
          error.status = response.status;
          error.details = info.details || null;
          throw error;
        });
    });
  };

  /* ---------- dashboard ---------- */

  function Dashboard(root) {
    this.root = root;
    this.grid = root.querySelector("[data-wh-grid]");
    this.live = root.querySelector("[data-wh-live]");
    this.empty = root.querySelector("[data-wh-empty]");
    this.urls = {
      catalog: root.getAttribute("data-wh-catalog"),
      instances: root.getAttribute("data-wh-instances"),
      credentials: root.getAttribute("data-wh-credentials"),
    };
    this.minRefresh = parseInt(root.getAttribute("data-wh-min-refresh"), 10) || 30;
    this.maxRefresh = parseInt(root.getAttribute("data-wh-max-refresh"), 10) || 86400;
    this.client = new Client(root);
    this.catalog = [];
    this.widgets = {};
    this.dialog = null;
  }

  Dashboard.prototype.start = function () {
    var self = this;
    this.root.querySelectorAll("[data-wh-add]").forEach(function (add) {
      add.addEventListener("click", function () {
        self.openForm(null, add);
      });
    });
    document.addEventListener("visibilitychange", function () {
      self.onVisibilityChange();
    });
    setInterval(function () {
      Object.keys(self.widgets).forEach(function (id) {
        self.widgets[id].updateMeta();
      });
    }, 30000);
    return Promise.all([
      this.client.request("GET", this.urls.catalog),
      this.client.request("GET", this.urls.instances),
    ])
      .then(function (results) {
        self.catalog = results[0];
        results[1].forEach(function (instance, index) {
          self.addWidget(instance, index);
        });
        self.updateEmpty();
      })
      .catch(function (error) {
        self.announce("The dashboard could not be loaded: " + error.message);
      });
  };

  Dashboard.prototype.announce = function (message) {
    if (this.live) this.live.textContent = message;
  };

  Dashboard.prototype.updateEmpty = function () {
    if (this.empty) this.empty.hidden = Object.keys(this.widgets).length > 0;
  };

  Dashboard.prototype.schemaFor = function (instance) {
    for (var i = 0; i < this.catalog.length; i++) {
      var item = this.catalog[i];
      if (item.service === instance.service && item.name === instance.widget) return item;
    }
    return null;
  };

  Dashboard.prototype.instanceUrl = function (id) {
    return this.urls.instances + "/" + encodeURIComponent(id);
  };

  /** Positions of every widget except ``exclude``. */
  Dashboard.prototype.positions = function (exclude) {
    var self = this;
    return Object.keys(this.widgets)
      .map(function (id) {
        return self.widgets[id];
      })
      .filter(function (widget) {
        return widget !== exclude;
      })
      .map(function (widget) {
        return widget.position;
      });
  };

  Dashboard.prototype.addWidget = function (instance, index) {
    var widget = new WidgetView(this, instance, index);
    var stored = instance.position || {};
    if (!Number.isInteger(stored.x) || !Number.isInteger(stored.y)) {
      widget.position = firstFreeSlot(this.positions(null), widget.position);
      widget.applyPosition();
    }
    this.widgets[instance.id] = widget;
    this.grid.appendChild(widget.node);
    widget.load();
    return widget;
  };

  Dashboard.prototype.removeWidget = function (widget) {
    widget.stop();
    delete this.widgets[widget.instance.id];
    widget.node.remove();
    this.updateEmpty();
  };

  Dashboard.prototype.onVisibilityChange = function () {
    var self = this;
    Object.keys(this.widgets).forEach(function (id) {
      var widget = self.widgets[id];
      if (document.hidden) widget.pause();
      else widget.resume();
    });
  };

  /* ---------- one widget ---------- */

  var uid = 0;

  function WidgetView(dashboard, instance, index) {
    this.dashboard = dashboard;
    this.instance = instance;
    this.position = normalizePosition(instance.position, index);
    this.timer = null;
    this.nextAt = 0;
    this.saveTimer = null;
    this.build();
  }

  WidgetView.prototype.label = function () {
    var schema = this.dashboard.schemaFor(this.instance);
    var base = schema && schema.description ? schema.description : this.instance.widget;
    return base;
  };

  WidgetView.prototype.subtitle = function () {
    var schema = this.dashboard.schemaFor(this.instance);
    return schema ? summarizeParams(schema.params, this.instance.params) : "";
  };

  WidgetView.prototype.build = function () {
    var self = this;
    var titleId = "wh-title-" + ++uid;
    this.title = el("h3", { className: "wh-widget-title", id: titleId, text: this.label() });
    this.subtitleNode = el("p", { className: "wh-widget-subtitle", text: this.subtitle() });
    this.handle = iconButton("grip", "Move or resize " + this.label(), "wh-handle");
    this.handle.setAttribute("aria-describedby", "wh-move-help");
    this.refreshButton = iconButton("refresh", "Refresh " + this.label());
    var settings = iconButton("sliders", "Settings of " + this.label());
    var remove = iconButton("close", "Remove " + this.label(), "wh-danger");
    var retry = el("button", { type: "button", className: "wh-link-button", text: "Try again" });
    this.errorText = el("p");
    this.error = el("div", { className: "wh-widget-error", role: "status", hidden: true }, [
      icon("alert"),
      el("div", { className: "wh-widget-error-text" }, [
        this.errorText,
        el("p", { className: "wh-error-hint" }, [
          document.createTextNode("Retries at the next refresh. "),
          retry,
        ]),
      ]),
    ]);
    this.content = el("div", { className: "wh-data" }, [skeleton()]);
    this.body = el("div", { className: "wh-widget-body" }, [this.error, this.content]);
    this.meta = el("p", { className: "wh-widget-meta" });
    this.resizer = el("span", { className: "wh-resize", "aria-hidden": "true" });
    this.node = el(
      "article",
      { className: "wh-widget", role: "listitem", "aria-labelledby": titleId },
      [
        el("header", { className: "wh-widget-header" }, [
          this.handle,
          el("div", { className: "wh-widget-heading" }, [this.title, this.subtitleNode]),
          this.refreshButton,
          settings,
          remove,
        ]),
        this.body,
        this.meta,
        this.resizer,
      ]
    );
    this.applyPosition();

    this.refreshButton.addEventListener("click", function () {
      self.load();
    });
    retry.addEventListener("click", function () {
      self.load();
    });
    settings.addEventListener("click", function () {
      self.dashboard.openForm(self, settings);
    });
    remove.addEventListener("click", function () {
      self.destroy(remove);
    });
    this.handle.addEventListener("keydown", function (event) {
      self.onKey(event);
    });
    this.enablePointer(this.handle, "move");
    this.enablePointer(this.resizer, "resize");
  };

  WidgetView.prototype.applyPosition = function () {
    var style = gridStyle(this.position);
    this.node.style.gridColumn = style.gridColumn;
    this.node.style.gridRow = style.gridRow;
    this.node.style.order = style.order;
  };

  WidgetView.prototype.describePosition = function () {
    var p = this.position;
    return (
      this.label() +
      ": column " + (p.x + 1) + ", row " + (p.y + 1) +
      ", " + p.w + " wide, " + p.h + " high."
    );
  };

  WidgetView.prototype.onKey = function (event) {
    var deltas = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
    var delta = deltas[event.key];
    if (!delta) return;
    event.preventDefault();
    var next = event.shiftKey
      ? resizeBy(this.position, delta[0], delta[1])
      : moveBy(this.position, delta[0], delta[1]);
    if (samePosition(next, this.position)) return;
    if (collides(next, this.dashboard.positions(this))) {
      this.dashboard.announce("Another widget is in the way.");
      return;
    }
    this.position = next;
    this.applyPosition();
    this.dashboard.announce(this.describePosition());
    this.savePositionSoon();
  };

  WidgetView.prototype.enablePointer = function (target, mode) {
    var self = this;
    target.addEventListener("pointerdown", function (event) {
      if (event.button !== 0) return;
      event.preventDefault();
      var grid = self.dashboard.grid;
      var styles = getComputedStyle(grid);
      var gap = parseFloat(styles.columnGap) || 0;
      var cellW = (grid.clientWidth - gap * (COLUMNS - 1)) / COLUMNS + gap;
      var cellH = (parseFloat(styles.gridAutoRows) || 90) + (parseFloat(styles.rowGap) || 0);
      var start = { x: event.clientX, y: event.clientY, position: self.position };
      target.setPointerCapture(event.pointerId);
      self.node.classList.add("wh-dragging");

      var others = self.dashboard.positions(self);

      function onMove(moveEvent) {
        var dx = Math.round((moveEvent.clientX - start.x) / cellW);
        var dy = Math.round((moveEvent.clientY - start.y) / cellH);
        var next =
          mode === "move" ? moveBy(start.position, dx, dy) : resizeBy(start.position, dx, dy);
        if (collides(next, others)) return; // keep the last position that fits
        self.position = next;
        self.applyPosition();
      }

      function onUp() {
        target.removeEventListener("pointermove", onMove);
        target.removeEventListener("pointerup", onUp);
        target.removeEventListener("pointercancel", onUp);
        self.node.classList.remove("wh-dragging");
        if (!samePosition(start.position, self.position)) {
          self.dashboard.announce(self.describePosition());
          self.savePosition();
        }
      }

      target.addEventListener("pointermove", onMove);
      target.addEventListener("pointerup", onUp);
      target.addEventListener("pointercancel", onUp);
    });
  };

  WidgetView.prototype.savePositionSoon = function () {
    var self = this;
    clearTimeout(this.saveTimer);
    this.saveTimer = setTimeout(function () {
      self.savePosition();
    }, 400);
  };

  WidgetView.prototype.savePosition = function () {
    var self = this;
    return this.dashboard.client
      .request("PATCH", this.dashboard.instanceUrl(this.instance.id), { position: this.position })
      .then(function (instance) {
        self.instance = instance;
      })
      .catch(function (error) {
        self.dashboard.announce("Position not saved: " + error.message);
      });
  };

  WidgetView.prototype.load = function () {
    var self = this;
    clearTimeout(this.timer);
    this.body.setAttribute("aria-busy", "true");
    this.refreshButton.disabled = true;
    this.refreshButton.firstChild.classList.add("wh-spin");
    var url = this.dashboard.instanceUrl(this.instance.id) + "/data";
    return this.dashboard.client
      .request("GET", url)
      .then(function (result) {
        self.error.hidden = true;
        self.render(result.data);
        self.hasData = true;
        self.fetchedAt = Date.parse(result.fetched_at);
        self.updateMeta();
      })
      .catch(function (error) {
        // Keep the last good data visible; the error stays inside this widget only.
        if (!self.hasData) self.content.replaceChildren();
        self.errorText.textContent = error.message;
        self.error.hidden = false;
      })
      .then(function () {
        self.body.removeAttribute("aria-busy");
        self.refreshButton.disabled = false;
        self.refreshButton.firstChild.classList.remove("wh-spin");
        self.schedule(self.instance.refresh_rate * 1000);
      });
  };

  WidgetView.prototype.updateMeta = function () {
    if (!this.fetchedAt) return;
    var seconds = Math.max(0, (Date.now() - this.fetchedAt) / 1000);
    this.meta.textContent = "Updated " + relativeTime(seconds);
    this.meta.title = new Date(this.fetchedAt).toLocaleString();
  };

  WidgetView.prototype.render = function (data) {
    var key = this.instance.service + "." + this.instance.widget;
    this.content.replaceChildren();
    if (renderers[key]) {
      try {
        renderers[key](this.content, data, this.instance);
        return;
      } catch (error) {
        this.content.replaceChildren();
      }
    }
    this.content.appendChild(renderValue(data));
  };

  WidgetView.prototype.schedule = function (delay) {
    var self = this;
    clearTimeout(this.timer);
    this.nextAt = Date.now() + delay;
    if (document.hidden) return; // resumed by the visibilitychange handler
    this.timer = setTimeout(function () {
      self.load();
    }, delay);
  };

  WidgetView.prototype.pause = function () {
    clearTimeout(this.timer);
    this.timer = null;
  };

  WidgetView.prototype.resume = function () {
    var remaining = this.nextAt - Date.now();
    if (remaining <= 0) this.load();
    else this.schedule(remaining);
  };

  WidgetView.prototype.stop = function () {
    clearTimeout(this.timer);
    clearTimeout(this.saveTimer);
  };

  WidgetView.prototype.destroy = function (trigger) {
    var self = this;
    if (!window.confirm("Remove “" + this.label() + "” from the dashboard?")) return;
    trigger.disabled = true;
    this.dashboard.client
      .request("DELETE", this.dashboard.instanceUrl(this.instance.id))
      .then(function () {
        self.dashboard.removeWidget(self);
        self.dashboard.announce(self.label() + " removed.");
        var add = self.dashboard.root.querySelector("[data-wh-add]");
        if (add) add.focus();
      })
      .catch(function (error) {
        trigger.disabled = false;
        self.dashboard.announce("Could not remove the widget: " + error.message);
      });
  };

  /* ---------- add / settings dialog ---------- */

  Dashboard.prototype.openForm = function (widget, trigger) {
    var self = this;
    if (this.dialog) this.dialog.remove();
    var editing = Boolean(widget);
    var dialog = el("dialog", { className: "wh-dialog", "aria-labelledby": "wh-dialog-title" });
    var form = el("form", { method: "dialog", novalidate: true });
    var formError = el("p", { className: "wh-form-error", role: "alert", hidden: true });
    var fieldsBox = el("div");
    var heading = el("h3", {
      id: "wh-dialog-title",
      text: editing ? widget.label() : "Add a widget",
    });
    var close = iconButton("close", "Close");
    form.appendChild(el("div", { className: "wh-dialog-header" }, [heading, close]));
    form.appendChild(formError);

    var picker = null;
    if (!editing) {
      picker = el("select", { id: "wh-pick", name: "__widget", required: true });
      picker.appendChild(el("option", { value: "", text: "Choose a widget…" }));
      var groups = {};
      this.catalog.forEach(function (item, i) {
        if (!groups[item.service]) {
          groups[item.service] = el("optgroup", { label: item.service });
          picker.appendChild(groups[item.service]);
        }
        groups[item.service].appendChild(
          el("option", { value: String(i), text: item.description || item.name })
        );
      });
      form.appendChild(
        el("div", { className: "wh-field" }, [
          el("label", { for: "wh-pick", text: "Widget" }),
          picker,
        ])
      );
    }
    form.appendChild(fieldsBox);

    var current = { schema: editing ? this.schemaFor(widget.instance) : null };

    function drawFields() {
      fieldsBox.replaceChildren();
      var schema = current.schema;
      if (!schema) return;
      var values = editing ? widget.instance.params : {};
      fieldsFromSchema(schema.params, values).forEach(function (field) {
        fieldsBox.appendChild(buildField(field));
      });
      var rate = editing ? widget.instance.refresh_rate : schema.default_refresh_rate;
      rate = clamp(rate, self.minRefresh, self.maxRefresh);
      fieldsBox.appendChild(
        buildField({
          name: "__refresh_rate",
          label: "Refresh every (seconds)",
          help: "Between " + self.minRefresh + " and " + self.maxRefresh + " seconds.",
          required: true,
          input: "number",
          attrs: { min: String(self.minRefresh), max: String(self.maxRefresh), step: "1" },
          value: rate,
        })
      );
      if (schema.uses_credential) {
        fieldsBox.appendChild(
          buildField({
            name: "__secret",
            label: "API token for " + schema.service + " (optional)",
            help: "Stored encrypted. Leave empty to keep the current one.",
            required: false,
            input: "password",
            attrs: { autocomplete: "off" },
            value: null,
          })
        );
      }
    }

    if (picker) {
      picker.addEventListener("change", function () {
        current.schema = picker.value === "" ? null : self.catalog[parseInt(picker.value, 10)];
        drawFields();
      });
    }
    drawFields();

    var cancel = el("button", { type: "button", className: "wh-button", text: "Cancel" });
    var submit = el("button", {
      type: "submit",
      className: "wh-button wh-button-primary",
      text: editing ? "Save" : "Add",
    });
    form.appendChild(el("div", { className: "wh-dialog-actions" }, [cancel, submit]));
    dialog.appendChild(form);
    this.root.appendChild(dialog);
    this.dialog = dialog;

    var focusAfter = trigger; // where focus returns when the dialog closes
    [cancel, close].forEach(function (button) {
      button.addEventListener("click", function () {
        dialog.close();
      });
    });
    dialog.addEventListener("close", function () {
      dialog.remove();
      if (self.dialog === dialog) self.dialog = null;
      if (focusAfter && document.contains(focusAfter)) focusAfter.focus();
    });

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      clearErrors(form, formError);
      var schema = current.schema;
      if (!schema) {
        showFormError(formError, "Choose a widget first.");
        return;
      }
      var raw = readForm(form);
      var payload = {
        params: paramsFromForm(schema.params, raw),
        refresh_rate: /^\d+$/.test(raw.__refresh_rate) ? parseInt(raw.__refresh_rate, 10) : raw.__refresh_rate,
      };
      submit.disabled = true;
      submit.textContent = editing ? "Saving…" : "Adding…";
      var secret = raw.__secret ? String(raw.__secret) : "";
      var saveSecret = secret
        ? self.client.request(
            "PUT",
            self.urls.credentials + "/" + encodeURIComponent(schema.service),
            { secret: secret }
          )
        : Promise.resolve();
      saveSecret
        .then(function () {
          if (editing) {
            return self.client.request("PATCH", self.instanceUrl(widget.instance.id), payload);
          }
          payload.service = schema.service;
          payload.widget = schema.name;
          return self.client.request("POST", self.urls.instances, payload);
        })
        .then(function (instance) {
          if (editing) {
            widget.instance = instance;
            widget.subtitleNode.textContent = widget.subtitle();
            widget.load();
            self.announce(widget.label() + " updated.");
          } else {
            var view = self.addWidget(instance, Object.keys(self.widgets).length);
            self.updateEmpty();
            self.announce(view.label() + " added.");
            if (!instance.position || !Object.keys(instance.position).length) view.savePosition();
            focusAfter = view.handle;
          }
          dialog.close();
        })
        .catch(function (error) {
          submit.disabled = false;
          submit.textContent = editing ? "Save" : "Add";
          showErrors(form, formError, error);
        });
    });

    dialog.showModal();
    var first = form.querySelector("select, input");
    if (first) first.focus();
  };

  function buildField(field) {
    var id = "wh-field-" + field.name + "-" + ++uid;
    var input;
    if (field.input === "select") {
      input = el("select", { id: id, name: field.name, required: field.required });
      if (!field.required) input.appendChild(el("option", { value: "", text: "—" }));
      field.options.forEach(function (option) {
        input.appendChild(
          el("option", { value: option, text: option, selected: option === field.value })
        );
      });
    } else {
      var attrs = {
        id: id,
        name: field.name,
        type: field.input,
        required: field.required,
      };
      Object.keys(field.attrs || {}).forEach(function (key) {
        attrs[key] = field.attrs[key];
      });
      if (field.input === "checkbox") attrs.checked = Boolean(field.value);
      else if (field.value !== null && field.value !== undefined) attrs.value = String(field.value);
      input = el("input", attrs);
    }
    var errorId = id + "-error";
    var error = el("p", {
      className: "wh-field-error",
      id: errorId,
      "data-wh-error-for": field.name,
      hidden: true,
    });
    var helpId = id + "-help";
    input.setAttribute("aria-describedby", (field.help ? helpId + " " : "") + errorId);
    var children = [];
    var label = el("label", { for: id, text: field.label });
    if (field.required) {
      label.appendChild(document.createTextNode(" "));
      label.appendChild(el("span", { className: "wh-required", "aria-hidden": "true", text: "*" }));
    }
    if (field.input === "checkbox") children.push(input, label);
    else children.push(label, input);
    if (field.help) {
      children.push(el("span", { className: "wh-field-help", id: helpId, text: field.help }));
    }
    children.push(error);
    return el(
      "div",
      { className: "wh-field" + (field.input === "checkbox" ? " wh-field-inline" : "") },
      children
    );
  }

  function readForm(form) {
    var raw = {};
    Array.prototype.forEach.call(form.elements, function (input) {
      if (!input.name) return;
      raw[input.name] = input.type === "checkbox" ? input.checked : input.value;
    });
    return raw;
  }

  function clearErrors(form, formError) {
    formError.hidden = true;
    formError.textContent = "";
    form.querySelectorAll("[data-wh-error-for]").forEach(function (node) {
      node.hidden = true;
      node.textContent = "";
    });
    form.querySelectorAll("[aria-invalid]").forEach(function (node) {
      node.removeAttribute("aria-invalid");
    });
  }

  function showFormError(formError, message) {
    formError.textContent = message;
    formError.hidden = false;
  }

  function showFieldError(form, name, message) {
    var target = form.querySelector('[data-wh-error-for="' + name + '"]');
    if (!target) return false;
    target.textContent = message;
    target.hidden = false;
    var input = form.querySelector('[name="' + name + '"]');
    if (input) input.setAttribute("aria-invalid", "true");
    return true;
  }

  function showErrors(form, formError, error) {
    var details = error.details || {};
    var unplaced = [];
    Object.keys(details).forEach(function (key) {
      var value = details[key];
      if (key === "params" && value && typeof value === "object") {
        Object.keys(value).forEach(function (name) {
          if (!showFieldError(form, name, value[name])) unplaced.push(name + ": " + value[name]);
        });
      } else if (key === "refresh_rate") {
        showFieldError(form, "__refresh_rate", value);
      } else if (key === "secret") {
        showFieldError(form, "__secret", value);
      } else {
        unplaced.push(key === "__all__" ? value : key + ": " + value);
      }
    });
    var invalid = form.querySelector("[aria-invalid]");
    if (unplaced.length) showFormError(formError, unplaced.join(" "));
    else showFormError(formError, invalid ? "Check the highlighted fields." : error.message);
    if (invalid) invalid.focus();
  }

  /* ---------- public API ---------- */

  var api = {
    registerRenderer: function (key, fn) {
      renderers[key] = fn;
    },
    _internals: {
      normalizePosition: normalizePosition,
      moveBy: moveBy,
      resizeBy: resizeBy,
      gridStyle: gridStyle,
      relativeTime: relativeTime,
      summarizeParams: summarizeParams,
      overlaps: overlaps,
      firstFreeSlot: firstFreeSlot,
      fieldsFromSchema: fieldsFromSchema,
      paramsFromForm: paramsFromForm,
      isHttpUrl: isHttpUrl,
      isImageUrl: isImageUrl,
      COLUMNS: COLUMNS,
    },
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
    return;
  }

  root.WidgetHub = api;

  function init() {
    document.querySelectorAll(".wh-dashboard[data-wh-instances]").forEach(function (node) {
      if (node.__whMounted) return;
      node.__whMounted = true;
      new Dashboard(node).start();
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})(typeof window !== "undefined" ? window : globalThis);
