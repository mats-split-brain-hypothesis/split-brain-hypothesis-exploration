"""Shared page furniture: palette, CSS, headers, figures, notes, tables, pills, chips, night mode.

Colour carries the algebra on every page: blue = h (and the plain lens), amber = mu, teal = h - mu
(the centred lens). Pages and figures use the CSS tokens (`var(--h)` etc.), so night mode only swaps
the token values; Plotly charts take theirs from `c()`.
"""

import hashlib
import html
import re

import streamlit as st

LIGHT = {
    "bg": "#f5f6f8", "surface": "#ffffff", "sunk": "#eceff3", "sidebar": "#eef0f4",
    "ink": "#17202b", "ink-2": "#3c4757", "muted": "#667185", "line": "#d9dee6", "line-2": "#c4cbd6",
    "h": "#3b63c9", "mu": "#b9781a", "delta": "#0f8a77",
    "h-soft": "#e3eafb", "mu-soft": "#f7ecd9", "delta-soft": "#dcf1ec",
    "good": "#1f7a4a", "warn": "#9a6a00", "bad": "#b3372f",
}
DARK = {
    "bg": "#10151c", "surface": "#161d26", "sunk": "#1c2430", "sidebar": "#131a22",
    "ink": "#e5eaf1", "ink-2": "#c3cbd6", "muted": "#8f9aab", "line": "#26303d", "line-2": "#354152",
    "h": "#6b8de6", "mu": "#c98a2c", "delta": "#22a085",
    "h-soft": "#1d2a47", "mu-soft": "#3a2c15", "delta-soft": "#123a33",
    "good": "#4cbf83", "warn": "#d9a93a", "bad": "#e0675d",
}
THEME = {  # Streamlit theme options: (light, dark); light values match .streamlit/config.toml
    "theme.base": ("light", "dark"),
    "theme.primaryColor": ("h", "h"),
    "theme.backgroundColor": ("bg", "bg"),
    "theme.secondaryBackgroundColor": ("sunk", "sunk"),
    "theme.textColor": ("ink", "ink"),
    "theme.linkColor": ("h", "h"),
    "theme.borderColor": ("line", "line"),
    "theme.dataframeBorderColor": ("line", "line"),
    "theme.dataframeHeaderBackgroundColor": ("sunk", "sunk"),
    "theme.codeBackgroundColor": ("sunk", "sunk"),
    "theme.sidebar.backgroundColor": ("sidebar", "sidebar"),
}
DISPLAY = "'Newsreader', 'Iowan Old Style', Georgia, serif"
BODY = "'IBM Plex Sans', -apple-system, 'Segoe UI', sans-serif"
MONO = "'IBM Plex Mono', ui-monospace, Menlo, monospace"


def night() -> bool:
    return st.get_option("theme.base") == "dark"


def set_night(on: bool):
    from streamlit import config

    pal = DARK if on else LIGHT
    for k, (lk, dk) in THEME.items():
        config.set_option(k, ("dark" if on else "light") if k == "theme.base" else pal[dk if on else lk], "night mode")
    st.session_state["_theme_changed"] = True


def c(token: str) -> str:
    """A token's hex value in the current theme (for Plotly, which cannot read CSS variables)."""
    return (DARK if night() else LIGHT)[token]


