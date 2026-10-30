// Shared page registry and chart kit for the "Reward Hacking Triggers" dashboard.
// Every agent page calls RH.page(id, {build(el), draw(el)}); see dashboard/README.md.
(() => {
  const RH = (window.RH = {});
  const pages = new Map();
  let shown = null;
  const root = () => document.getElementById('dash-root') || document.body;

  // ---- pages ------------------------------------------------------------------------------------------------
  // build(el) runs once, the first time the page is shown: write the page's HTML (with data-source marks) there.
  // draw(el) runs whenever data or the width changes while the page is visible: read datasets and draw.
  RH.page = (id, spec) => {
    pages.set(id, { spec, built: false });
    if (id === shown) RH.redraw();
  };
  RH.show = (id) => {
    shown = id;
    RH.redraw();
  };
  RH.redraw = () => {
    const p = pages.get(shown);
    const el = shown && document.getElementById(shown);
    if (!p || !el || el.hidden) return;
    if (!p.built) {
      el.replaceChildren();
      p.spec.build?.(el);
      el.append(askBox(shown));
      p.built = true;
    }
    p.spec.draw?.(el);
  };
  // The box at the end of every tab: how to ask a question or request a change (the dashboard's own comments).
  const askBox = (id) => {
    const tab = document.getElementById(`tab-${id}`);
    const n = tab?.querySelector('.rh-tab-n')?.textContent;
    const box = document.createElement('section');
    box.className = 'rh-card rh-wide rh-ask';
    box.id = `${id}-ask`;
    const h = document.createElement('h3');
    h.textContent = 'Ask a question or request a change';
    const p = document.createElement('p');
    p.textContent = `Comment on any chart, number or on this box, then choose Send to Claude (or mention @claude). The orchestrator receives it, passes it to ${n ? `agent ${n}, who owns this tab` : 'the right agent'}, and replies in the same thread when it's done.`;
    box.append(h, p);
    return box;
  };
  // A page with no results yet.
  RH.placeholder = (who, question) => ({
    build(el) {
      const box = document.createElement('div');
      box.className = 'rh-intro';
      const h = document.createElement('h2');
      h.textContent = question;
      const p = document.createElement('p');
      p.textContent = `${who} hasn't published results here yet.`;
      box.append(h, p);
      el.append(box);
    },
  });

  // ---- formats and numbers ----------------------------------------------------------------------------------
  RH.pct = d3.format('.0%');
  RH.pct1 = d3.format('.1%');
  RH.int = d3.format(',');
  RH.num = d3.format(',.2~f');
  RH.usd = (v) => (v == null || v === '' || Number.isNaN(+v) ? '—' : '$' + d3.format(',.2f')(+v));
  RH.kn = (k, n) => `${RH.int(k)}/${RH.int(n)}`;
  // 95% Wilson interval for k successes out of n.
  RH.wilson = (k, n, z = 1.96) => {
    if (!(n > 0)) return [NaN, NaN];
    const p = k / n;
    const z2 = z * z;
    const d = 1 + z2 / n;
    const c = (p + z2 / (2 * n)) / d;
    const h = (z * Math.sqrt((p * (1 - p)) / n + z2 / (4 * n * n))) / d;
    return [Math.max(0, c - h), Math.min(1, c + h)];
  };

  // ---- data -------------------------------------------------------------------------------------------------
  // Rows of dataset `id` when loaded; otherwise paints the loading or failed state on `el` and returns null.
  RH.rows = (id, el) => {
    const d = dash.data(id);
    if (d.status === 'ok') {
      if (el) {
        el.classList.remove('dash-skeleton');
        el.querySelector(':scope > .rh-failed')?.remove();
      }
      return Array.isArray(d.data) ? d.data : [];
    }
    if (el) {
      if (d.status === 'loading') {
        el.replaceChildren();
        el.classList.add('dash-skeleton');
      } else {
        el.classList.remove('dash-skeleton');
        const f = document.createElement('div');
        f.className = 'rh-failed';
        f.textContent = d.status === 'missing' ? 'No data yet' : 'Failed to load';
        el.replaceChildren(f);
      }
    }
    return null;
  };

  // ---- colours ----------------------------------------------------------------------------------------------
  const probe = document.createElement('span');
  probe.style.display = 'none';
  // The computed rgb() of a colour or token, for interpolation.
  RH.css = (color) => {
    root().append(probe);
    probe.style.color = '';
    probe.style.color = color;
    const c = getComputedStyle(probe).color;
    probe.remove();
    return c;
  };
  RH.series = (i) => dash.colors[((i % dash.colors.length) + dash.colors.length) % dash.colors.length];
  const ink = (fill) => {
    const c = d3.rgb(fill);
    return (0.299 * c.r + 0.587 * c.g + 0.114 * c.b) / 255 > 0.55 ? '#16181d' : '#ffffff';
  };

  // ---- shared pieces ----------------------------------------------------------------------------------------
  RH.legend = (items) => {
    const d = document.createElement('div');
    d.className = 'rh-legend';
    for (const [name, color] of items) {
      const s = document.createElement('span');
      const sw = document.createElement('i');
      sw.className = 'rh-sw';
      sw.style.background = color;
      s.append(sw, document.createTextNode(name));
      d.append(s);
    }
    return d;
  };
  // A tooltip inside `el` (which is position: relative). lines: [[text, swatchColor?], ...]
  RH.tip = (el) => {
    let t = el.querySelector(':scope > .rh-tip');
    if (!t) {
      t = document.createElement('div');
      t.className = 'rh-tip';
      t.hidden = true;
      el.append(t);
    }
    return {
      show(event, head, lines) {
        const h = document.createElement('div');
        h.className = 'rh-tip-head';
        h.textContent = head;
        const rows = lines.map(([text, color]) => {
          const r = document.createElement('div');
          r.className = 'rh-tip-row';
          if (color) {
            const s = document.createElement('i');
            s.className = 'rh-sw';
            s.style.background = color;
            r.append(s);
          }
          r.append(document.createTextNode(text));
          return r;
        });
        t.replaceChildren(h, ...rows);
        t.hidden = false;
        const box = el.getBoundingClientRect();
        const tw = t.offsetWidth;
        const th = t.offsetHeight;
        let x = event.clientX - box.left + el.scrollLeft + 12;
        let y = event.clientY - box.top + 12;
        if (x + tw > el.scrollLeft + el.clientWidth) x = Math.max(el.scrollLeft, x - tw - 24);
        if (y + th > el.clientHeight) y = Math.max(0, y - th - 24);
        t.style.left = `${x}px`;
        t.style.top = `${y}px`;
      },
      hide() {
        t.hidden = true;
      },
    };
  };
  const newSvg = (el) => d3.select(el).append('svg').attr('class', 'rh-svg').attr('width', '100%');
  const widest = (svg, texts, cls) => {
    const g = svg.append('g').attr('opacity', 0);
    let w = 0;
    for (const t of texts) w = Math.max(w, g.append('text').attr('class', cls).text(t).node().getComputedTextLength());
    g.remove();
    return Math.ceil(w);
  };
  // Splits text into at most `max` lines that fit `width`; the last line ends in an ellipsis if cut.
  const wrap = (svg, text, width, max, cls) => {
    const g = svg.append('g').attr('opacity', 0);
    const t = g.append('text').attr('class', cls);
    const fits = (s) => t.text(s).node().getComputedTextLength() <= width;
    const words = String(text).split(/\s+/);
    const lines = [];
    let line = '';
    for (const w of words) {
      const next = line ? `${line} ${w}` : w;
      if (fits(next) || !line) line = next;
      else {
        lines.push(line);
        line = w;
      }
    }
    if (line) lines.push(line);
    let out = lines.slice(0, max);
    if (lines.length > max || !fits(out[out.length - 1])) {
      let last = lines.slice(max - 1).join(' ');
      while (last.length > 1 && !fits(`${last}…`)) last = last.slice(0, -1);
      out = [...out.slice(0, max - 1), `${last}…`];
    }
    g.remove();
    return out;
  };
  const lineH = 15;
  const label = (g, lines, x, yMid, anchor, cls) => {
    const t = g.append('text').attr('class', cls).attr('text-anchor', anchor);
    const y0 = yMid - ((lines.length - 1) * lineH) / 2;
    lines.forEach((s, i) => t.append('tspan').attr('x', x).attr('y', y0 + i * lineH).attr('dy', '0.35em').text(s));
    return t;
  };
  const xAxis = (svg, x, y0, y1, fmt, n = 4) => {
    const ticks = x.ticks(n);
    const g = svg.append('g');
    g.selectAll('line').data(ticks).join('line').attr('class', 'rh-grid-line')
      .attr('x1', (d) => x(d)).attr('x2', (d) => x(d)).attr('y1', y0).attr('y2', y1);
    g.selectAll('text').data(ticks).join('text').attr('class', 'rh-tick').attr('text-anchor', 'middle')
      .attr('x', (d) => x(d)).attr('y', y1 + 14).text((d) => fmt(d));
  };

  // ---- charts -----------------------------------------------------------------------------------------------
  // Horizontal bars of k/n with 95% Wilson intervals and "k/n · p" at the end.
  // o: {label='label', k='k', n='n', group?, groupOrder?, colors?: {group: colour}, max=1, xLabel?: axis title}
  RH.rates = (el, rows, o = {}) => {
    const L = o.label ?? 'label';
    const K = o.k ?? 'k';
    const N = o.n ?? 'n';
    const G = o.group;
    const data = rows.map((r) => {
      const k = +r[K];
      const n = +r[N];
      const [lo, hi] = RH.wilson(k, n);
      return { row: r, label: String(r[L]), group: G ? String(r[G]) : '', k, n, p: n > 0 ? k / n : NaN, lo, hi };
    });
    const groups = o.groupOrder ?? [...new Set(data.map((d) => d.group))];
    const colorOf = (g) => o.colors?.[g] ?? RH.series(Math.max(0, groups.indexOf(g)));
    const labels = [...new Set(data.map((d) => d.label))];
    const W = Math.max(280, el.clientWidth);
    el.replaceChildren();
    if (G && groups.length > 1) el.append(RH.legend(groups.map((g) => [g, colorOf(g)])));
    const svg = newSvg(el);
    const vText = (d) => `${RH.kn(d.k, d.n)} · ${Number.isFinite(d.p) ? RH.pct(d.p) : '—'}`;
    const valW = widest(svg, data.map(vText), 'rh-tick');
    const labW = Math.min(Math.round(W * 0.4), widest(svg, labels, 'rh-lab'));
    const bar = 16;
    const gap = 4;
    const blockGap = 12;
    const blocks = [];
    let y = 2;
    for (const lab of labels) {
      const ds = groups.map((g) => data.find((d) => d.label === lab && d.group === g)).filter(Boolean);
      const lines = wrap(svg, lab, labW, 2, 'rh-lab');
      const h = Math.max(ds.length * (bar + gap) - gap, lines.length * lineH);
      const top = y + (h - (ds.length * (bar + gap) - gap)) / 2;
      blocks.push({ lab, lines, mid: y + h / 2, bars: ds.map((d, i) => ({ d, y: top + i * (bar + gap) })) });
      y += h + blockGap;
    }
    const plotBottom = y - blockGap + 6;
    const H = plotBottom + 40;
    const x = d3.scaleLinear([0, o.max ?? 1], [labW + 10, W - valW - 10]);
    svg.attr('viewBox', `0 0 ${W} ${H}`);
    xAxis(svg, x, 0, plotBottom, RH.pct);
    // Axis title: what the bar length is. Pages pass o.xLabel; the default says what the kit draws.
    svg.append('text').attr('class', 'rh-tick').attr('text-anchor', 'middle')
      .attr('x', (x.range()[0] + x.range()[1]) / 2).attr('y', plotBottom + 32)
      .text(o.xLabel ?? 'Share (k of n), line = 95% interval');
    const tip = RH.tip(el);
    for (const b of blocks) {
      label(svg, b.lines, labW, b.mid, 'end', 'rh-lab');
      for (const { d, y: by } of b.bars) {
        const c = colorOf(d.group);
        const g = svg.append('g');
        if (Number.isFinite(d.p)) {
          g.append('rect').attr('x', x(0)).attr('y', by).attr('height', bar).attr('rx', 3)
            .attr('width', Math.max(d.p > 0 ? 2 : 0, x(Math.min(d.p, x.domain()[1])) - x(0))).style('fill', c);
          const cy = by + bar / 2;
          g.append('line').attr('class', 'rh-ci').attr('x1', x(d.lo)).attr('x2', x(d.hi)).attr('y1', cy).attr('y2', cy);
          for (const v of [d.lo, d.hi]) g.append('line').attr('class', 'rh-ci').attr('x1', x(v)).attr('x2', x(v)).attr('y1', cy - 4).attr('y2', cy + 4);
        }
        g.append('text').attr('class', 'rh-tick').attr('text-anchor', 'end').attr('x', W).attr('y', by + bar / 2).attr('dy', '0.35em').text(vText(d));
        g.append('rect').attr('x', 0).attr('y', by - gap / 2).attr('width', W).attr('height', bar + gap).style('fill', 'transparent')
          .on('mousemove', (event) => {
            tip.show(event, d.label, [
              [`${d.group ? `${d.group}: ` : ''}${RH.kn(d.k, d.n)} (${Number.isFinite(d.p) ? RH.pct1(d.p) : '—'})`, c],
              [Number.isFinite(d.lo) ? `95% interval ${RH.pct(d.lo)}–${RH.pct(d.hi)}` : 'No episodes'],
              ...(o.detail ? o.detail(d.row).map((s) => [s]) : []),
            ]);
          })
          .on('mouseleave', () => tip.hide());
      }
    }
  };

  // Grid of values, rows × columns, coloured by value. Good for cue × measure maps.
  // o: {row, col, value, n?, rowOrder?, colOrder?, fmt?, diverging?, max?, min?, detail?(row) -> [text]}
  RH.heat = (el, rows, o) => {
    const key = (r, c) => `${r}\u0000${c}`;
    const rowNames = o.rowOrder ?? [...new Set(rows.map((r) => String(r[o.row])))];
    const colNames = o.colOrder ?? [...new Set(rows.map((r) => String(r[o.col])))];
    const cells = new Map(rows.map((r) => [key(String(r[o.row]), String(r[o.col])), r]));
    const num = (v) => (v == null || v === '' || !Number.isFinite(+v) ? null : +v);
    const vals = rows.map((r) => num(r[o.value])).filter((v) => v != null);
    const fmt = o.fmt ?? (o.diverging ? d3.format('+.0%') : RH.pct);
    const W = Math.max(280, el.clientWidth);
    el.replaceChildren();
    el.classList.add('rh-scroll');
    const svg = d3.select(el).append('svg').attr('class', 'rh-svg');
    const labW = Math.min(Math.round(W * 0.38), widest(svg, rowNames, 'rh-lab'));
    const cw = Math.max(56, (W - labW - 8) / colNames.length);
    const colW = widest(svg, colNames, 'rh-tick');
    const rotate = colW > cw - 8;
    const headH = rotate ? Math.ceil(colW * 0.58) + 18 : 22;
    const ch = 30;
    const width = Math.ceil(labW + 8 + cw * colNames.length + (rotate ? colW * 0.82 : 0));
    const H = headH + ch * rowNames.length + 2;
    svg.attr('viewBox', `0 0 ${width} ${H}`).attr('width', width > W ? width : '100%');
    const base = RH.css('var(--color-panel)');
    const pos = RH.css(RH.series(o.colorIndex ?? 0));
    const neg = RH.css(RH.series(o.negIndex ?? 1));
    const lo = o.min ?? (o.diverging ? 0 : Math.min(0, d3.min(vals) ?? 0));
    const hi = o.max ?? (o.diverging ? d3.max(vals.map(Math.abs)) : d3.max(vals)) ?? 1;
    const colorOf = (v) => {
      if (o.diverging) return v >= 0 ? d3.interpolateRgb(base, pos)(Math.min(1, v / (hi || 1))) : d3.interpolateRgb(base, neg)(Math.min(1, -v / (hi || 1)));
      return d3.interpolateRgb(base, pos)(Math.max(0, Math.min(1, (v - lo) / (hi - lo || 1))));
    };
    const x0 = labW + 8;
    colNames.forEach((c, j) => {
      const cx = x0 + j * cw + cw / 2;
      if (rotate) svg.append('text').attr('class', 'rh-tick').attr('transform', `translate(${cx},${headH - 8}) rotate(-35)`).text(c);
      else svg.append('text').attr('class', 'rh-tick').attr('text-anchor', 'middle').attr('x', cx).attr('y', headH - 8).text(c);
    });
    const tip = RH.tip(el);
    rowNames.forEach((rn, i) => {
      const y = headH + i * ch;
      label(svg, wrap(svg, rn, labW, 1, 'rh-lab'), labW, y + ch / 2, 'end', 'rh-lab');
      colNames.forEach((cn, j) => {
        const r = cells.get(key(rn, cn));
        const v = r ? num(r[o.value]) : null;
        const fill = v == null ? base : colorOf(v);
        const g = svg.append('g');
        g.append('rect').attr('x', x0 + j * cw + 1).attr('y', y + 1).attr('width', cw - 2).attr('height', ch - 2).attr('rx', 3)
          .style('fill', fill).style('stroke', v == null ? 'var(--color-border-line)' : 'none');
        g.append('text').attr('class', 'rh-cell').attr('text-anchor', 'middle').attr('x', x0 + j * cw + cw / 2).attr('y', y + ch / 2).attr('dy', '0.35em')
          .style('fill', v == null ? 'var(--color-fg-muted)' : ink(fill)).text(v == null ? '–' : fmt(v));
        g.on('mousemove', (event) => {
          tip.show(event, `${rn} · ${cn}`, [
            [v == null ? 'No data' : fmt(v)],
            ...(r && o.n && r[o.n] != null ? [[`n = ${RH.int(+r[o.n])}`]] : []),
            ...(r && o.detail ? o.detail(r).map((s) => [s]) : []),
          ]);
        }).on('mouseleave', () => tip.hide());
      });
    });
  };

  // 100% stacked horizontal bars: how each condition's episodes split across categories (e.g. how they end).
  // o: {label, category, value, labelOrder?, order?, colors?: {category: colour}}
  RH.stack = (el, rows, o) => {
    const labels = o.labelOrder ?? [...new Set(rows.map((r) => String(r[o.label])))];
    const cats = o.order ?? [...new Set(rows.map((r) => String(r[o.category])))];
    const colorOf = (c) => o.colors?.[c] ?? RH.series(cats.indexOf(c));
    const W = Math.max(280, el.clientWidth);
    el.replaceChildren();
    el.append(RH.legend(cats.map((c) => [c, colorOf(c)])));
    const svg = newSvg(el);
    const totals = new Map(labels.map((l) => [l, d3.sum(rows.filter((r) => String(r[o.label]) === l), (r) => +r[o.value] || 0)]));
    const nText = (l) => `n = ${RH.int(totals.get(l))}`;
    const valW = widest(svg, labels.map(nText), 'rh-tick');
    const labW = Math.min(Math.round(W * 0.38), widest(svg, labels, 'rh-lab'));
    const bar = 20;
    const rowH = 34;
    const H = labels.length * rowH + 4;
    svg.attr('viewBox', `0 0 ${W} ${H}`);
    const x = d3.scaleLinear([0, 1], [labW + 10, W - valW - 10]);
    const tip = RH.tip(el);
    labels.forEach((l, i) => {
      const y = i * rowH + (rowH - bar) / 2;
      label(svg, wrap(svg, l, labW, 2, 'rh-lab'), labW, y + bar / 2, 'end', 'rh-lab');
      svg.append('text').attr('class', 'rh-tick').attr('text-anchor', 'end').attr('x', W).attr('y', y + bar / 2).attr('dy', '0.35em').text(nText(l));
      const total = totals.get(l) || 0;
      let acc = 0;
      for (const c of cats) {
        const r = rows.find((d) => String(d[o.label]) === l && String(d[o.category]) === c);
        const v = r ? +r[o.value] || 0 : 0;
        if (!v || !total) continue;
        const share = v / total;
        const x1 = x(acc);
        const w = x(acc + share) - x1;
        const fill = colorOf(c);
        const g = svg.append('g');
        g.append('rect').attr('x', x1).attr('y', y).attr('width', Math.max(0, w - 1)).attr('height', bar).style('fill', fill);
        if (w > 34) {
          g.append('text').attr('class', 'rh-cell').attr('text-anchor', 'middle').attr('x', x1 + w / 2).attr('y', y + bar / 2).attr('dy', '0.35em')
            .style('fill', ink(RH.css(fill))).text(RH.pct(share));
        }
        g.on('mousemove', (event) => tip.show(event, l, [[`${c}: ${RH.int(v)} of ${RH.int(total)} (${RH.pct1(share)})`, fill]]))
          .on('mouseleave', () => tip.hide());
        acc += share;
      }
    });
  };

  // Lines over a numeric x (e.g. rejection round): one per series, labelled at its end.
  // o: {x, y, series?, seriesOrder?, xFmt?, yFmt?, yMax?, xLabel?, colors?}
  RH.line = (el, rows, o) => {
    const S = o.series;
    const series = o.seriesOrder ?? (S ? [...new Set(rows.map((r) => String(r[S])))] : ['']);
    const colorOf = (s) => o.colors?.[s] ?? RH.series(series.indexOf(s));
    const yFmt = o.yFmt ?? RH.pct;
    const xFmt = o.xFmt ?? RH.int;
    const pts = rows.map((r) => ({ row: r, s: S ? String(r[S]) : '', x: +r[o.x], y: +r[o.y] })).filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y));
    const W = Math.max(280, el.clientWidth);
    el.replaceChildren();
    const svg = newSvg(el);
    const yMax = o.yMax ?? (d3.max(pts, (p) => p.y) || 1) * 1.1;
    const y = d3.scaleLinear([0, yMax], [180, 8]).nice();
    const tickW = widest(svg, y.ticks(4).map(yFmt), 'rh-tick');
    const ends = series.map((s) => {
      const last = d3.greatest(pts.filter((p) => p.s === s), (p) => p.x);
      return last ? { s, p: last, text: `${s ? `${s} ` : ''}${yFmt(last.y)}` } : null;
    }).filter(Boolean);
    const endW = Math.min(W * 0.3, widest(svg, ends.map((e) => e.text), 'rh-tick'));
    const x = d3.scaleLinear(d3.extent(pts, (p) => p.x).map((v, i) => v ?? i), [tickW + 10, W - endW - 10]);
    const H = 180 + (o.xLabel ? 40 : 24);
    svg.attr('viewBox', `0 0 ${W} ${H}`);
    const g = svg.append('g');
    for (const t of y.ticks(4)) {
      g.append('line').attr('class', 'rh-grid-line').attr('x1', x.range()[0]).attr('x2', x.range()[1]).attr('y1', y(t)).attr('y2', y(t));
      g.append('text').attr('class', 'rh-tick').attr('text-anchor', 'end').attr('x', tickW).attr('y', y(t)).attr('dy', '0.35em').text(yFmt(t));
    }
    const xs = [...new Set(pts.map((p) => p.x))].sort((a, b) => a - b);
    const xt = xs.length <= 12 ? xs : x.ticks(6);
    for (const t of xt) g.append('text').attr('class', 'rh-tick').attr('text-anchor', 'middle').attr('x', x(t)).attr('y', 198).text(xFmt(t));
    if (o.xLabel) g.append('text').attr('class', 'rh-tick').attr('text-anchor', 'middle').attr('x', (x.range()[0] + x.range()[1]) / 2).attr('y', 216).text(o.xLabel);
    const lineGen = d3.line().x((p) => x(p.x)).y((p) => y(p.y));
    for (const s of series) {
      const ps = pts.filter((p) => p.s === s).sort((a, b) => a.x - b.x);
      svg.append('path').attr('d', lineGen(ps)).attr('class', 'rh-line').style('stroke', colorOf(s));
      svg.append('g').selectAll('circle').data(ps).join('circle').attr('cx', (p) => x(p.x)).attr('cy', (p) => y(p.y)).attr('r', 3).style('fill', colorOf(s));
    }
    // End labels, nudged apart.
    const placed = ends.map((e) => ({ ...e, ty: y(e.p.y) })).sort((a, b) => a.ty - b.ty);
    for (let i = 1; i < placed.length; i++) if (placed[i].ty - placed[i - 1].ty < 14) placed[i].ty = placed[i - 1].ty + 14;
    for (const e of placed) svg.append('text').attr('class', 'rh-tick').attr('x', W - endW).attr('y', e.ty).attr('dy', '0.35em').style('fill', colorOf(e.s)).text(e.text);
    const tip = RH.tip(el);
    svg.append('rect').attr('x', x.range()[0]).attr('y', 0).attr('width', Math.max(0, x.range()[1] - x.range()[0])).attr('height', 180).style('fill', 'transparent')
      .on('mousemove', (event) => {
        const [mx] = d3.pointer(event);
        const near = d3.least(xs, (v) => Math.abs(x(v) - mx));
        const here = pts.filter((p) => p.x === near);
        tip.show(event, `${o.xLabel ?? 'x'} ${xFmt(near)}`, here.map((p) => [`${p.s ? `${p.s}: ` : ''}${yFmt(p.y)}${o.n && p.row[o.n] != null ? ` (n = ${RH.int(+p.row[o.n])})` : ''}`, colorOf(p.s)]));
      })
      .on('mouseleave', () => tip.hide());
  };

  // "How this was computed" panels. In build, end each chart card with
  //   <details class="rh-method" data-source="a1_methods" data-chart="a1-gaming"></details>
  // and in draw call RH.methods(el, 'a1_methods'). Rows: {chart, data, sample, computation, labels, code, caveats}.
  const METHOD_FIELDS = [
    ['data', 'Data'],
    ['sample', 'Sample and n'],
    ['computation', 'Computation'],
    ['labels', 'Labels and checks'],
    ['code', 'Code to reproduce'],
    ['caveats', 'Caveats'],
  ];
  RH.methods = (pageEl, id) => {
    const d = dash.data(id);
    const boxes = [...pageEl.querySelectorAll('details.rh-method')].filter((b) => (b.dataset.source || '').split(' ').includes(id));
    const byChart = new Map(d.status === 'ok' && Array.isArray(d.data) ? d.data.map((r) => [String(r.chart), r]) : []);
    for (const box of boxes) {
      const s = document.createElement('summary');
      s.textContent = 'How this was computed';
      const r = byChart.get(box.dataset.chart);
      const body = document.createElement('div');
      body.className = 'rh-method-body';
      if (!r) {
        const p = document.createElement('p');
        p.className = 'rh-note';
        p.textContent = d.status === 'ok' ? 'Not documented yet.' : 'Loading…';
        body.append(p);
      } else {
        const dl = document.createElement('dl');
        for (const [k, label] of METHOD_FIELDS) {
          if (r[k] == null || r[k] === '') continue;
          const dt = document.createElement('dt');
          dt.textContent = label;
          const dd = document.createElement('dd');
          dd.textContent = String(r[k]);
          if (k === 'code') dd.className = 'rh-code';
          dl.append(dt, dd);
        }
        body.append(dl);
      }
      box.replaceChildren(s, body);
    }
  };

  // Numbered findings, most important first: the claim, then its evidence underneath.
  // o: {text='finding', evidence='evidence', tag?: field shown as a small label (e.g. 'strength')}
  RH.findings = (el, rows, o = {}) => {
    el.replaceChildren();
    const ol = document.createElement('ol');
    ol.className = 'rh-findings';
    for (const r of rows) {
      const li = document.createElement('li');
      const p = document.createElement('p');
      p.className = 'rh-finding';
      p.textContent = r[o.text ?? 'finding'] ?? '';
      if (o.tag && r[o.tag]) {
        const t = document.createElement('span');
        t.className = 'rh-pill';
        t.textContent = r[o.tag];
        p.append(' ', t);
      }
      li.append(p);
      const ev = r[o.evidence ?? 'evidence'];
      if (ev) {
        const e = document.createElement('p');
        e.className = 'rh-note';
        e.textContent = ev;
        li.append(e);
      }
      ol.append(li);
    }
    el.append(ol);
  };

  // Example cards: one per row, each with a title, a meta line and quoted text blocks (prompt, reply, reasoning…).
  // Long blocks are cut to `clip` characters with a "Show all" button. A block can highlight a substring of its
  // text (e.g. the cue sentence) given in another field.
  // o: {title, meta?: [fields], blocks: [{field, label, highlight?: field}], clip=700}
  RH.examples = (el, rows, o) => {
    const open = (el.rhOpen ??= new Set());
    const clip = o.clip ?? 700;
    el.replaceChildren();
    const wrapEl = document.createElement('div');
    wrapEl.className = 'rh-examples';
    rows.forEach((r, i) => {
      const card = document.createElement('article');
      card.className = 'rh-ex';
      const head = document.createElement('header');
      const h = document.createElement('strong');
      h.textContent = typeof o.title === 'function' ? o.title(r) : String(r[o.title] ?? '');
      head.append(h);
      const meta = (o.meta ?? []).map((f) => r[f]).filter((v) => v != null && v !== '');
      if (meta.length) {
        const m = document.createElement('span');
        m.className = 'rh-ex-meta';
        m.textContent = meta.join(' · ');
        head.append(m);
      }
      card.append(head);
      o.blocks.forEach((b, j) => {
        const text = r[b.field];
        if (text == null || text === '') return;
        const id = `${i}:${j}`;
        const full = String(text);
        const long = full.length > clip;
        const shown = long && !open.has(id) ? `${full.slice(0, clip).trimEnd()}…` : full;
        const block = document.createElement('div');
        block.className = 'rh-ex-block';
        const lab = document.createElement('div');
        lab.className = 'rh-ex-label';
        lab.textContent = b.label ?? b.field;
        const q = document.createElement('blockquote');
        q.className = 'rh-ex-text';
        const hl = b.highlight ? String(r[b.highlight] ?? '') : '';
        const at = hl ? shown.indexOf(hl) : -1;
        if (at >= 0) {
          const mark = document.createElement('mark');
          mark.textContent = hl;
          q.append(shown.slice(0, at), mark, shown.slice(at + hl.length));
        } else q.textContent = shown;
        block.append(lab, q);
        if (long) {
          const btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'rh-ex-more';
          btn.textContent = open.has(id) ? 'Show less' : 'Show all';
          btn.addEventListener('click', () => {
            if (open.has(id)) open.delete(id);
            else open.add(id);
            RH.examples(el, rows, o);
          });
          block.append(btn);
        }
        card.append(block);
      });
      wrapEl.append(card);
    });
    el.append(wrapEl);
  };

  // A sortable table. Marks itself for the dashboard's Sources: data-source, data-row-key, data-field per column.
  // o: {source, key, columns: [{field, title, fmt?, num?}]}
  RH.table = (el, rows, o) => {
    const state = (el.rhSort ??= { field: null, dir: 1 });
    const cols = o.columns;
    const sorted = [...rows];
    if (state.field) {
      const c = cols.find((d) => d.field === state.field);
      sorted.sort((a, b) => {
        const va = a[state.field];
        const vb = b[state.field];
        const r = c?.num ? (+va || 0) - (+vb || 0) : String(va ?? '').localeCompare(String(vb ?? ''));
        return r * state.dir;
      });
    }
    el.replaceChildren();
    const box = document.createElement('div');
    box.className = 'rh-table-box';
    const t = document.createElement('table');
    t.className = 'rh-table';
    t.dataset.source = o.source;
    t.dataset.rowKey = o.key;
    const tr = document.createElement('tr');
    for (const c of cols) {
      const th = document.createElement('th');
      th.dataset.field = c.field;
      if (c.num) th.classList.add('rh-num');
      th.setAttribute('aria-sort', state.field === c.field ? (state.dir > 0 ? 'ascending' : 'descending') : 'none');
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = c.title ?? c.field;
      b.addEventListener('click', () => {
        state.dir = state.field === c.field ? -state.dir : 1;
        state.field = c.field;
        RH.table(el, rows, o);
      });
      th.append(b);
      tr.append(th);
    }
    const thead = document.createElement('thead');
    thead.append(tr);
    const tbody = document.createElement('tbody');
    for (const r of sorted) {
      const row = document.createElement('tr');
      for (const c of cols) {
        const td = document.createElement('td');
        if (c.num) td.classList.add('rh-num');
        const v = r[c.field];
        td.textContent = c.field === o.key ? String(v) : c.fmt ? c.fmt(v, r) : v == null || v === '' ? '—' : String(v);
        row.append(td);
      }
      tbody.append(row);
    }
    t.append(thead, tbody);
    box.append(t);
    el.append(box);
  };
})();
