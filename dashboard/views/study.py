"""Studies: one page per study of the mu loop, laid out from its card (notes/iteration-anthony/studies/<id>.card.yaml,
schema in CARDS.md): the question and verdict beside the headline numbers, how g is built (formulas) beside a diagram,
the result charts (the study's arms and controls against the family mean, from out/eval), the insights, and under tabs
the full notes and the standard battery (dashboard/battery.py, out/analysis/<run>/). A study with notes or a battery
but no card shows those alone. The overview lists every study as a card."""

import re

import numpy as np
import plotly.graph_objects as go
import streamlit as st

import battery
import catalog
import explainers
import figures
import sources
import ui

ui.header(
    "Loop",
    "Studies",
    "One page per study: the question, the answer, how its centre g is built, and the scores behind it. Pick a study, "
    "or start from the overview.",
)

stamp = sources.stamp()
CARDS = sources.study_cards(stamp)
RUNS = sources.studies()  # out/analysis/ folders, newest first
NOTES = sorted(p.stem for p in sources.STUDIES.glob("*.md") if p.stem not in ("CARDS", "README"))


def _order(sid: str) -> tuple:
    m = re.match(r"([A-Za-z]+)(\d+)", sid)
    return (sid != "baseline", m[1] if m else sid, int(m[2]) if m else 0, sid)


ids = sorted({*CARDS, *NOTES, *(r.split("-")[0] for r in RUNS)}, key=_order)
STATUS = {"finalist": ("finalist", "good"), "negative": ("negative", "bad"), "diagnostic": ("diagnostic", "h"),
          "closed": ("closed", "muted"), "open": ("in progress", "mu")}
OVERVIEW = "Overview"


def title_of(sid: str) -> str:
    c = CARDS.get(sid) or {}
    return f"{sid} · {c['title']}" if c.get("title") else sid


def chip(status: str) -> str:
    lab, tok = STATUS.get(status or "", (status or "no card", "muted"))
    return (f'<span style="display:inline-block;padding:2px 9px;border-radius:999px;font-size:11.5px;font-weight:600;'
            f'letter-spacing:.02em;color:var(--{tok});border:1px solid var(--{tok})">{ui.esc(lab)}</span>')


def arrows(s: str) -> str:
    return (s or "").replace(" -> ", " → ").replace("->", "→").strip()


TEX_SYMBOLS = {"mu": "μ", "lambda": "λ", "alpha": "α", "beta": "β", "sigma": "σ", "Sigma": "Σ", "Delta": "Δ", "delta": "δ",
               "ge": "≥", "geq": "≥", "le": "≤", "leq": "≤", "mid": "|", "approx": "≈", "times": "×", "cdot": "·", "in": "∈",
               "setminus": "∖", "lVert": "‖", "rVert": "‖", "langle": "⟨", "rangle": "⟩", "to": "→", "rightarrow": "→",
               "sum": "Σ", "ne": "≠", "neq": "≠", "neg": "¬", "top": "⊤", "pm": "±", "infty": "∞", "prime": "′", "quad": " ", "qquad": " ", ",": " ", ";": " "}


def tex_inline(t: str) -> str:
    """A $...$ fragment as HTML for places with no maths renderer: macros to symbols, _x / ^x to sub / sup."""
    t = re.sub(r"\\(?:bar|hat|tilde)\s*\{?\s*([A-Za-z])\}?", lambda m: m[1] + "\u0304", t)
    t = re.sub(r"\\([A-Za-z]+|[,;])", lambda m: TEX_SYMBOLS.get(m[1], "\\" + m[1]), t)  # known symbols first
    t = re.sub(r"\\(?:text|mathrm|operatorname|mathbf|mathbb|mathcal|textrm)\{([^{}]*)\}", r"\1", t)
    t = re.sub(r"\\([A-Za-z]+)", r"\1", t)  # any other macro: its name
    t = ui.esc(t)
    for op, tag in (("_", "sub"), ("\\^", "sup")):
        t = re.sub(op + r"\{([^{}]*)\}", rf"<{tag}>\1</{tag}>", t)
        t = re.sub(op + r"([A-Za-z0-9+−-]+)", rf"<{tag}>\1</{tag}>", t)
    return t.replace("{", "").replace("}", "")