CSS = """
<style>
:root { __TOKENS__ }
.block-container { max-width: none; padding: 2.2rem 2.75rem 5rem; }
@media (max-width: 640px) { .block-container { padding-left: 1rem; padding-right: 1rem; } }
.jm-eyebrow { font: 500 11.5px var(--f-mono); letter-spacing: .09em; text-transform: uppercase; color: var(--muted); }
.jm-title { font: 400 clamp(30px, 4vw, 44px)/1.1 var(--f-display); letter-spacing: -.02em; color: var(--ink);
  margin: .3rem 0 .9rem; max-width: 26ch; text-wrap: balance; }
.jm-lede { font-size: 16.5px; line-height: 1.65; color: var(--ink-2); max-width: 70ch; }
.jm-h2 { font: 500 25px/1.2 var(--f-display); letter-spacing: -.01em; color: var(--ink); margin: .2rem 0 .3rem; text-wrap: balance; }
.jm-sub { color: var(--muted); max-width: 78ch; line-height: 1.6; font-size: 14.5px; }
.jm-sec { margin-top: 2.6rem; display: grid; gap: .25rem; }
.m { font-family: var(--f-display); font-style: italic; font-size: 1.12em; white-space: nowrap; }
.m sub { font-size: .68em; }
.c-h { color: var(--h); } .c-mu { color: var(--mu); } .c-d { color: var(--delta); }
.jm-fig { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 16px; overflow-x: auto; }
div[class*="st-key-jmfig"] { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 16px; overflow-x: auto; }
div[class*="st-key-jmfigw"] img { min-width: 560px; }
div[class*="st-key-jmfig"] img { width: 100%; height: auto; display: block; margin: 0 auto; }
.jm-cap { font-size: 13px; color: var(--muted); line-height: 1.55; padding: 8px 2px 0; max-width: 90ch; }
.jm-cap b { color: var(--ink-2); }
.jm-prose { max-width: 78ch; display: grid; gap: .8rem; color: var(--ink-2); line-height: 1.65; font-size: 15px; }
.jm-prose p { margin: 0; }
.jm-note { border-left: 3px solid var(--line-2); padding: 2px 0 2px 14px; display: grid; gap: 4px; font-size: 14.5px;
  color: var(--ink-2); line-height: 1.6; }
.jm-note b.t { color: var(--ink); font-size: 14.5px; }
.jm-note.key { border-left-color: var(--delta); } .jm-note.open { border-left-color: var(--mu); }
.jm-props { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1px; background: var(--line);
  border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }
.jm-props > div { background: var(--surface); padding: 14px 16px; display: grid; gap: 5px; align-content: start; }
.jm-props h4 { margin: 0; padding: 0; font: 600 14.5px var(--f-body); color: var(--ink); }
.jm-props p { margin: 0; font-size: 13.5px; color: var(--ink-2); line-height: 1.5; }
.jm-props .q { font: italic 13px var(--f-display); color: var(--muted); }
.jm-spec { display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: 9px 26px; margin: 0; }
.jm-spec dt { font: 500 11.5px var(--f-mono); letter-spacing: .06em; text-transform: uppercase; color: var(--muted); padding-top: 3px; }
.jm-spec dd { margin: 0; color: var(--ink-2); line-height: 1.55; }
@media (max-width: 600px) { .jm-spec { grid-template-columns: 1fr; gap: 2px; } .jm-spec dd { margin-bottom: 9px; } }
.jm-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px; }
.jm-stat { display: grid; gap: 3px; padding-top: 10px; border-top: 2px solid var(--line-2); }
.jm-stat .v { font: 400 30px/1.1 var(--f-display); font-variant-numeric: tabular-nums; }
.jm-stat .l { font-size: 13px; color: var(--muted); }
.jm-wrap { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; overflow-x: auto; }
.jm-table { width: 100%; border-collapse: collapse; font-size: 13.5px; font-variant-numeric: tabular-nums; }
.jm-table th { text-align: left; font: 500 11px var(--f-mono); letter-spacing: .06em; text-transform: uppercase;
  color: var(--muted); background: var(--sunk); padding: 9px 12px; border-bottom: 1px solid var(--line); white-space: nowrap; }
.jm-table td { padding: 8px 12px; border-bottom: 1px solid var(--line); color: var(--ink); white-space: nowrap; }
.jm-table tr:last-child td { border-bottom: 0; }
.jm-table td .wrap { white-space: normal; display: block; min-width: 16ch; }
.jm-table .num { text-align: right; }
.jm-table .mono { font-family: var(--f-mono); font-size: 12.5px; }
.jm-pill { display: inline-flex; align-items: center; gap: 6px; font: 500 12px var(--f-mono); padding: 1px 9px;
  border-radius: 999px; line-height: 1.75; border: 1px solid transparent; }
.jm-pill::before { content: ""; width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.jm-n { font: 11.5px var(--f-mono); color: var(--muted); margin-left: 4px; }
.jm-pill.done { color: var(--good); background: color-mix(in srgb, var(--good) 12%, transparent); }
.jm-pill.part { color: var(--warn); background: color-mix(in srgb, var(--warn) 13%, transparent); }
.jm-pill.todo { color: var(--muted); border-color: var(--line-2); }
.jm-pill.todo::before { background: transparent; border: 1.5px solid currentColor; box-sizing: border-box; }
.jm-chips { display: flex; flex-wrap: wrap; gap: 5px; }
.jm-chip { font: 12.5px var(--f-mono); padding: 1px 7px; border-radius: 4px; background: var(--sunk); color: var(--ink-2); white-space: pre; }
.jm-chip.hit { background: var(--delta-soft); color: var(--delta); font-weight: 500;
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--delta) 45%, transparent); }
/* another form of the target (swims for swimming): a pass under strict + forms only */
.jm-chip.formhit { color: var(--delta); outline: 1px dashed color-mix(in srgb, var(--delta) 70%, transparent); outline-offset: -1px; }
.jm-ex { display: grid; gap: 10px; padding: 16px; background: var(--surface); border: 1px solid var(--line); border-radius: 10px; }
.jm-ex .hd { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 4px 16px; align-items: baseline; }
.jm-ex .prompt { font: 18px var(--f-display); color: var(--ink); }
.jm-ex .prompt mark { background: none; color: var(--bad); text-decoration: underline wavy; text-underline-offset: 3px; }
.jm-ex .loc { font: 12px var(--f-mono); color: var(--muted); }
.jm-ex .row { display: grid; grid-template-columns: 130px minmax(0, 1fr); gap: 12px; align-items: start; }
.jm-ex .lab { font-size: 12.5px; color: var(--muted); line-height: 1.4; }
.jm-ex .lab b { display: block; font-weight: 600; }
.jm-ex .plain b { color: var(--h); } .jm-ex .cent b { color: var(--delta); }
@media (max-width: 560px) { .jm-ex .row { grid-template-columns: 1fr; gap: 4px; } }
.jm-legend { display: flex; flex-wrap: wrap; gap: 16px; font-size: 13px; color: var(--ink-2); }
.jm-legend span { display: inline-flex; gap: 6px; align-items: center; }
.jm-legend i { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.jm-steps { margin: 0; padding-left: 1.3rem; display: grid; gap: 8px; color: var(--ink-2); line-height: 1.6; max-width: 78ch; }
.jm-steps b { color: var(--ink); }
.jm-wrap code, .jm-prose code, .jm-cap code, .jm-sub code, .jm-steps code, .jm-spec code, .jm-note code {
  font: 12.5px var(--f-mono); background: var(--sunk); padding: 1px 5px; border-radius: 4px; color: var(--ink-2); }
div[class*="st-key-jmeq"], div[class*="st-key-jmkey"] { background: var(--surface); border: 1px solid var(--line);
  border-radius: 10px; padding: 6px 64px 6px 18px; overflow-x: auto; position: relative; }
div[class*="st-key-jmeq"] div[data-testid="stElementContainer"]:has(.jm-tag),
div[class*="st-key-jmkey"] div[data-testid="stElementContainer"]:has(.jm-tag) { position: absolute; right: 18px; top: 50%;
  transform: translateY(-50%); width: auto; }
.jm-tag { font: 14px var(--f-display); color: var(--muted); font-variant-numeric: tabular-nums; }
div[class*="st-key-jmkey"] { border-left: 3px solid var(--delta); background: color-mix(in srgb, var(--delta-soft) 45%, var(--surface)); }
div[class*="st-key-jmeq"] .katex-display, div[class*="st-key-jmkey"] .katex-display { margin: .7em 0; }
div[class*="st-key-jmeq"] .katex, div[class*="st-key-jmkey"] .katex { font-size: 1.16em; color: var(--ink); }
.jm-eqnote { font-size: 13px; color: var(--muted); line-height: 1.5; padding: 0 0 10px; text-align: center; }
div[class*="st-key-jmtext"] p, div[class*="st-key-jmtext"] li { color: var(--ink-2); font-size: 15px; line-height: 1.68; max-width: 78ch; }
div[class*="st-key-jmtext"] .katex { font-size: 1.07em; color: var(--ink); }
.jm-passage { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 14px 18px;
  font: 18px/1.6 var(--f-display); color: var(--ink); display: grid; gap: 10px; white-space: pre-wrap; max-height: 360px; overflow-y: auto; }
.jm-passage .role { display: block; font: 500 11px var(--f-mono); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); margin-bottom: 2px; }
.jm-passage.tok { display: block; font-size: 17px; line-height: 1.75; }
.jm-passage.tok span.sp { font: 11px var(--f-mono); color: var(--muted); background: var(--sunk); border-radius: 3px; padding: 0 3px; }
.jm-passage.tok span.rd { box-shadow: inset 0 -2px 0 color-mix(in srgb, var(--h) 45%, transparent); }
.jm-passage.tok span.sel { background: var(--h-soft); color: var(--h); box-shadow: inset 0 -2px 0 var(--h); border-radius: 3px; }
.jm-passage mark.read { background: var(--h-soft); color: var(--h); border-radius: 3px; padding: 0 2px; box-shadow: inset 0 -2px 0 var(--h); }
.jm-armtag { display: inline-flex; align-items: center; gap: 7px; white-space: nowrap; }
.jm-armtag i { width: 9px; height: 9px; border-radius: 50%; display: inline-block; flex: none; }
.jm-rgrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; }
.jm-rcard { background: var(--surface); border: 1px solid var(--line); border-top: 3px solid var(--c); border-radius: 10px;
  padding: 12px 14px 14px; display: grid; gap: 9px; align-content: start; min-width: 0; }
.jm-rcard .hd { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
.jm-rcard .nm { font: 600 14.5px var(--f-body); color: var(--ink); }
.jm-rcard .sub { font: 11.5px var(--f-mono); color: var(--muted); }
.jm-rcard .meta { display: flex; flex-wrap: wrap; gap: 6px 10px; align-items: center; font: 12px var(--f-mono); color: var(--muted); }
.jm-rcard ol { list-style: none; margin: 0; padding: 0; display: grid; gap: 2px; }
.jm-rcard li { display: grid; grid-template-columns: 16px minmax(0, 1fr) 74px; gap: 8px; align-items: center;
  font: 13px var(--f-mono); padding: 2px 4px; border-radius: 4px; color: var(--ink-2); }
.jm-rcard li .k { color: var(--muted); font-size: 10.5px; text-align: right; }
.jm-rcard li .t { white-space: pre; overflow: hidden; text-overflow: ellipsis; }
.jm-rcard li .s { display: grid; grid-template-columns: 1fr 34px; gap: 5px; align-items: center; }
.jm-rcard li .bar { height: 5px; border-radius: 3px; background: var(--c); opacity: .5; }
.jm-rcard li .v { font-size: 10.5px; color: var(--muted); text-align: right; font-variant-numeric: tabular-nums; }
.jm-rcard li.hit { background: var(--delta-soft); color: var(--delta); font-weight: 600; }
.jm-rcard li.formhit { color: var(--delta); outline: 1px dashed color-mix(in srgb, var(--delta) 70%, transparent); outline-offset: -1px; }
.jm-rcard .jv { border-top: 1px dashed var(--line); padding-top: 8px; display: grid; gap: 5px; }
.jm-rcard .jv .ev { font: 12.5px var(--f-mono); color: var(--ink-2); }
.jm-rcard .jv .why { font-size: 12px; color: var(--muted); line-height: 1.45; max-height: 7.5em; overflow-y: auto; }
.jm-rcard .jm-empty { color: var(--muted); font-size: 13px; }
.jm-layers td { vertical-align: middle; }
.jm-layers tr.cur td { background: color-mix(in srgb, var(--h-soft) 60%, var(--surface)); }
.jm-layers .jm-chip { font-size: 11.5px; }
.jm-phead { display: flex; align-items: baseline; gap: 14px; flex-wrap: wrap; margin: -.4rem 0 .2rem; }
.jm-ptitle { font: 400 30px/1.1 var(--f-display); letter-spacing: -.015em; color: var(--ink); }
.jm-help { color: var(--muted); cursor: help; font-size: 15px; }
.jm-label { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; margin-top: .5rem;
  border-bottom: 1px solid var(--line); padding-bottom: 4px; }
.jm-label > span:first-child { font: 500 11.5px var(--f-mono); letter-spacing: .09em; text-transform: uppercase; color: var(--muted); }
.jm-pgroup { font: 500 10.5px var(--f-mono); letter-spacing: .08em; text-transform: uppercase; color: var(--muted);
             margin: 2px 0 -10px; }
.jm-label .r { font: 12px var(--f-mono); color: var(--ink-2); }
div[class*="st-key-jmchart"] { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 8px 10px 2px; }
</style>
"""


