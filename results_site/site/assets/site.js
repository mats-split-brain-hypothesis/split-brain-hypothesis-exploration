/* Real or Graded: shared shell, data loading and chart helpers. Every page loads d3 (cdnjs, 7.9.0) and then this file.
   Numbers never live in the markup: a value slot is <span class="v" data-ds="<dataset>" data-f="<field>"
   data-w="col=value&col=value">—</span>, filled from data/<dataset>.json; every figure names its datasets in a
   [data-src] line, which shows where they come from (notes file, section, commit). results_site/check.py checks both. */
(function () {
  "use strict";

  // Pages. ready:false shows as "soon" in the sidebar.
  const PAGES = [
    { file: "index.html", title: "Overview", group: "Project", ready: true },
    { file: "sorh.html", title: "School of Reward Hacks", group: "Results", ready: true },
    { file: "ib.html", title: "ImpossibleBench", group: "Results", ready: true },
    { file: "goodfire.html", title: "Goodfire's transcripts", group: "Results", ready: true },
    { file: "beliefs.html", title: "Beliefs and coding chats", group: "Results", ready: true },
    { file: "other.html", title: "Other datasets", group: "Results", ready: true },
    { file: "methods.html", title: "Methods and sources", group: "Reference", ready: true },
  ];
  const GROUPS = ["Project", "Results", "Reference"];

  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const store = { get(k) { try { return localStorage.getItem(k); } catch { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch { /* not kept */ } } };

  // ---------- theme ----------
  function applyTheme(t) {
    if (t === "light" || t === "dark") document.documentElement.dataset.theme = t;
    else delete document.documentElement.dataset.theme;
  }
  applyTheme(store.get("rg-theme"));

  // ---------- shell ----------
  function shell() {
    const host = document.querySelector("[data-page]");
    const here = (host && host.dataset.page) || "index.html";
    const aside = document.getElementById("nav");
    if (!aside) return;
    aside.className = "sidebar";
    const top = el("div"); top.style.cssText = "display:flex;justify-content:space-between;align-items:flex-start;gap:8px";
    const brand = el("a", "brand"); brand.href = "index.html";
    brand.append(el("span", "brand-name", "Real or Graded"), el("span", "brand-sub", "Results across four models"));
    const close = el("button", "nav-close", "Close"); close.type = "button"; close.addEventListener("click", () => aside.classList.remove("open"));
    top.append(brand, close);
    const nav = el("nav"); nav.setAttribute("aria-label", "Pages"); nav.style.cssText = "display:flex;flex-direction:column;gap:18px";
    for (const g of GROUPS) {
      const ps = PAGES.filter((p) => p.group === g);
      if (!ps.length) continue;
      const box = el("div", "nav-group");
      box.append(el("div", "nav-label", g));
      for (const p of ps) {
        if (p.ready) {
          const a = el("a", "nav-link" + (p.file === here ? " active" : ""), p.title); a.href = p.file;
          if (p.file === here) a.setAttribute("aria-current", "page");
          box.append(a);
        } else {
          const s = el("span", "nav-link disabled", p.title); s.title = "Being built"; s.append(el("span", "nav-soon", "soon"));
          box.append(s);
        }
      }
      nav.append(box);
    }
    const foot = el("div", "sidebar-foot");
    const tg = el("div", "theme-toggle"); tg.setAttribute("role", "group"); tg.setAttribute("aria-label", "Theme");
    const cur = store.get("rg-theme") || "system";
    for (const [k, label] of [["system", "System"], ["light", "Light"], ["dark", "Dark"]]) {
      const b = el("button", null, label); b.type = "button"; b.setAttribute("aria-pressed", String(k === cur));
      b.addEventListener("click", () => { store.set("rg-theme", k); applyTheme(k); tg.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", String(x === b))); });
      tg.append(b);
    }
    const built = el("span", null, "Data built —"); built.id = "built-at";
    foot.append(tg, built);
    aside.append(top, nav, foot);
    const bar = document.getElementById("mobile-bar");
    if (bar) {
      bar.className = "mobile-bar";
      const b = el("button", null, "Pages"); b.type = "button"; b.setAttribute("aria-label", "Open the list of pages");
      b.addEventListener("click", () => aside.classList.add("open"));
      bar.append(el("span", "brand-name", "Real or Graded"), b);
    }
  }

  // ---------- data ----------
  const cache = {};
  function load(ids) {
    const want = [...new Set(["manifest", ...ids])];
    return Promise.all(want.map((id) => cache[id] || (cache[id] = fetch(`data/${id}.json`).then((r) => {
      if (!r.ok) throw new Error(`data/${id}.json: ${r.status}`);
      return r.json();
    })))).then((arr) => {
      const D = {}; want.forEach((id, i) => { D[id] = arr[i]; });
      const b = document.getElementById("built-at");
      if (b && D.manifest) b.textContent = "Data built " + fmtDate(D.manifest.built_at);
      return D;
    });
  }
  function fmtDate(iso) {
    const d = new Date(iso);
    return d.toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "UTC" }) + " UTC";
  }
  const parseWhere = (s) => Object.fromEntries((s || "").split("&").filter(Boolean).map((p) => { const i = p.indexOf("="); return [p.slice(0, i), p.slice(i + 1)]; }));
  function row(D, id, where) {
    const rows = D[id] ? D[id].rows : [];
    return rows.find((r) => Object.entries(where).every(([k, v]) => String(r[k]) === v));
  }
  function fmt(v) {
    if (typeof v === "number") return Number.isInteger(v) ? v.toLocaleString("en-US") : String(v);
    return v == null ? "—" : String(v);
  }
  function fill(root, D) {
    root.querySelectorAll("[data-ds][data-f]").forEach((e) => {
      const r = row(D, e.dataset.ds, parseWhere(e.dataset.w));
      e.textContent = r ? fmt(r[e.dataset.f]) : "—";
      e.classList.remove("loading");
    });
  }
  function sources(root, D) {
    root.querySelectorAll("[data-src]").forEach((box) => {
      const seen = new Map();
      for (const id of box.dataset.src.split(/\s+/)) {
        const d = D[id]; if (!d) continue;
        const add = (s) => { if (!s) return; const k = `${s.path}@${s.commit}#${s.section || ""}`; if (!seen.has(k)) seen.set(k, s); };
        add(d.source); (d.rows || []).forEach((r) => { add(r._src); (r._srcs || []).forEach(add); });
      }
      box.replaceChildren(el("span", "src-label", "Source"));
      [...seen.values()].forEach((s, i) => {
        const span = el("span");
        span.append(el("span", "mono", s.path), document.createTextNode(s.section ? ` › ${s.section.replace(/\s*\($/, "")}` : ""),
          document.createTextNode(" · commit "), el("span", "mono", s.commit));
        if (i) span.prepend(document.createTextNode("· "));
        box.append(span);
      });
    });
  }

  // ---------- tooltip ----------
  let tipEl = null;
  function tipShow(x, y, title, lines) {
    if (!tipEl) { tipEl = el("div", "tooltip"); tipEl.setAttribute("role", "status"); document.body.append(tipEl); }
    tipEl.replaceChildren();
    if (title) tipEl.append(el("div", "tooltip-title", title));
    for (const ln of lines || []) {
      if (Array.isArray(ln)) { const r = el("div", "tooltip-row"); r.append(el("span", null, ln[0]), el("b", null, ln[1])); tipEl.append(r); }
      else tipEl.append(el("div", "tooltip-text", ln));
    }
    tipEl.hidden = false;
    const w = tipEl.offsetWidth, h = tipEl.offsetHeight;
    tipEl.style.left = Math.max(8, Math.min(x + 14, window.innerWidth - w - 8)) + "px";
    tipEl.style.top = (y + 16 + h > window.innerHeight ? Math.max(8, y - h - 12) : y + 16) + "px";
  }
  function tipHide() { if (tipEl) tipEl.hidden = true; }
  function bindTip(node, title, lines) {
    node.setAttribute("tabindex", "0");
    node.addEventListener("mousemove", (e) => tipShow(e.clientX, e.clientY, title, typeof lines === "function" ? lines() : lines));
    node.addEventListener("mouseleave", tipHide);
    node.addEventListener("focus", () => { const r = node.getBoundingClientRect(); tipShow(r.left + r.width / 2, r.bottom, title, typeof lines === "function" ? lines() : lines); });
    node.addEventListener("blur", tipHide);
  }
  window.addEventListener("scroll", tipHide, { passive: true });

  // ---------- chart / table toggle ----------
  function tableView(fig, columns, rows) {
    // fig: a .figure with a .fig-chart child; adds a toggle and a table built from rows.
    const chart = fig.querySelector(".fig-chart");
    let tools = fig.querySelector(".fig-tools-auto");
    if (!tools) {
      tools = el("div", "fig-tools fig-tools-auto");
      const tg = el("div", "view-toggle"); tg.setAttribute("role", "group"); tg.setAttribute("aria-label", "View");
      const bC = el("button", null, "Chart"), bT = el("button", null, "Table"); bC.type = bT.type = "button";
      bC.setAttribute("aria-pressed", "true"); bT.setAttribute("aria-pressed", "false");
      tg.append(bC, bT); tools.append(el("span"), tg);
      fig.prepend(tools);
      const wrap = el("div", "table-wrap fig-table"); wrap.hidden = true; chart.after(wrap);
      bC.addEventListener("click", () => { bC.setAttribute("aria-pressed", "true"); bT.setAttribute("aria-pressed", "false"); chart.hidden = false; wrap.hidden = true; });
      bT.addEventListener("click", () => { bT.setAttribute("aria-pressed", "true"); bC.setAttribute("aria-pressed", "false"); chart.hidden = true; wrap.hidden = false; });
    }
    const wrap = fig.querySelector(".fig-table");
    const t = el("table", "table"); const thead = el("thead"); const tr = el("tr");
    columns.forEach((c) => { const th = el("th", c.num ? "num" : null, c.label); tr.append(th); });
    thead.append(tr); t.append(thead);
    const tb = el("tbody");
    rows.forEach((r) => { const tr2 = el("tr"); columns.forEach((c) => tr2.append(el("td", c.num ? "num" : null, fmt(typeof c.get === "function" ? c.get(r) : r[c.key])))); tb.append(tr2); });
    t.append(tb); wrap.replaceChildren(t);
  }

  // ---------- redraw on resize ----------
  const drawers = [];
  function onResize(fn) { drawers.push(fn); }
  let rt = null;
  window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => drawers.forEach((f) => f()), 120); });

  function newSvg(box, H, W) {
    box.querySelectorAll(":scope > svg").forEach((s) => s.remove());
    const svg = d3.select(box).append("svg").attr("class", "chart").attr("viewBox", `0 0 ${W} ${H}`).attr("width", "100%").attr("role", "img");
    return svg;
  }
  const pct = (v, d = 1) => (v * 100).toFixed(d).replace(/\.0+$/, "") + "%";
  function measure(svg, cls, strings) {
    const t = svg.append("text").attr("class", cls).style("font-size", "12px");
    let w = 0; strings.forEach((s) => { t.text(s); w = Math.max(w, t.node().getComputedTextLength()); });
    t.remove(); return w;
  }

  // Small multiples, one panel per model: bars of k/n by bin (rejections seen, conditions...).
  // o: {panels:[{title, rows:[{bin, k, n}]}], bins, color, minN, ymax, label(bin)->str, tipTitle(panel,row), tipLine(row), axis}
  function binPanels(wrap, o) {
    const draw = () => {
      wrap.classList.add("panels");
      wrap.replaceChildren(...o.panels.map((p) => { const d = el("div"); d.append(el("div", "panel-t", p.title), el("div", "fig-panel")); return d; }));
      const share = (r) => (r.n ? r.k / r.n : 0);
      const ymax = o.ymax || d3.max(o.panels.flatMap((p) => p.rows.filter((r) => r.n >= o.minN)), share) || 0.01;
      const tickFmt = ymax < 0.05 ? (v) => pct(v, 1) : (v) => pct(v, 0);
      o.panels.forEach((p, i) => {
        const box = wrap.children[i].querySelector(".fig-panel");
        const W = Math.max(220, box.clientWidth || 260), H = 190, left = 40, bottom = H - 36, top = 22;
        const svg = newSvg(box, H, W).attr("aria-label", `${p.title}: ${o.axis || ""}`);
        const x = d3.scaleBand().domain(o.bins).range([left, W - 4]).padding(0.26);
        const y = d3.scaleLinear().domain([0, ymax]).nice().range([bottom, top]);
        y.ticks(3).forEach((t) => {
          svg.append("line").attr("class", "grid-line").attr("x1", left).attr("x2", W - 4).attr("y1", y(t)).attr("y2", y(t));
          svg.append("text").attr("class", "t-muted").attr("x", left - 6).attr("y", y(t)).attr("dy", "0.35em").attr("text-anchor", "end").style("font-size", "11px").text(tickFmt(t));
        });
        svg.append("line").attr("class", "axis-line").attr("x1", left).attr("x2", W - 4).attr("y1", bottom).attr("y2", bottom);
        o.bins.forEach((b) => svg.append("text").attr("class", "t-muted").attr("x", x(b) + x.bandwidth() / 2).attr("y", bottom + 15).attr("text-anchor", "middle").style("font-size", "11.5px").text(o.label ? o.label(b) : b));
        if (o.axis) svg.append("text").attr("class", "t-muted").attr("x", (left + W) / 2).attr("y", bottom + 31).attr("text-anchor", "middle").style("font-size", "11px").text(o.axis);
        p.rows.forEach((r) => {
          const bx = x(r.bin), bw = x.bandwidth(), v = share(r);
          if (bx == null) return;
          if (r.n < o.minN) {
            svg.append("text").attr("class", "t-muted").attr("x", bx + bw / 2).attr("y", bottom - 6).attr("text-anchor", "middle").style("font-size", "11px").text(`${r.k}/${r.n}`);
          } else {
            const h = Math.max(1.5, bottom - y(v));
            svg.append("path").attr("d", roundTop(bx, bottom - h, bw, h, 4)).style("fill", o.color);
            svg.append("text").attr("x", bx + bw / 2).attr("y", bottom - h - 6).attr("text-anchor", "middle").style("font-size", "11.5px").style("font-variant-numeric", "tabular-nums").text(pct(v, 1));
          }
          const hit = svg.append("rect").attr("class", "hit").attr("x", bx - 4).attr("y", top).attr("width", bw + 8).attr("height", bottom - top).node();
          bindTip(hit, o.tipTitle ? o.tipTitle(p, r) : p.title, () => [o.tipLine ? o.tipLine(r) : `${r.k} of ${r.n}`,
            r.n < o.minN ? "Too few turns left to show a share" : ["Share", pct(v, 1)]]);
        });
      });
    };
    draw(); onResize(draw);
  }
  function roundTop(x, y, w, h, r) {
    r = Math.min(r, w / 2, h);
    return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
  }

  // Dot and 95% interval on a linear scale. rows: {group, label, color, ratio, lo, hi, highlight, tipTitle, tipLines}
  function forest(box, rows, o) {
    const draw = () => {
      const W = Math.max(300, box.clientWidth || 600);
      const rowH = 26, gGap = 10, top = 8, axisH = 40;
      const groups = [...new Set(rows.map((r) => r.group))];
      const probe = newSvg(box, 10, W);
      const labW = Math.min(measure(probe, "", groups) + 16, W * 0.38);
      const subW = rows.some((r) => r.label) ? Math.min(measure(probe, "", rows.map((r) => r.label || "")) + 12, W * 0.26) : 0;
      const valW = measure(probe, "", rows.map((r) => fmtRatio(r.ratio))) + 12;
      const x = d3.scaleLinear().domain(o.domain).range([labW + subW, W - valW - 6]).clamp(true);
      let y = top; const placed = [];
      groups.forEach((g) => {
        const rs = rows.filter((r) => r.group === g);
        placed.push({ label: g, y: y + (rs.length * rowH) / 2 });
        rs.forEach((r) => { placed.push({ r, y: y + rowH / 2 }); y += rowH; });
        y += gGap;
      });
      const bottom = y - gGap + 4, H = bottom + axisH;
      const svg = newSvg(box, H, W).attr("aria-label", o.axisLabel || "Ratios with intervals");
      placed.filter((p) => p.r && p.r.highlight).forEach((p) => svg.append("rect").attr("class", "hl").attr("x", labW - 4).attr("y", p.y - rowH / 2 + 1).attr("width", W - labW + 4).attr("height", rowH - 2).attr("rx", 5));
      o.ticks.forEach((t) => {
        svg.append("line").attr("class", t === o.ref ? "ref-line" : "grid-line").attr("x1", x(t)).attr("x2", x(t)).attr("y1", top - 4).attr("y2", bottom);
        svg.append("text").attr("class", "t-muted").attr("x", x(t)).attr("y", bottom + 15).attr("text-anchor", "middle").style("font-size", "11px").text(t + "×");
      });
      svg.append("text").attr("class", "t-muted").attr("x", (x.range()[0] + x.range()[1]) / 2).attr("y", bottom + 32).attr("text-anchor", "middle").style("font-size", "11.5px").text(o.axisLabel);
      placed.filter((p) => p.label).forEach((p) => svg.append("text").attr("x", 2).attr("y", p.y).attr("dy", "0.35em").style("font-size", "12.5px").style("font-weight", "550").text(p.label));
      placed.filter((p) => p.r).forEach((p) => {
        const r = p.r;
        if (r.label) svg.append("text").attr("class", "t-secondary").attr("x", labW).attr("y", p.y).attr("dy", "0.35em").style("font-size", "12px").text(r.label);
        if (r.ratio == null) { svg.append("text").attr("class", "t-muted").attr("x", x.range()[0] + 4).attr("y", p.y).attr("dy", "0.35em").style("font-size", "11.5px").text("no events"); return; }
        const lo = r.lo == null ? o.domain[0] : r.lo, hi = r.hi == null ? o.domain[1] : r.hi;
        svg.append("line").attr("x1", x(lo)).attr("x2", x(hi)).attr("y1", p.y).attr("y2", p.y).style("stroke", r.color).attr("stroke-width", 2).attr("stroke-linecap", "round");
        if (hi > o.domain[1]) svg.append("path").attr("d", `M${x(o.domain[1])},${p.y - 4}l6,4l-6,4z`).style("fill", r.color);
        svg.append("circle").attr("cx", x(r.ratio)).attr("cy", p.y).attr("r", 5).style("fill", r.color).style("stroke", "var(--surface-1)").attr("stroke-width", 2);
        svg.append("text").attr("x", Math.min(x(hi), x.range()[1]) + 8).attr("y", p.y).attr("dy", "0.35em").style("font-size", "11.5px").style("font-variant-numeric", "tabular-nums").text(fmtRatio(r.ratio));
        const hit = svg.append("rect").attr("class", "hit").attr("x", 0).attr("y", p.y - rowH / 2).attr("width", W).attr("height", rowH).node();
        bindTip(hit, r.tipTitle, r.tipLines);
      });
    };
    draw(); onResize(draw);
  }
  const fmtRatio = (v) => (v == null ? "—" : v + "×");

  // 100% stacked horizontal bars. rows: {label, total, parts:[{value, color, name}], tipTitle, tipLines}; o.titles {index: title}
  function stack100(box, rows, o = {}) {
    const draw = () => {
      const W = Math.max(300, box.clientWidth || 600);
      const barH = 22, gap = 12, top = 4, titleH = 24;
      const titles = o.titles || {};
      const probe = newSvg(box, 10, W);
      const labW = Math.min(measure(probe, "", rows.map((r) => r.label)) + 16, W * 0.42);
      const x = d3.scaleLinear().domain([0, 1]).range([labW, W - 4]);
      const H = top + rows.length * (barH + gap) + Object.keys(titles).length * titleH + 20;
      const svg = newSvg(box, H, W).attr("aria-label", o.aria || "Shares");
      [0, 0.5, 1].forEach((t) => {
        svg.append("line").attr("class", "grid-line").attr("x1", x(t)).attr("x2", x(t)).attr("y1", top).attr("y2", H - 20);
        svg.append("text").attr("class", "t-muted").attr("x", x(t)).attr("y", H - 4).attr("text-anchor", t === 0 ? "start" : t === 1 ? "end" : "middle").style("font-size", "11px").text(pct(t, 0));
      });
      let y = top;
      rows.forEach((r, i) => {
        if (titles[i] != null) { svg.append("text").attr("x", 2).attr("y", y + 15).style("font-size", "12px").style("font-weight", "600").text(titles[i]); y += titleH; }
        svg.append("text").attr("class", "t-secondary").attr("x", 2).attr("y", y + barH / 2).attr("dy", "0.35em").style("font-size", "12.5px").text(r.label);
        let acc = 0;
        r.parts.forEach((part) => {
          const f = r.total ? part.value / r.total : 0;
          const x0 = x(acc), x1 = x(acc + f);
          if (x1 - x0 > 0.5) {
            svg.append("rect").attr("x", x0 + (acc > 0 ? 1 : 0)).attr("y", y).attr("width", Math.max(0, x1 - x0 - (acc > 0 ? 1 : 0))).attr("height", barH).attr("rx", 3).style("fill", part.color);
            const lab = String(part.value);
            if (x1 - x0 > lab.length * 7 + 10) svg.append("text").attr("x", (x0 + x1) / 2).attr("y", y + barH / 2).attr("dy", "0.35em").attr("text-anchor", "middle").style("font-size", "11.5px").style("fill", part.ink || "var(--surface-1)").style("font-variant-numeric", "tabular-nums").text(lab);
          }
          acc += f;
        });
        const hit = svg.append("rect").attr("class", "hit").attr("x", 0).attr("y", y - gap / 2).attr("width", W).attr("height", barH + gap).node();
        bindTip(hit, r.tipTitle || r.label, r.tipLines || r.parts.map((p) => [p.name, `${p.value} of ${r.total}`]));
        y += barH + gap;
      });
    };
    draw(); onResize(draw);
  }

  // Share bars, grouped: groups {label, bars:[{name, k, n, color}]}
  function shareBars(box, groups, o = {}) {
    const draw = () => {
      const W = Math.max(300, box.clientWidth || 600);
      const barH = 13, inner = 4, gap = 16, top = 4;
      const probe = newSvg(box, 10, W);
      const labW = Math.min(measure(probe, "", groups.map((g) => g.label)) + 16, W * 0.34);
      const valW = measure(probe, "", groups.flatMap((g) => g.bars.map((b) => `${fmt(b.k)} of ${fmt(b.n)}`))) + 12;
      const x = d3.scaleLinear().domain([0, 1]).range([labW, W - valW]);
      const H = top + groups.reduce((s, g) => s + g.bars.length * (barH + inner) + gap, 0) + 20;
      const svg = newSvg(box, H, W).attr("aria-label", o.aria || "Shares");
      [0, 0.5, 1].forEach((t) => {
        svg.append("line").attr("class", "grid-line").attr("x1", x(t)).attr("x2", x(t)).attr("y1", top).attr("y2", H - 20);
        svg.append("text").attr("class", "t-muted").attr("x", x(t)).attr("y", H - 4).attr("text-anchor", t === 0 ? "start" : "middle").style("font-size", "11px").text(pct(t, 0));
      });
      let y = top;
      groups.forEach((g) => {
        const gh = g.bars.length * (barH + inner) - inner;
        svg.append("text").attr("x", 2).attr("y", y + gh / 2).attr("dy", "0.35em").style("font-size", "12.5px").text(g.label);
        g.bars.forEach((b) => {
          const f = b.n ? b.k / b.n : 0;
          svg.append("rect").attr("x", x(0)).attr("y", y).attr("width", Math.max(f > 0 ? 2 : 0, x(f) - x(0))).attr("height", barH).attr("rx", 3).style("fill", b.color);
          svg.append("text").attr("class", "t-secondary").attr("x", x(f) + 6).attr("y", y + barH / 2).attr("dy", "0.35em").style("font-size", "11.5px").style("font-variant-numeric", "tabular-nums").text(`${fmt(b.k)} of ${fmt(b.n)}`);
          const hit = svg.append("rect").attr("class", "hit").attr("x", 0).attr("y", y - inner / 2).attr("width", W).attr("height", barH + inner).node();
          bindTip(hit, `${g.label} · ${b.name}`, [[b.name, `${fmt(b.k)} of ${fmt(b.n)}`], ["Share", pct(f, 1)]]);
          y += barH + inner;
        });
        y += gap - inner;
      });
    };
    draw(); onResize(draw);
  }

  // Horizontal share bars with k/n labels. rows {label, k, n, color, tipTitle, tipLines}; o {ref: share for a dashed line, refLabel}
  function hbars(box, rows, o = {}) {
    const draw = () => {
      box.querySelectorAll(":scope > svg").forEach((s) => s.remove());
      const W = Math.max(300, box.clientWidth || 600), barH = 18, gap = 10, top = o.ref != null ? 18 : 4;
      const probe = newSvg(box, 10, W);
      const labW = Math.min(measure(probe, "", rows.map((r) => r.label)) + 16, W * 0.5);
      const valW = measure(probe, "", rows.map((r) => `${r.k}/${r.n}`)) + 12;
      probe.remove();
      const x = d3.scaleLinear().domain([0, 1]).range([labW, W - valW]);
      const H = top + rows.length * (barH + gap) + 20;
      const svg = newSvg(box, H, W).attr("aria-label", o.aria || "Shares");
      [0, 0.5, 1].forEach((t) => {
        svg.append("line").attr("class", "grid-line").attr("x1", x(t)).attr("x2", x(t)).attr("y1", top - 4).attr("y2", H - 20);
        svg.append("text").attr("class", "t-muted").attr("x", x(t)).attr("y", H - 4).attr("text-anchor", t === 0 ? "start" : t === 1 ? "end" : "middle").style("font-size", "11px").text(pct(t, 0));
      });
      if (o.ref != null) {
        svg.append("line").attr("class", "ref-line").attr("x1", x(o.ref)).attr("x2", x(o.ref)).attr("y1", top - 6).attr("y2", H - 20);
        svg.append("text").attr("class", "t-muted").attr("x", x(o.ref) + 4).attr("y", top - 6).style("font-size", "11px").text(o.refLabel || "");
      }
      rows.forEach((r, i) => {
        const y = top + i * (barH + gap), f = r.n ? r.k / r.n : 0;
        svg.append("text").attr("class", "t-secondary").attr("x", 2).attr("y", y + barH / 2).attr("dy", "0.35em").style("font-size", "12.5px").text(r.label);
        svg.append("rect").attr("x", x(0)).attr("y", y).attr("width", Math.max(f > 0 ? 2 : 0, x(f) - x(0))).attr("height", barH).attr("rx", 3).style("fill", r.color);
        svg.append("text").attr("x", x(f) + 6).attr("y", y + barH / 2).attr("dy", "0.35em").style("font-size", "11.5px").style("font-variant-numeric", "tabular-nums").text(`${r.k}/${r.n}`);
        const hit = svg.append("rect").attr("class", "hit").attr("x", 0).attr("y", y - gap / 2).attr("width", W).attr("height", barH + gap).node();
        bindTip(hit, r.tipTitle || r.label, r.tipLines || [[`${r.k} of ${r.n}`, pct(f, 1)]]);
      });
    };
    draw(); onResize(draw);
  }

  // Quote cards: rows {title, text, model, bench, context, source, note, cut}
  function quotes(box, rows, tone) {
    box.classList.add("quotes");
    box.replaceChildren(...rows.map((r) => {
      const f = el("figure", "quote " + (typeof tone === "function" ? tone(r) : tone || ""));
      const q = el("blockquote", null, `“${r.text}${r.cut ? " …" : ""}”`);
      const c = el("figcaption", null, `${r.model} · ${r.bench}${r.context ? " · " + r.context : ""}. ${r.source}.${r.note ? " " + r.note : ""}`);
      f.append(el("div", "quote-t", r.title), q, c); return f;
    }));
  }

  window.RG = { PAGES, shell, load, fill, sources, row, fmt, pct, el, bindTip, tipShow, tipHide, tableView, binPanels, forest, stack100, shareBars, hbars, quotes, onResize, fmtRatio };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", shell); else shell();
})();