def plain(s: str) -> str:
    """Card text as HTML (st.html has no maths renderer): $...$ via tex_inline, `code` unquoted, -> as an arrow."""
    parts = re.split(r"(\$[^$]*\$)", arrows(s or ""))
    return "".join(f'<i>{tex_inline(p[1:-1])}</i>' if p.startswith("$") and p.endswith("$") and len(p) > 1
                   else ui.esc(p).replace("`", "") for p in parts)


st.html("""<style>
.st-card-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(330px,1fr)); gap:14px; }
.st-card { display:grid; gap:8px; align-content:start; background:var(--surface); border:1px solid var(--line);
  border-radius:12px; padding:16px 18px; text-decoration:none !important; color:var(--ink) !important; }
.st-card:hover { border-color:var(--h); box-shadow:0 2px 10px rgba(0,0,0,.06); }
.st-card .top { display:flex; justify-content:space-between; align-items:center; gap:8px; }
.st-card .id { font:600 12.5px var(--f-mono, monospace); color:var(--muted); }
.st-card h4 { margin:0; padding:0; font-size:17px; line-height:1.3; color:var(--ink); }
.st-card p { margin:0; font-size:13.5px; line-height:1.5; color:var(--ink-2); }
.st-card .num { display:flex; gap:8px; align-items:baseline; margin-top:2px; }
.st-card .num b { font-size:19px; color:var(--ink); } .st-card .num span { font-size:12px; color:var(--muted); }
.st-tiles { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:1px; background:var(--line);
  border:1px solid var(--line); border-radius:12px; overflow:hidden; }
.st-tiles > div { background:var(--surface); padding:14px 16px; display:grid; gap:3px; align-content:start; }
.st-tiles .l { font-size:12px; color:var(--muted); line-height:1.35; }
.st-tiles .v { font-size:24px; font-weight:600; color:var(--ink); line-height:1.2; }
.st-tiles .s { font-size:12px; color:var(--ink-2); line-height:1.4; }
.st-head { display:flex; flex-wrap:wrap; align-items:center; gap:10px 14px; margin:6px 0 2px; }
.st-head .id { font:600 15px var(--f-mono, monospace); color:var(--muted); }
.st-head h2 { margin:0; padding:0; font-size:30px; line-height:1.15; }
.st-owner { font-size:12.5px; color:var(--muted); margin-bottom:6px; }
.st-xh { display:flex; align-items:baseline; gap:10px; font-size:19px; font-weight:600; color:var(--ink); margin:26px 0 6px;
  padding-top:14px; border-top:1px solid var(--line); }
.st-xh span { font:600 12px var(--f-mono, monospace); color:var(--surface); background:var(--h); border-radius:999px;
  padding:2px 8px; position:relative; top:-2px; }
div[class*="st-key-stx_"], div[class*="st-key-stxa_"] { max-width:78ch; }
div[class*="st-key-stx_"] p, div[class*="st-key-stxa_"] p, div[class*="st-key-stx_"] li { font-size:15px; line-height:1.6; }
div[class*="st-key-stq_"], div[class*="st-key-stv_"], div[class*="st-key-sti_"] { background:var(--surface);
  border:1px solid var(--line); border-radius:12px; padding:12px 18px 4px; }
div[class*="st-key-stv_"] { border-left:4px solid var(--delta); }
div[class*="st-key-stq_"] { border-left:4px solid var(--h); }
div[class*="st-key-sti_"] p { font-size:14px; line-height:1.55; }
div[data-testid="stTabs"] h1 { font-size:26px !important; } div[data-testid="stTabs"] h2 { font-size:21px !important; }
div[data-testid="stTabs"] h3 { font-size:17px !important; } div[data-testid="stTabs"] [data-testid="stMarkdownContainer"] { max-width:900px; }
.st-lab { font-size:11.5px; font-weight:600; letter-spacing:.08em; text-transform:uppercase; color:var(--muted);
  margin-bottom:-6px; }
</style>""")

c1, c2, _ = st.columns([2.2, 3.2, 0.6], vertical_alignment="bottom")
qp = st.query_params.get("study")
opts = [OVERVIEW, *ids]
sid = c1.selectbox("Study", opts, index=opts.index(qp) if qp in opts else 0, format_func=lambda s: s if s == OVERVIEW else title_of(s),
                   key="st_pick")
st.query_params["study"] = sid