def setup():
    pal = DARK if night() else LIGHT
    tokens = " ".join(f"--{k}: {v};" for k, v in pal.items())
    tokens += f" --f-display: {DISPLAY}; --f-body: {BODY}; --f-mono: {MONO};"
    st.html(CSS.replace("__TOKENS__", tokens))


# ------------------------------------------------------------------ building blocks


def esc(s) -> str:
    return html.escape(str(s))


def header(eyebrow: str, title: str, lede: str = ""):
    st.html(f'<div class="jm-eyebrow">{eyebrow}</div><div class="jm-title">{title}</div>'
            + (f'<div class="jm-lede">{lede}</div>' if lede else ""))


def section(title: str, sub: str = "", eyebrow: str = ""):
    st.html('<div class="jm-sec">' + (f'<div class="jm-eyebrow">{eyebrow}</div>' if eyebrow else "")
            + f'<div class="jm-h2">{title}</div>' + (f'<div class="jm-sub">{sub}</div>' if sub else "") + "</div>")


FIG_SCALE = 1.2  # largest on-screen size of a diagram, relative to its viewBox


def figure(svg: str, caption: str = "", narrow: bool = False):
    """Diagrams go in through st.image (Streamlit's HTML sanitiser strips inline <svg> and data-URI images), so the
    CSS tokens are resolved to the current theme here and the text styles travel inside the SVG."""
    pal = DARK if night() else LIGHT
    svg = re.sub(r"var\(--([a-z0-9-]+)\)", lambda m: pal[m[1]], svg.strip())
    style = (f"<style>text{{font-family:{BODY};fill:{pal['ink']}}} .t-m{{font-family:{DISPLAY};font-style:italic}} "
             f".t-mono{{font-family:{MONO}}} .t-mut{{fill:{pal['muted']}}} .t-2{{fill:{pal['ink-2']}}}</style>")
    svg = re.sub(r"^<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ', svg)
    svg = re.sub(r"(<svg[^>]*>)", lambda m: m[1] + style, svg, count=1)
    key = f"jmfig{'n' if narrow else 'w'}_{hashlib.md5(svg.encode()).hexdigest()[:10]}"
    # Full-width pages: a diagram grows with the window only up to FIG_SCALE x its drawn size (so its text stays near body
    # size), and its card hugs it rather than leaving a wide empty frame.
    vb = re.search(r'viewBox="[\d.]+ [\d.]+ ([\d.]+) ', svg)
    if vb:
        cap = round(float(vb[1]) * FIG_SCALE)
        st.html(f"<style>div.st-key-{key} {{ max-width: {cap + 34}px; }} "
                f"div.st-key-{key} img {{ max-width: {cap}px !important; }}</style>")
    with st.container(key=key):
        st.image(svg, width="stretch")
    if caption:
        st.html(f'<div class="jm-cap">{caption}</div>')


def prose(*paras: str):
    st.html('<div class="jm-prose">' + "".join(f"<p>{p}</p>" for p in paras) + "</div>")


def note(kind: str, title: str, body: str) -> str:
    return f'<div class="jm-note {kind}"><b class="t">{title}</b><span>{body}</span></div>'


def pill(state: str) -> str:
    return f'<span class="jm-pill {state}">{ {"done": "done", "part": "partial", "todo": "to do"}[state]}</span>'


def table(head: list[str], rows: list[list[str]], num: set[int] = frozenset(), mono: set[int] = frozenset()):
    def cls(i):
        k = ("num " if i in num else "") + ("mono" if i in mono else "")
        return f' class="{k.strip()}"' if k.strip() else ""

    th = "".join(f"<th{cls(i) if i in num else ''}>{h}</th>" for i, h in enumerate(head))
    tb = "".join("<tr>" + "".join(f"<td{cls(i)}>{v}</td>" for i, v in enumerate(r)) + "</tr>" for r in rows)
    st.html(f'<div class="jm-wrap"><table class="jm-table"><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table></div>')


def legend(*items: tuple[str, str]):
    st.html('<div class="jm-legend">' + "".join(f'<span><i style="background:var(--{t})"></i>{lab}</span>' for t, lab in items) + "</div>")


def chips(tokens: list[str], target: str) -> str:
    out = []
    for t in tokens:
        hit = t.strip().lower() == target.lower()
        vis = t.replace("\n", "\\n") if t.strip() else (t.replace(" ", "␣") or "∅")
        out.append(f'<span class="jm-chip{" hit" if hit else ""}">{esc(vis)}</span>')
    return '<div class="jm-chips">' + "".join(out) + "</div>"


def plot_layout(fig, height: int):
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=28, b=8), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Sans, sans-serif", size=12.5, color=c("ink-2")), showlegend=False,
        hoverlabel=dict(bgcolor=c("ink"), font=dict(color=c("bg"), family="IBM Plex Sans, sans-serif", size=12.5), bordercolor=c("ink")),
    )
    fig.update_xaxes(gridcolor=c("line"), zeroline=False, linecolor=c("line-2"), tickfont=dict(color=c("muted")))
    fig.update_yaxes(gridcolor=c("line"), zeroline=False, linecolor=c("line-2"), tickfont=dict(color=c("muted")))
    return fig


