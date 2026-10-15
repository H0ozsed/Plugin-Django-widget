// Unit tests of the dashboard's pure helpers: `node --test tests/js/`
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const { _internals: h } = require(
  path.join(__dirname, "../../src/widget_hub/static/widget_hub/dashboard.js")
);

test("normalizePosition fills gaps and flows new widgets left to right", () => {
  assert.deepEqual(h.normalizePosition({}, 0), { x: 0, y: 0, w: 4, h: 2 });
  assert.deepEqual(h.normalizePosition(undefined, 2), { x: 8, y: 0, w: 4, h: 2 });
  assert.deepEqual(h.normalizePosition({}, 3), { x: 0, y: 2, w: 4, h: 2 });
  assert.deepEqual(h.normalizePosition({ x: 11, y: 1, w: 6, h: 3 }, 0), { x: 6, y: 1, w: 6, h: 3 });
  assert.deepEqual(h.normalizePosition({ w: 99, h: 0 }, 0), { x: 0, y: 0, w: 12, h: 1 });
});

test("moveBy stays inside the grid", () => {
  const p = { x: 0, y: 0, w: 4, h: 2 };
  assert.deepEqual(h.moveBy(p, -1, -1), p);
  assert.deepEqual(h.moveBy(p, 20, 3), { x: 8, y: 3, w: 4, h: 2 });
});

test("resizeBy keeps at least one cell and the right edge", () => {
  const p = { x: 6, y: 0, w: 4, h: 2 };
  assert.deepEqual(h.resizeBy(p, 10, 0), { x: 6, y: 0, w: 6, h: 2 });
  assert.deepEqual(h.resizeBy(p, -10, -10), { x: 6, y: 0, w: 1, h: 1 });
});

test("overlaps detects shared cells only", () => {
  const a = { x: 0, y: 0, w: 4, h: 2 };
  assert.equal(h.overlaps(a, { x: 3, y: 1, w: 2, h: 2 }), true);
  assert.equal(h.overlaps(a, { x: 4, y: 0, w: 2, h: 2 }), false);
  assert.equal(h.overlaps(a, { x: 0, y: 2, w: 4, h: 1 }), false);
});

test("firstFreeSlot finds the first gap row by row", () => {
  const taken = [
    { x: 0, y: 0, w: 4, h: 2 },
    { x: 4, y: 0, w: 8, h: 1 },
  ];
  assert.deepEqual(h.firstFreeSlot(taken, { w: 4, h: 2 }), { x: 4, y: 1, w: 4, h: 2 });
  assert.deepEqual(h.firstFreeSlot([], { w: 4, h: 2 }), { x: 0, y: 0, w: 4, h: 2 });
  assert.deepEqual(h.firstFreeSlot([{ x: 0, y: 0, w: 12, h: 3 }], { w: 6, h: 1 }), {
    x: 0,
    y: 3,
    w: 6,
    h: 1,
  });
});

test("gridStyle maps positions to CSS grid lines", () => {
  assert.deepEqual(h.gridStyle({ x: 2, y: 1, w: 3, h: 2 }), {
    gridColumn: "3 / span 3",
    gridRow: "2 / span 2",
  });
});

test("fieldsFromSchema builds inputs from the param schema", () => {
  const fields = h.fieldsFromSchema(
    [
      { name: "city", type: "string", label: "City", required: true, max_length: 100 },
      { name: "days", type: "integer", label: "Days", required: false, default: 5, min_value: 1, max_value: 16 },
      { name: "metric", type: "boolean", label: "Metric", required: true },
      { name: "unit", type: "choice", label: "Unit", required: false, default: "c", choices: ["c", "f"] },
      { name: "feed", type: "url", label: "Feed", required: true, help_text: "RSS URL" },
    ],
    { city: "Lyon" }
  );
  assert.deepEqual(
    fields.map((f) => [f.name, f.input, f.required, f.value]),
    [
      ["city", "text", true, "Lyon"],
      ["days", "number", false, 5],
      ["metric", "checkbox", false, null],
      ["unit", "select", false, "c"],
      ["feed", "url", true, null],
    ]
  );
  assert.deepEqual(fields[0].attrs, { maxlength: "100" });
  assert.deepEqual(fields[1].attrs, { step: "1", min: "1", max: "16" });
  assert.deepEqual(fields[3].options, ["c", "f"]);
  assert.equal(fields[4].help, "RSS URL");
});

test("paramsFromForm converts types and omits empty optional values", () => {
  const params = [
    { name: "city", type: "string" },
    { name: "days", type: "integer" },
    { name: "metric", type: "boolean" },
    { name: "note", type: "string" },
    { name: "odd", type: "integer" },
  ];
  assert.deepEqual(
    h.paramsFromForm(params, { city: "Paris", days: "7", metric: false, note: "  ", odd: "1.5" }),
    { city: "Paris", days: 7, metric: false, odd: "1.5" }
  );
});

test("only http(s) URLs become links or images", () => {
  assert.equal(h.isHttpUrl("https://example.com/a"), true);
  assert.equal(h.isHttpUrl("javascript:alert(1)"), false);
  assert.equal(h.isHttpUrl("data:text/html,x"), false);
  assert.equal(h.isImageUrl("https://example.com/a.PNG?x=1"), true);
  assert.equal(h.isImageUrl("https://example.com/a.svg"), false);
});