# ------------------------------------------------------------------ overview
if sid == OVERVIEW:
    shown = c2.segmented_control("Status", ["all", *STATUS], default="all", key="st_status",
                                 format_func=lambda s: "all" if s == "all" else STATUS[s][0]) or "all"
    cards = []
    for s in ids:
        c = CARDS.get(s) or {}
        if shown != "all" and c.get("status") != shown:
            continue
        t = (c.get("tiles") or [{}])[0]
        num = (f'<div class="num"><b>{plain(t.get("value", ""))}</b><span>{plain(t.get("label", ""))}</span></div>'
               if t.get("value") else "")
        cards.append(f'<a class="st-card" href="?study={s}" target="_self"><div class="top"><span class="id">{ui.esc(s)}</span>'
                     f'{chip(c.get("status"))}</div><h4>{plain(c.get("title") or s)}</h4>'
                     f'<p>{plain(c.get("question") or "No card yet: notes and battery only.")}</p>{num}</a>')
    st.html(f'<div class="st-card-grid">{"".join(cards)}</div>')
    st.caption("A card per study (notes/iteration-anthony/studies/<id>.card.yaml). Click one to open it.")
    st.stop()

# ------------------------------------------------------------------ one study
card = CARDS.get(sid) or {}
if card.get("_error"):
    st.error(f"{sid}.card.yaml does not parse: {card['_error']}")
    card = {}
note = sources.study_note(sid, card)
runs = [r for r in RUNS if r == sid or r.startswith(f"{sid}-")]

st.html(f'<div class="st-head"><span class="id">{ui.esc(sid)}</span><h2>{plain(card.get("title") or sid)}</h2>'
        f'{chip(card.get("status")) if card else ""}</div>'
        + (f'<div class="st-owner">{plain(card.get("owner", ""))}</div>' if card.get("owner") else ""))

if card:
    left, right = st.columns([1.25, 1], gap="large")
    with left:
        with st.container(key=f"stq_{sid}"):
            st.html('<div class="st-lab">Question</div>')
            st.markdown(arrows(card.get("question", "")))
        with st.container(key=f"stv_{sid}"):
            st.html('<div class="st-lab">Verdict</div>')
            st.markdown(arrows(card.get("verdict", "")))
    with right:
        tiles = card.get("tiles") or []
        if tiles:
            st.html('<div class="st-tiles">' + "".join(
                f'<div><span class="l">{plain(t.get("label", ""))}</span><span class="v">{plain(t.get("value", ""))}</span>'
                f'<span class="s">{plain(t.get("sub", ""))}</span></div>' for t in tiles) + "</div>")

    # -------------------------------------------------------------- how g is built
    ui.section("Method", "How the study builds the centre g in the readout J<sub>l</sub>(h − g(h)), or what it measures.", eyebrow="How it works")
    left, right = st.columns([1.15, 1], gap="large")
    with left:
        for f in card.get("formulas") or []:
            ui.eq(f.get("latex", ""), note=plain(f.get("note", "")))
    with right:
        d = dict(card.get("diagram") or {})
        svg = figures.study(d.pop("kind", ""), **d) if d or card.get("diagram") else None
        if svg:
            ui.figure(svg, caption=plain((card.get("diagram") or {}).get("caption", "")))

    # -------------------------------------------------------------- in depth (card key ``explainer``, CARDS.md)
    if card.get("explainer"):
        ui.section("In depth", "The method step by step: what each piece is, why it is built that way, and what it does "
                   "to the readout, with numbers from the study's own runs.", eyebrow="Explained")
        for k, b in enumerate(card["explainer"]):
            st.html(f'<div class="st-xh"><span>{k + 1}</span>{plain(b.get("heading", ""))}</div>')
            fig = dict(b.get("figure") or {})
            svg = figures.study(fig.pop("kind", ""), **{x: v for x, v in fig.items() if x != "caption"}) if fig else None
            panel = b.get("panel")

            def body(b=b, k=k) -> None:
                with st.container(key=f"stx_{sid}_{k}"):
                    st.markdown(arrows(b.get("text", "")))
                for f in b.get("equations") or []:
                    ui.eq(f.get("latex", ""), note=plain(f.get("note", "")))
                if b.get("after"):
                    with st.container(key=f"stxa_{sid}_{k}"):
                        st.markdown(arrows(b["after"]))

            def side(b=b, k=k, svg=svg, panel=panel) -> None:
                if svg:
                    ui.figure(svg, caption=plain((b.get("figure") or {}).get("caption", "")))
                if panel:
                    explainers.render(panel, f"stxp_{sid}_{k}")

            if b.get("wide") or not (svg or panel):
                body()
                side()
            else:
                left, right = st.columns([1.05, 1], gap="large")
                with left:
                    body()
                with right:
                    side()

