"""Hover the passage: one self-contained HTML/JS component (st.iframe) for the explorer. The
passage is shown as the model read it; hovering a read token shows every selected centre's top 10 at that cell side
by side (accepted targets filled, prompt echoes dotted), with the model's own next token beside them. A layer slider
and click-to-pin run in the browser, so moving along the sentence needs no rerun. Everything shown is passed in as
data; the component reads nothing itself."""

import json

import streamlit as st

import ui

CSS = """
:root { color-scheme: __SCHEME__; }
* { box-sizing: border-box; }
body { margin: 0; font: 13px/1.45 'IBM Plex Sans', -apple-system, 'Segoe UI', sans-serif; color: __ink__; background: transparent; }
.bar { display: flex; align-items: center; gap: 12px; margin: 2px 0 8px; color: __muted__; font-size: 12px; flex-wrap: wrap; }
.bar input[type=range] { flex: 1 1 220px; max-width: 420px; accent-color: __h__; }
.bar b { color: __ink__; font-family: 'IBM Plex Mono', monospace; }
.pin { padding: 1px 7px; border-radius: 9px; border: 1px solid __line2__; cursor: pointer; }
.pin.on { background: __hsoft__; border-color: __h__; color: __ink__; }
.passage { position: relative; background: __surface__; border: 1px solid __line__; border-radius: 8px; padding: 10px 12px; max-height: 150px;
           overflow-y: auto; white-space: pre-wrap; word-break: break-word; font-size: 15px; line-height: 1.7; }
.passage .sp { font-size: 10.5px; color: __muted__; }
.passage .rd { border-bottom: 2px solid __line2__; cursor: pointer; border-radius: 2px; }
.passage .rd:hover, .passage .rd.cur { background: __musoft__; border-bottom-color: __mu__; }
.passage .rd.hit { border-bottom-color: __delta__; }
.cols { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px; margin-top: 10px; }
.col { background: __surface__; border: 1px solid __line__; border-top: 3px solid var(--c); border-radius: 8px; padding: 6px 8px; min-width: 0; }
.col .nm { font-weight: 600; font-size: 12.5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col .meta { color: __muted__; font-size: 11px; margin: 1px 0 4px; min-height: 15px; }
.col ol { list-style: none; margin: 0; padding: 0; }
.col li { display: flex; gap: 6px; padding: 0 4px; border-radius: 4px; font-family: 'IBM Plex Mono', monospace; font-size: 12px;
          white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.col li .k { color: __muted__; width: 14px; text-align: right; flex: none; }
.col li.hit { background: __deltasoft__; color: __ink__; font-weight: 600; }
.col li.echo .t { text-decoration: underline dotted __warn__; text-underline-offset: 3px; }
.col li .g { color: __muted__; font-family: 'IBM Plex Sans', sans-serif; font-size: 11px; margin-left: 4px; }
.col.next { --c: __muted__; }
.empty { color: __muted__; font-style: italic; font-size: 12px; }
.hint { color: __muted__; font-size: 12px; margin-top: 8px; }
"""

