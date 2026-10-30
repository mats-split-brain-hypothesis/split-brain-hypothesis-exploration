// Local smoke test of dashboard/agent3.js, no browser or node needed (macOS JavaScriptCore):
//   osascript -l JavaScript dashboard/smoke_agent3.js
// Runs the page's build() and draw() against logs/sorh_persistence/dashboard/*.json with stand-ins for the DOM, d3 and
// the shared kit (RH). The stand-in kit checks what the real one needs: every dataset read exists, every field a chart
// or table names is in its rows, table keys are present and unique, every data-source id in the markup is a dataset,
// and every method box has a methods row. Prints problems, then "OK" or "FAILED".
ObjC.import('Foundation');
const ROOT = $.NSFileManager.defaultManager.currentDirectoryPath.js;
const read = (p) => {
  const s = $.NSString.stringWithContentsOfFileEncodingError(p, $.NSUTF8StringEncoding, null);
  return s.isNil() ? null : s.js;
};
const DIR = `${ROOT}/logs/sorh_persistence/dashboard`;
const problems = [];
const calls = [];
const need = (cond, msg) => { if (!cond) problems.push(msg); };

// ---- datasets ----
const cache = {};
const load = (id) => {
  if (!(id in cache)) {
    const t = read(`${DIR}/${id}.json`);
    cache[id] = t == null ? null : JSON.parse(t);
  }
  return cache[id];
};
globalThis.dash = {
  data: (id) => {
    const d = load(id);
    need(d != null, `dataset ${id} has no local file`);
    return d == null ? { status: 'missing', data: [] } : { status: 'ok', data: d };
  },
  colors: ['#c96442', '#5b8def', '#3d9a6b', '#b8862f', '#8a63d2', '#d0546e', '#4aa3b8', '#7c7c7c'],
};

// ---- d3 stand-in: chainable selections, simple helpers ----
const chain = () => new Proxy(function () {}, { get: (t, k) => (k === 'node' ? () => ({ getBBox: () => ({ width: 10 }) }) : () => chain()), apply: () => chain() });
globalThis.d3 = {
  select: () => chain(), selectAll: () => chain(),
  format: () => (v) => String(v),
  rgb: () => ({ r: 120, g: 120, b: 120 }), color: () => ({ r: 120, g: 120, b: 120 }),
  interpolateRgb: () => () => '#787878',
  min: (a, f) => Math.min(...a.map(f || ((x) => x))), max: (a, f) => Math.max(...a.map(f || ((x) => x))),
  sum: (a, f) => a.map(f || ((x) => x)).reduce((s, x) => s + (+x || 0), 0),
  scaleLinear: () => { const s = (v) => v; s.nice = () => s; s.ticks = () => [0, 1]; s.domain = () => [0, 1]; s.range = () => [0, 1]; return s; },
};

// ---- DOM stand-in ----
const mkEl = (id) => {
  const el = {
    id, children: [], dataset: {}, style: {}, className: '', textContent: '', clientWidth: 900,
    classList: { add() {} }, setAttribute() {}, addEventListener() {},
    append(...c) { this.children.push(...c); }, replaceChildren(...c) { this.children = c; },
    querySelector() { return null; }, querySelectorAll() { return []; },
  };
  return el;
};
globalThis.document = { createElement: () => mkEl(null) };