# ------------------------------------------------------------------ results (out/eval)
split = card.get("split") or "val"
arm_names, ctrl_names = list(card.get("arms") or []), list(card.get("controls") or [])
R = sources.results(stamp)
fams = [f for f in sources.ALL_FAMILIES if split in R.get(f, {})]
CORE = [f for f in fams if f not in ("user_modeling", "directed_modulation")]
present = {a for f in fams for a in R[f][split]["arms"]}
ref = next((r for r in (["fam@self|cos", "fam@fit|cos"] if split == "fit" else ["fam@fit|cos"]) if r in present), None)
if card and (arm_names or ctrl_names) and ref:
    ARM = {a: catalog.parse(a) for a in [*arm_names, *ctrl_names, ref, "zero|cos"]}

    def change(f: str, a: str) -> dict | None:
        r = R[f][split]
        if a not in r["arms"] or ref not in r["arms"]:
            return None
        if (d := r["diffs"].get(f"{a} - {ref}")) is not None:
            return d
        passes = [sources.item_passes(f, split, sources.arm_dir(x), sources.readouts_mtime(f, split, sources.arm_dir(x)))
                  for x in (a, ref)]
        if None in passes:
            return None
        p = sources.paired(*passes, tuple(r["scored_ids"]))
        return None if p["diff"] is None else {"d": p["diff"], "ci": p["ci95"]}

    shown = [a for a in [*arm_names, *ctrl_names] if a in present and a != ref]
    D = {(f, a): change(f, a) for f in fams for a in shown}

    def mean_d(a: str, fs: list[str]) -> float | None:
        xs = [D[f, a]["d"] for f in fs if D.get((f, a))]
        return float(np.mean(xs)) if xs else None

    def n_fams(a: str) -> int:
        return sum(1 for f in fams if D.get((f, a)))

    def lab(a: str) -> str:
        n = n_fams(a)
        return ("control · " if a in ctrl_names else "") + ARM[a].label + (f" ({n}/{len(fams)})" if n < len(fams) else "")

    ui.section("Results", f"{split} · strict pass (piece proxy on the multi-token families), paired against the family mean "
               f"({ARM[ref].label}). Controls are faded. Numbers are ours, not WorkspaceBench scores.", eyebrow="Scores")
    left, right = st.columns([1, 1.5], gap="large")
    with left:
        ui.label("Macro change vs the family mean", "faded: all families · solid: without UM / DM")
        rows = [a for a in shown if n_fams(a)][::-1]
        fig = go.Figure()
        for k, (name, fs, op) in enumerate([("all families", fams, 0.4), ("without UM / DM", CORE, 1.0)]):
            xs = [mean_d(a, fs) for a in rows]
            fig.add_trace(go.Bar(y=[lab(a) for a in rows], x=xs, orientation="h", name=name, opacity=op,
                                 marker=dict(color=[ARM[a].colour for a in rows]),
                                 text=[f"{x:+.3f}" if x is not None else "" for x in xs], textposition="outside",
                                 textfont=dict(size=10.5), cliponaxis=False,
                                 hovertemplate=f"%{{y}} · {name}: %{{x:+.3f}}<extra></extra>"))
        ui.plot_layout(fig, 90 + 46 * len(rows))
        fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0, margin=dict(r=52))
        fig.add_vline(x=0, line=dict(color=ui.c("line-2"), width=1))
        vals = [x for t in fig.data for x in t.x if x is not None] or [0.0]
        pad = 0.3 * max(max(vals) - min(vals, default=0), 0.02)  # room for the outside labels on both sides
        fig.update_xaxes(range=[min(min(vals), 0) - pad, max(max(vals), 0) + pad])
        fig.update_yaxes(automargin=True, tickfont=dict(size=11.5, color=ui.c("ink-2")))
        fig.update_xaxes(title=dict(text="Δ pass", font=dict(size=11.5)))
        ui.chart(fig, f"st_macro_{sid}")
    with right:
        ui.label("Pass per family", "the main arms beside the plain lens and the family mean · whiskers: 95 % interval")
        fig = go.Figure()
        for a in ["zero|cos", ref, *[x for x in arm_names if x in present and x != ref]]:
            if a not in present:
                continue
            xs, ys, lo, hi = [], [], [], []
            for f in fams:
                v = R[f][split]["arms"].get(a)
                if v:
                    xs.append(f)
                    ys.append(v["v"])
                    lo.append(v["v"] - v["ci"][0])
                    hi.append(v["ci"][1] - v["v"])
            fig.add_trace(go.Bar(x=xs, y=ys, name=ARM[a].label, marker=dict(color=ARM[a].colour),
                                 error_y=dict(type="data", symmetric=False, array=hi, arrayminus=lo, thickness=1, width=2,
                                              color=ui.c("muted")),
                                 hovertemplate=f"<b>{ui.esc(ARM[a].label)}</b> %{{x}}: %{{y:.3f}}<extra></extra>"))
        ui.plot_layout(fig, max(330, 90 + 46 * len([a for a in shown if n_fams(a)])))
        fig.update_layout(barmode="group", bargap=0.22, bargroupgap=0.04)
        fig.update_yaxes(range=[0, 1.05], title=dict(text="pass", font=dict(size=11.5)))
        ui.chart(fig, f"st_pass_{sid}")
        ui.legend_arms([ARM[a] for a in ["zero|cos", ref, *arm_names] if a in present])
    ui.label("Change per family", "paired Δ pass vs the family mean · hover for the 95 % interval")
    rows = [a for a in shown if n_fams(a)][::-1]
    z = [[D[f, a]["d"] if D.get((f, a)) else None for f in fams] for a in rows]
    ci = [[f"[{D[f, a]['ci'][0]:+.2f}, {D[f, a]['ci'][1]:+.2f}]" if D.get((f, a)) else "" for f in fams] for a in rows]
    flat = [v for r in z for v in r if v is not None] or [0.1]
    m = max(max(abs(v) for v in flat), 0.05)
    fig = go.Figure(go.Heatmap(
        z=z, x=fams, y=[lab(a) for a in rows], customdata=ci, zmin=-m, zmax=m, xgap=2, ygap=2, showscale=False,
        colorscale=[[0, ui.c("bad")], [0.5, ui.c("surface")], [1, ui.c("good")]], hoverongaps=False,
        text=[[f"{v:+.2f}" if v is not None else "" for v in r] for r in z], texttemplate="%{text}", textfont=dict(size=11),
        hovertemplate="%{y}<br>%{x}: %{text} %{customdata}<extra></extra>"))
    ui.plot_layout(fig, 110 + 34 * len(rows))
    fig.update_xaxes(side="top", tickangle=-30, tickfont=dict(size=11))
    fig.update_yaxes(automargin=True, tickfont=dict(size=11.5, color=ui.c("ink-2")))
    ui.chart(fig, f"st_heat_{sid}")