JS = """
const D = JSON.parse(document.getElementById('d').textContent);
const P = document.getElementById('passage'), C = document.getElementById('cols'), S = document.getElementById('layer');
const LV = document.getElementById('lv'), WH = document.getElementById('where'), PIN = document.getElementById('pin');
let cur = D.pos, pinned = false, li = Math.max(0, D.layers.indexOf(D.layer));
S.max = D.layers.length - 1; S.value = li;
function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
function anyHit(p) { return D.arms.some(a => D.layers.some(L => ((a.cells[L + '|' + p] || {}).t || []).some(x => x[1].includes('hit')))); }
function renderPassage() {
  P.textContent = '';
  if (!D.toks) {  // no tokenizer cached: the read cells only
    D.positions.forEach(p => { const s = el('span', 'rd', D.posTok[p] + ' '); s.dataset.p = p; P.appendChild(s); });
  } else {
    const at = {}; D.positions.forEach(p => { at[p >= 0 ? p : D.toks.length + p] = p; });
    D.toks.forEach((t, k) => {
      const special = (t.startsWith('<|') && t.endsWith('|>')) || t === '<think>' || t === '</think>';
      if (k in at) {
        const s = el('span', 'rd' + (anyHit(at[k]) ? ' hit' : ''), t.trim() ? t : t.replace(/ /g, '\\u2423').replace(/\\n/g, '\\u21b5\\n'));
        s.dataset.p = at[k]; s.title = 'read cell · position ' + k; P.appendChild(s);
      } else if (special) { P.appendChild(el('span', 'sp', t)); }
      else { P.appendChild(document.createTextNode(t)); }
    });
  }
  P.querySelectorAll('.rd').forEach(s => {
    s.addEventListener('mouseenter', () => { if (!pinned) show(+s.dataset.p); });
    s.addEventListener('click', () => { pinned = !(pinned && cur === +s.dataset.p); setPin(); show(+s.dataset.p); });
  });
}
function setPin() { PIN.classList.toggle('on', pinned); PIN.textContent = pinned ? 'pinned · click to release' : 'hover a token · click to pin'; }
function list(rows) {
  const ol = el('ol');
  rows.forEach((x, k) => {
    const li = el('li', x[1]); li.appendChild(el('span', 'k', String(k + 1)));
    li.appendChild(el('span', 't', x[0])); if (x[2]) li.appendChild(el('span', 'g', x[2])); ol.appendChild(li);
  });
  return ol;
}
function show(p) {
  cur = p; const L = D.layers[li];
  LV.textContent = 'L' + L; WH.textContent = '\\u201c' + (D.posTok[p] || '') + '\\u201d · ' + (p >= 0 ? 'position ' + p : 'token ' + (-p) + ' from the end');
  P.querySelectorAll('.rd').forEach(s => s.classList.toggle('cur', +s.dataset.p === p));
  const ce = P.querySelector('.rd.cur');  // keep the current cell in view (DM reads sit below the prompt)
  if (ce && (ce.offsetTop < P.scrollTop || ce.offsetTop > P.scrollTop + P.clientHeight - 28)) P.scrollTop = ce.offsetTop - 40;
  C.textContent = '';
  D.arms.forEach(a => {
    const c = el('div', 'col'); c.style.setProperty('--c', a.colour);
    c.appendChild(el('div', 'nm', a.label)); const cell = a.cells[L + '|' + p];
    const r = cell ? cell.r : null;
    c.appendChild(el('div', 'meta', r == null ? '' : r < 0 ? 'no single-token target' : 'target #' + (r + 1)));
    c.appendChild(cell ? list(cell.t) : el('div', 'empty', 'no readout here'));
    C.appendChild(c);
  });
  const n = D.next[p];
  if (n) { const c = el('div', 'col next'); c.appendChild(el('div', 'nm', "Model's next token")); c.appendChild(el('div', 'meta', 'final layer, same at every layer')); c.appendChild(list(n)); C.appendChild(c); }
}
S.addEventListener('input', () => { li = +S.value; show(cur); });
document.addEventListener('keydown', e => {
  const i = D.positions.indexOf(cur);
  if (e.key === 'ArrowRight' && i < D.positions.length - 1) show(D.positions[i + 1]);
  if (e.key === 'ArrowLeft' && i > 0) show(D.positions[i - 1]);
  if (e.key === 'ArrowUp' && li < D.layers.length - 1) { li++; S.value = li; show(cur); }
  if (e.key === 'ArrowDown' && li > 0) { li--; S.value = li; show(cur); }
});
renderPassage(); setPin(); show(cur);
"""


def panel(*, toks: list[str] | None, positions: list[int], pos_tok: dict[int, str], layers: list[int], layer: int,
          pos: int, arms: list[dict], next_tokens: dict[int, list[list[str]]], height: int = 560) -> None:
    """Render the component. ``arms``: [{label, colour, cells: {"L|pos": {"t": [[shown, classes, gloss], ...],
    "r": best target rank or None}}}]; ``next_tokens``: pos -> rows in the same form."""
    pal = ui.DARK if ui.night() else ui.LIGHT
    css = CSS.replace("__SCHEME__", "dark" if ui.night() else "light")
    for k in ("ink", "muted", "h", "mu", "delta", "warn", "surface", "line"):
        css = css.replace(f"__{k}__", pal[k])
    css = (css.replace("__line2__", pal["line-2"]).replace("__hsoft__", pal["h-soft"])
              .replace("__musoft__", pal["mu-soft"]).replace("__deltasoft__", pal["delta-soft"]))
    data = {"toks": toks, "positions": positions, "posTok": {str(k): v for k, v in pos_tok.items()}, "layers": layers,
            "layer": layer, "pos": pos, "arms": arms, "next": {str(k): v for k, v in next_tokens.items()}}
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = (f"<style>{css}</style>"
            '<div class="bar"><span>layer <b id="lv"></b></span><input type="range" id="layer" min="0" step="1">'
            '<span id="where"></span><span class="pin" id="pin"></span></div>'
            '<div class="passage" id="passage"></div><div class="cols" id="cols"></div>'
            '<div class="hint">← → move along the read cells · ↑ ↓ change layer · filled = accepted target · '
            'dotted = an echo of the prompt</div>'
            f'<script type="application/json" id="d">{blob}</script><script>{JS}</script>')
    st.iframe(html, height=height)