// ---- kit stand-in ----
const fieldsOf = (rows) => new Set(rows.flatMap((r) => Object.keys(r)));
const hasFields = (what, rows, fields) => {
  const f = fieldsOf(rows);
  for (const x of fields.filter(Boolean)) need(f.has(x), `${what}: field "${x}" not in its rows (${[...f].slice(0, 12).join(', ')})`);
};
const rowsFor = new Map();
globalThis.RH = {
  page: (id, spec) => { RH._spec = spec; },
  rows: (id, el) => {
    need(el != null, `RH.rows(${id}): its box is not in the markup`);
    const d = dash.data(id);
    if (d.status !== 'ok') return null;
    need(Array.isArray(d.data), `${id} is not an array of rows`);
    need(d.data.length > 0, `${id} is empty`);
    rowsFor.set(el, id);
    calls.push(`rows ${id} (${d.data.length})`);
    return d.data;
  },
  tip: () => ({ show() {}, hide() {} }),
  css: () => '#787878', series: (i) => dash.colors[i % 8],
  pct: (v) => String(v), pct1: (v) => String(v), int: (v) => String(v), num: (v) => String(v), usd: (v) => String(v),
  kn: (k, n) => `${k}/${n}`,
  findings: (el, rows, o = {}) => { hasFields('findings', rows, [o.text ?? 'finding', o.evidence ?? 'evidence']); calls.push('findings'); },
  rates: (el, rows, o = {}) => { need(rows.length > 0, 'rates: no rows'); hasFields('rates', rows, [o.label ?? 'label', o.k ?? 'k', o.n ?? 'n', o.group]); calls.push('rates'); },
  heat: (el, rows, o) => { hasFields('heat', rows, [o.row, o.col, o.value, o.n]); calls.push('heat'); },
  stack: (el, rows, o) => { hasFields('stack', rows, [o.label, o.category, o.value]); calls.push('stack'); },
  line: (el, rows, o) => {
    need(rows.length > 0, `line in #${el && el.id}: no rows after filtering`);
    hasFields(`line #${el && el.id}`, rows, [o.x, o.y, o.series, o.n]);
    if (o.seriesOrder) need(o.seriesOrder.length > 0, `line #${el && el.id}: empty seriesOrder`);
    calls.push(`line #${el && el.id} (${rows.length})`);
  },
  examples: (el, rows, o) => { hasFields('examples', rows, [typeof o.title === 'string' ? o.title : null, ...(o.meta || []), ...o.blocks.map((b) => b.field)]); calls.push('examples'); },
  table: (el, rows, o) => {
    const ds = load(o.source);
    need(ds != null, `table: source ${o.source} has no dataset`);
    hasFields(`table ${o.source}`, rows, o.columns.map((c) => c.field));
    const keys = o.key.split(',');
    hasFields(`table ${o.source} key`, rows, keys);
    for (const k of keys) need(o.columns.some((c) => c.field === k), `table ${o.source}: key column "${k}" not shown`);
    const seen = new Set(rows.map((r) => keys.map((k) => String(r[k])).join('\u0000')));
    need(seen.size === rows.length, `table ${o.source}: key "${o.key}" not unique (${seen.size} of ${rows.length})`);
    for (const r of rows.slice(0, 50)) for (const c of o.columns) if (c.fmt) c.fmt(r[c.field], r);
    calls.push(`table ${o.source} (${rows.length})`);
  },
  methods: (pageEl, id) => {
    const rows = load(id) || [];
    const charts = new Set(rows.map((r) => r.chart));
    for (const c of pageEl._methodCharts) need(charts.has(c), `method box "${c}" has no row in ${id}`);
    calls.push(`methods (${pageEl._methodCharts.length} boxes)`);
  },
};

// ---- run ----
const src = read(`${ROOT}/dashboard/agent3.js`);
(0, eval)(src);
const spec = RH._spec;
const page = mkEl('page');
spec.build(page);
const html = page.innerHTML;
const ids = new Map([...html.matchAll(/id="([^"$]+)"/g)].map((m) => [m[1], mkEl(m[1])]));
page.querySelector = (sel) => (sel.startsWith('#') ? ids.get(sel.slice(1)) || null : null);
page._methodCharts = [...html.matchAll(/data-chart="([^"]+)"/g)].map((m) => m[1]);
for (const m of html.matchAll(/data-source="([^"$]+)"/g)) {
  for (const id of m[1].split(' ')) need(load(id) != null, `markup data-source "${id}" has no dataset file`);
}
try {
  spec.draw(page);
} catch (e) {
  problems.push(`draw threw: ${e} ${e.stack || ''}`);
}
const out = [`${calls.length} kit calls:`, ...calls.map((c) => `  ${c}`), ...problems.map((p) => `PROBLEM ${p}`),
  problems.length ? 'FAILED' : 'OK'];
out.join('\n');