def chart(fig, key: str, **kw):
    with st.container(key=f"jmchart_{key}"):
        return st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=key, **kw)


def rgba(token: str, alpha: float) -> str:
    h = c(token)
    return f"rgba({int(h[1:3], 16)},{int(h[3:5], 16)},{int(h[5:7], 16)},{alpha})"


# ------------------------------------------------------------------ mathematics (KaTeX through st.latex / st.markdown)


def tex(token: str, s: str) -> str:
    """A LaTeX fragment in a token's colour: tex("mu", r"\\mu") -> \\textcolor{#b9781a}{\\mu}."""
    return rf"\textcolor{{{c(token)}}}{{{s}}}"


def _key(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()[:10]


def eq(latex: str, tag: str = "", key: bool = False, note: str = ""):
    """A display equation in its own panel; `key=True` marks a result the page builds on."""
    with st.container(key=f"{'jmkey' if key else 'jmeq'}_{_key(latex + tag)}"):
        if tag:  # drawn outside KaTeX: its \tag overlaps the equation inside Streamlit's fit-content block
            st.html(f'<span class="jm-tag">({tag})</span>')
        st.latex(latex)
        if note:
            st.html(f'<div class="jm-eqnote">{note}</div>')


def md(text: str):
    """Running text with inline $...$ maths (st.html cannot render LaTeX)."""
    with st.container(key=f"jmtext_{_key(text)}"):
        st.markdown(text)


def legend_arms(arms):
    """A legend row of arm labels in their identity colours (catalog.Arm objects)."""
    st.html('<div class="jm-legend">' + "".join(
        f'<span title="{esc(a.blurb)}"><i style="background:{a.colour}"></i>{esc(a.label)}</span>' for a in arms) + "</div>")


def page_header(eyebrow: str, title: str, help: str = ""):
    """A one-line header for working pages: eyebrow and title on one baseline, explanation behind a hover."""
    tip = f' <span class="jm-help" title="{esc(help)}">ⓘ</span>' if help else ""
    st.html(f'<div class="jm-phead"><span class="jm-eyebrow">{eyebrow}</span><span class="jm-ptitle">{title}</span>{tip}</div>')


def label(text: str, right: str = ""):
    """A small section label for dense pages (in place of a full section heading)."""
    st.html(f'<div class="jm-label"><span>{text}</span>{f"<span class=r>{right}</span>" if right else ""}</div>')


def grouped_pills(label: str, options: list[str], group_of, default: list[str], key: str, format_func=str,
                  help: str = "", order=None, fold=None, beside=None) -> list[str]:
    """Multi-select pills, one row per group under a small group label (one plain row when there is a single group).
    ``fold(g)`` true: the group sits in a collapsed expander. ``beside(g)`` names a group drawn in a column to the right
    of ``g`` instead of on its own row. Returns the options picked in any row, in ``options`` order. Each row keeps its
    own state (key ``<key>:<group>``)."""
    groups: dict[str, list[str]] = {}
    for o in options:
        groups.setdefault(group_of(o), []).append(o)
    names = sorted(groups, key=order) if order else list(groups)
    partner = {}
    for g in names:
        b = beside(g) if beside else None
        if b in groups and b != g and b not in partner.values() and b not in partner:
            partner[g] = b
    picked: set[str] = set()

    def pills(g: str, tip: str = "", labelled: bool = True) -> None:
        if labelled and len(names) > 1:
            st.html(f'<div class="jm-pgroup">{esc(g)}{tip}</div>')
        sel = st.pills(f"{label}: {g}", groups[g], selection_mode="multi", default=[o for o in groups[g] if o in default],
                       format_func=format_func, key=f"{key}:{g}", label_visibility="collapsed",
                       help=help if len(names) == 1 else None)
        picked.update(sel or [])

    def row(g: str, tip: str = "") -> None:
        if fold and fold(g) and len(names) > 1:
            with st.expander(f"{g} ({len(groups[g])})"):
                pills(g, labelled=False)
        else:
            pills(g, tip)

    for i, g in enumerate(names):
        if g in partner.values():
            continue
        tip = f' <span class="jm-help" title="{esc(help)}">ⓘ</span>' if help and i == 0 else ""
        if g in partner:
            left, right = st.columns([3, 2])
            with left:
                row(g, tip)
            with right:
                row(partner[g])
        else:
            row(g, tip)
    return [o for o in options if o in picked]

