/* Findings-style helpers for the SoRH and IB pages (agent 9). Needs site.js (RG) and d3. Everything drawn here comes
   from the datasets the page loads: grids from per-model rows, example cards and quote chains from the examples
   datasets (each quote checked against its record by results_site/check_quotes.py). */
(function () {
  "use strict";
  const { el, bindTip, tableView, onResize } = RG;
  const MODELS = ["Qwen 3.8 2.4T", "DeepSeek V4 Pro", "GLM 5.2", "Qwen 3.8 27B"];
  const SHORT = ["Qwen 2.4T", "DeepSeek", "GLM", "Qwen 27B"];
  const COL = { control: "var(--control)", graded: "var(--graded)", real: "var(--real)" };

  // Versions × models: each version's label on its own line, then one bar per model in four columns.
  function grid(box, rows, o = {}) {
    const draw = () => {
      box.querySelectorAll(":scope > svg").forEach((s) => s.remove());
      const W = Math.max(300, box.clientWidth || 640);
      const names = W < 560 ? SHORT : MODELS;
      const headH = 26, labH = 24, cellH = 28, gap = 12, groupH = 28, colW = W / 4;
      let H = headH; let g = null;
      rows.forEach((r) => { if (r.group && r.group !== g) { g = r.group; H += groupH; } H += labH + cellH + gap; });
      const svg = d3.select(box).append("svg").attr("class", "chart").attr("viewBox", `0 0 ${W} ${H}`).attr("width", "100%")
        .attr("role", "img").attr("aria-label", o.aria || "Values by version and model");
      names.forEach((n, i) => svg.append("text").attr("x", i * colW).attr("y", 14).style("font-size", "12px").style("font-weight", "600").text(n));
      let y = headH; g = null;
      rows.forEach((r) => {
        if (r.group && r.group !== g) {
          g = r.group;
          svg.append("text").attr("class", "t-muted").attr("x", 0).attr("y", y + 18).style("font-size", "11.5px").style("font-weight", "600")
            .style("text-transform", "uppercase").style("letter-spacing", "0.04em").text(r.group);
          y += groupH;
        }
        svg.append("text").attr("x", 0).attr("y", y + 14).style("font-size", "13px").text(r.label);
        r.cells.forEach((c, i) => {
          const x = i * colW, tw = colW - 18, by = y + labH + 17;
          svg.append("text").attr("class", c.na ? "t-muted" : null).attr("x", x).attr("y", y + labH + 12).style("font-size", "12px")
            .style("font-weight", c.na ? "400" : "600").style("font-variant-numeric", "tabular-nums").text(c.t);
          if (c.na) return;
          svg.append("rect").attr("x", x).attr("y", by).attr("width", tw).attr("height", 8).attr("rx", 4).style("fill", "var(--surface-sunken)");
          if (c.frac > 0) svg.append("rect").attr("x", x).attr("y", by).attr("width", Math.max(3, tw * Math.min(1, c.frac))).attr("height", 8)
            .attr("rx", 4).style("fill", COL[c.kind || r.kind] || "var(--control)");
          const hit = svg.append("rect").attr("class", "hit").attr("x", x - 2).attr("y", y + labH - 6).attr("width", colW - 4).attr("height", cellH + 6).node();
          bindTip(hit, `${r.label} · ${MODELS[i]}`, c.tip || []);
        });
        y += labH + cellH + gap;
      });
    };
    draw(); onResize(draw);
  }
  // Rows (one per version × model) into grid rows, in dataset order.
  function pivot(rows, key, cellOf, keep) {
    const out = [];
    rows.filter(keep || (() => true)).slice().sort((a, b) => (a.order ?? 0) - (b.order ?? 0) || a.mi - b.mi).forEach((r) => {
      let v = out.find((x) => x.key === r[key]);
      if (!v) { v = { key: r[key], label: r.label, group: r.group || "", kind: r.kind, cells: [] }; out.push(v); }
      v.cells[r.mi] = cellOf(r);
    });
    return out;
  }
  const NA = { t: "—", na: true, frac: 0 };
  function knCell(r, what) {
    const tip = [[what || "Padded", `${r.k} of ${r.n}`]];
    if (r.old && r.old !== `${r.k}/${r.n}`) tip.push(["Old judge (whole reply)", r.old.replace("/", " of ")]);
    if (r.redrawn) tip.push("† re-drawn: a reply cut while reasoning or lost to provider errors is now a second draw");
    return { t: r.t || `${r.k}/${r.n}`, frac: r.n ? r.k / r.n : 0, tip };
  }
  function gridTable(fig, rows, first) {
    tableView(fig, [{ label: first || "Version", get: (r) => (r.group ? r.group + ": " : "") + r.label }]
      .concat(MODELS.map((m, i) => ({ label: m, get: (r) => (r.cells[i] ? r.cells[i].t : "—") }))), rows);
  }
  const range = (xs) => { const a = Math.min(...xs), b = Math.max(...xs); return a === b ? `${a}` : `${a}–${b}`; };
  const list = (xs) => (xs.length < 2 ? String(xs[0] ?? "") : xs.slice(0, -1).join(", ") + " and " + xs[xs.length - 1]);

  // Examples.
  let EX = {};
  function useExamples(rows) { EX = Object.fromEntries(rows.map((r) => [r.id, r])); }
  const ex = (id) => { if (!EX[id]) throw new Error("example missing: " + id); return EX[id]; };
  // The model's own markdown inside a quote: **bold** shown bold, `code` as code. The text itself is unchanged.
  function md(text) {
    const f = document.createDocumentFragment();
    String(text).split(/(\*\*[^*]+\*\*|`[^`]+`)/).forEach((p) => {
      if (/^\*\*[^*]+\*\*$/.test(p)) f.append(el("b", null, p.slice(2, -2)));
      else if (/^`[^`]+`$/.test(p)) f.append(el("code", null, p.slice(1, -1)));
      else if (p) f.append(document.createTextNode(p));
    });
    return f;
  }
  const quoted = (cls, text) => { const b = el("blockquote", cls); b.append("“", md(text), "”"); return b; };
  function meta(r, extra) {
    const m = el("div", "ex-meta");
    const who = r.model === "all" ? "" : r.model;
    const what = [who, r.prompt || r.task || "", r.cell || r.arm || ""].filter(Boolean).join(" · ");
    m.append(el("span", null, what));
    if (extra) m.append(el("span", null, extra));
    const w = el("span", "mono", r.where); m.append(w);
    bindTip(m, "Source", [r.how, "Checked verbatim against the record (whitespace collapsed; … marks a cut)."]);
    return m;
  }
  function flag(r) {
    if (r.padded_v2 === true || r.padded_label === "padded") return el("span", "ex-flag yes", "padded");
    if (r.padded_v2 === false || r.padded_label === "not padded") return el("span", "ex-flag no", "not padded");
    return null;
  }
  // A side of a contrast: tag, the request (with an optional highlighted part), the reply, the padded flag, the source.
  function exCard(o) {
    const c = el("figure", "ex-card " + (o.tone || ""));
    c.append(el("div", "ex-tag", o.tag));
    if (o.request) {
      const q = el("div", "ex-req"); q.append(el("b", null, "Request: "));
      const text = o.request.quote; const hl = o.highlight;
      if (hl && text.includes(hl)) { const i = text.indexOf(hl); q.append(document.createTextNode(text.slice(0, i)), el("mark", null, hl), document.createTextNode(text.slice(i + hl.length))); }
      else q.append(document.createTextNode(text));
      c.append(q);
    }
    (o.items || []).forEach((it) => {
      if (it.code) c.append(el("pre", "ex-code", it.row.quote));
      else if (it.label) { const d = el("div", "ex-req"); d.append(el("b", null, it.label + ": "), document.createTextNode(it.row.quote)); c.append(d); }
      else { if (it.cap) c.append(el("div", "ex-cap", it.cap)); c.append(quoted("ex-reply" + (it.think ? " think" : ""), it.row.quote)); }
    });
    const last = (o.items || [])[(o.items || []).length - 1];
    if (last && last.row) {
      const f = flag(last.row);
      const m = meta(last.row, o.metaExtra);
      if (f) m.prepend(f);
      c.append(m);
    }
    if (o.then) { const t = el("div", "fd-then"); t.append(el("b", null, "Then: "), document.createTextNode(o.then)); c.append(t); }
    return c;
  }
  function quoteCard(r, tone, note) {
    const c = el("figure", "fd-quote " + (tone || ""));
    c.append(quoted(null, r.quote));
    c.append(meta(r, note));
    return c;
  }
  function chain(box, rows, tones, then) {
    const wrap = el("div", "fd-chain" + (rows.length === 2 ? " n2" : ""));
    rows.forEach((r, i) => { if (i) wrap.append(el("span", "fd-arrow", "→")); wrap.append(quoteCard(r, (tones || [])[i])); });
    box.append(wrap);
    if (then) { const t = el("p", "fd-then"); t.append(el("b", null, "Then: "), document.createTextNode(then)); box.append(t); }
  }
  function table(box, head, rows, hl, text) {
    const t = el("table", "fd-table"), th = el("thead"), hr = el("tr"), cls = (i) => (i && !text ? "num" : null);
    head.forEach((h, i) => hr.append(el("th", cls(i), h))); th.append(hr); t.append(th);
    const tb = el("tbody");
    rows.forEach((r, j) => { const tr = el("tr", (hl || []).includes(j) ? "fd-hl" : null); r.forEach((v, i) => tr.append(el("td", cls(i), v))); tb.append(tr); });
    t.append(tb); box.replaceChildren(t);
  }

  // Verdict chips, as on the Overview, for "Where this fits".
  const GLYPH = { supports: "▲", against: "▼", "can't tell": "?", "fits pursuit": "◆", mixed: "◐", consistent: "△", agrees: "▲", "partly agrees": "△", complements: "◆", contradicts: "▼", "can't compare": "·", "not tested": "·", pending: "…" };
  const CLS = { supports: "supports", against: "against", "fits pursuit": "fits", consistent: "complements", agrees: "agrees", "partly agrees": "complements", contradicts: "contradicts", complements: "complements", pending: "pending" };
  function chip(verdict, label, qual) {
    const c = el("span", "vchip " + (CLS[verdict] || "") + (qual ? " qual" : ""));
    c.append(el("span", "g", GLYPH[verdict] || "·"), document.createTextNode(label ? `${label} ${verdict}` : verdict));
    if (qual) bindTip(c, label ? `${label}: ${verdict}` : verdict, [qual]);
    return c;
  }
  function fits(keyBox, listBox, D, benches) {
    keyBox.append(el("span", "lab", "Key:"));
    ["supports", "against", "fits pursuit", "consistent", "mixed", "can't tell"].forEach((v) => keyBox.append(chip(v)));
    keyBox.append(el("span", "lab", "* qualified (hover)"));
    const P = D.pending_runs.rows;
    const pendFor = (sec) => P.filter((p) => !p.done && (p.affects || []).some((a) => a === sec || a === "IB " + sec));
    const ORDER = ["1a", "1b", "2", "3", "4"];
    listBox.replaceChildren(...D.claims_map.rows.filter((r) => benches.includes(r.bench)).map((r) => {
      const row = el("div", "fit-row");
      const left = el("div"); left.append(el("b", null, r.bench === "Tests" ? "Test " + r.short : r.section));
      const runs = pendFor(r.section);
      if (r.pending || runs.length) { const pl = el("span", "pill pending", "pending"); pl.style.marginLeft = "8px"; bindTip(pl, "Pending", runs.length ? runs.flatMap((p) => [p.what, p.status]) : [r.status]); left.append(pl); }
      const right = el("div"); right.style.display = "grid"; right.style.gap = "6px";
      const subs = el("div", "chips"); subs.append(el("span", "lab", "Subclaims"));
      const sv = Object.entries(r.sub_verdicts).sort((a, b) => ORDER.indexOf(a[0]) - ORDER.indexOf(b[0]));
      if (sv.length) sv.forEach(([s, v]) => subs.append(chip(v.verdict, s, v.qual)));
      else subs.append(el("span", "muted", r.subclaims + (/^Descriptive/.test(r.shows) ? ", descriptive" : "")));
      const ants = el("div", "chips"); ants.append(el("span", "lab", "Anthony"));
      const av = Object.entries(r.anthony_verdicts).sort((a, b) => Number(a[0]) - Number(b[0]));
      av.forEach(([a, v]) => ants.append(chip(v.verdict, `(${a})`, v.qual)));
      if (!av.length) ants.append(el("span", "muted", "no direct match"));
      right.append(subs, ants); row.append(left, right); return row;
    }));
  }

  window.FD = { MODELS, SHORT, COL, NA, grid, pivot, knCell, gridTable, range, list, useExamples, ex, exCard, quoteCard, chain, table, chip, fits };
})();