elif card:
    st.caption("This study has no evaluated arms of its own (its results are in the numbers above and the notes below).")

# ------------------------------------------------------------------ insights
if card.get("insights"):
    ui.section("Insights", "Most important first.", eyebrow="Findings")
    ins = card["insights"]
    cols = st.columns(2, gap="medium")
    for k, it in enumerate(ins):
        with cols[k % 2]:
            with st.container(key=f"sti_{sid}_{k}"):
                st.markdown(f"**{k + 1}. {arrows(it.get('lead', ''))}**\n\n{arrows(it.get('text', ''))}")
if card.get("next"):
    ui.label("Next")
    st.markdown("\n".join(f"- {arrows(x)}" for x in card["next"]))

# ------------------------------------------------------------------ notes and battery
ui.section("Detail", "The full study notes, and the standard battery for each of the study's runs.", eyebrow="Record")
tabs = st.tabs(["Notes", "Battery (bank by bank)"])
with tabs[0]:
    if note:
        ui.md(note)
    else:
        st.caption(f"No notes/iteration-anthony/studies/{sid}.md yet.")
with tabs[1]:
    if runs:
        run = st.selectbox("Run", runs, key=f"st_run_{sid}",
                           help="out/analysis/<run>/: a study's screens (fit), confirmations (val) and extras.") if len(runs) > 1 else runs[0]
        battery.render(run, stamp)
    else:
        st.caption(f"No battery under out/analysis/{sid}*/.")
