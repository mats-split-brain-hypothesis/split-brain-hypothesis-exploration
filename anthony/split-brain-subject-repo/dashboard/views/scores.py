"""Scores: just the numbers, charts first. For the chosen arms on one split: the macro average over the families picked
at the top (by default every family but user_modeling / directed_modulation, the two whose pass can be bought by reading
the prompt), pass per family with its 95 % interval, and the paired change against a reference arm; then the same
numbers as tables. Every chart and table covers the picked families only.
Generated from out/eval/*/<split>/summary.json and the judge runs, like the Leaderboard."""

import numpy as np
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import catalog
import nights
import sources
import ui

ui.header(
    "Loop",
    "Scores",
    "The scores alone: bar charts first, then the tables behind them. Strict pass on the single-token families, the "
    "distinctive-piece proxy on the multi-token ones; judged is the newest full Haiku run where one exists (val). "
    "Ours, not WorkspaceBench scores.",
)

PROMPT_READ = ("user_modeling", "directed_modulation")  # pass can come from reading the prompt (S11, U1)
stamp = sources.stamp()
R = sources.results(stamp)
splits = [s for s in sources.SPLITS if any(s in R[f] for f in R)]
if not splits:
    st.info("No summary.json under out/eval yet: run experiments/evaluate.py first.")
    st.stop()

c1, c2, c3, c4 = st.columns([1, 1, 1.3, 2.2], vertical_alignment="bottom")
split = c1.segmented_control("Split", splits, default="val" if "val" in splits else splits[0], key="sc_split") or splits[0]
readout = c2.segmented_control("Readout", ["cos", "rms"], default="cos", key="sc_readout") or "cos"
FORMS = "strict + forms"
SCORES = ["strict", FORMS, "judged"] if split == "val" else ["strict", FORMS]
# ?score=strict|forms|judged picks the score (a link to one view); strict + forms by default
asked = {"strict": "strict", "forms": FORMS, "judged": "judged"}.get(st.query_params.get("score", ""), FORMS)
metric = c3.segmented_control("Score", SCORES, default=asked if asked in SCORES else FORMS, key=f"sc_metric_{split}",
                              help="strict: a top-10 token spells the target. strict + forms: also its inflections "
                                   "(swims for swimming), and in association words derived from it (swimmer); "
                                   "data/forms, jlm.forms. Multi-token families keep the piece proxy.") or FORMS
PAIRED = metric != "judged"  # free scores: paired changes rebuilt from the readouts
all_fams = [f for f in sources.ALL_FAMILIES if split in R.get(f, {})]
fams = st.pills("Families in the score", all_fams, selection_mode="multi",
                default=[f for f in all_fams if f not in PROMPT_READ], key=f"sc_fams_{split}",
                help="The macro averages, the ranking and every chart and table below use only these families. "
                     "Off by default: user_modeling and directed_modulation, whose pass a centre can buy by reading "
                     "the prompt (studies S11, U1).")
fams = [f for f in all_fams if f in (fams or [])]
if not fams:
    st.info("No families selected.")
    st.stop()
names = {a for f in fams for a in R[f][split]["arms"]}
arms = sorted((catalog.parse(n) for n in names if catalog.parse(n).readout == readout), key=lambda a: a.sort_key)
if not arms:
    st.info(f"No {readout} arms on {split}.")
    st.stop()
by_name = {a.name: a for a in arms}
held_ref = "self" if split == "fit" else "fit"
ref_default = next((a.name for a in arms if a.centre == "fam" and a.ref == held_ref and not a.control),
                   next((a.name for a in arms if a.centre == "zero"), arms[0].name))
ref_name = c4.selectbox("Reference (for the change)", [a.name for a in arms], index=[a.name for a in arms].index(ref_default),
                        format_func=lambda n: f"{by_name[n].label} · {n}", key=f"sc_ref_{split}_{readout}")

STUDY = {a.name: ("control" if a.control else "J++" if a.lens != "jlens" else catalog.study(a.inner)) for a in arms}
studies = sorted({v for v in STUDY.values()} - {"baseline", "control", "J++"})
s1, s2, s3 = st.columns([2.6, 2.2, 1.6], vertical_alignment="bottom")
SETS = ["Defaults", "Every centre", "By study"]
aset = s1.segmented_control("Show", SETS, default="Defaults", key="sc_set",
                            help="Defaults: plain J-lens, family mean, plain J++ and Anthony's best candidates (catalog.DEFAULT_CENTRES). "
                                 "Every centre: every centre scored on this split. By study: one study's centres, with "
                                 "the baseline and the study's controls.") or "Defaults"
with_ctrl = s3.toggle("Include controls", value=aset == "By study", key=f"sc_ctrl_{aset}",
                      help="shuf. (another cell's g) and rand. (a random direction with g's norm) arms.")
if aset == "By study":
    which = s2.selectbox("Study", studies, key="sc_study") if studies else None
    pool = [a for a in arms if STUDY[a.name] in ("baseline", which)
            or (a.control and catalog.study(a.inner) == which)]
elif aset == "Every centre":
    pool = [a for a in arms if a.lens == "jlens"]
    flt = s2.text_input("Filter", placeholder="e.g. knn, u1, pco", key="sc_filter").strip().lower()
    if flt:
        pool = [a for a in pool if flt in a.name.lower() or flt in a.label.lower() or a.name == ref_name]
else:
    pool = arms
if not with_ctrl:
    pool = [a for a in pool if not a.control]
if aset == "Defaults":
    # Night 2's best candidates in their own group beside Anthony's best candidates, ranked best first; "Other centres" folded
    picker = nights.Picker(pool, held_ref, stamp, fold_others=True)
    chosen = [by_name[n] for n in picker.pills("Arms", catalog.defaults(arms, held_ref), key=f"sc_arms_{split}_{readout}_{with_ctrl}")]
else:
    chosen = sorted(pool, key=lambda a: a.sort_key)
if not chosen:
    st.info("No arms selected.")
    st.stop()
MANY = len(chosen) > 8  # past this, ranked bars and heatmaps instead of grouped bars
# Past 8 arms the per-centre colours repeat, so the ranked bars are coloured by study instead.
STUDY_COLOURS = ["#3b63c9", "#0f8a77", "#b9781a", "#c2417a", "#6250d6", "#008300", "#e34948", "#5f6b7a", "#8a5a00",
                 "#1b8fb5", "#9b4fd0", "#d06a1f", "#4a7d2c"]
STUDY_COLOUR = {k: STUDY_COLOURS[i % len(STUDY_COLOURS)] for i, k in enumerate(sorted(set(STUDY.values())))}


def colour(a) -> str:
    return STUDY_COLOUR[STUDY[a.name]] if MANY else a.colour
if not MANY:
    ui.legend_arms(chosen)
else:
    st.caption(f"{len(chosen)} arms: ranked bars and heatmaps below, coloured by study. Narrow with the filter or a study.")
    here = sorted({STUDY[a.name] for a in chosen})
    st.html('<div class="jm-legend">' + "".join(f'<span><i style="background:{STUDY_COLOUR[k]}"></i>{ui.esc(k)}</span>'
                                                for k in here) + "</div>")


def judged(f: str, a: str) -> dict | None:
    adir = sources.arm_dir(a)
    runs = sources.judge_runs(f, split, adir)
    if not runs:
        return None
    j = sources.judged(f, split, adir, runs[0], sources.readouts_mtime(f, split, adir))
    return {"v": j["value"], "ci": j["ci"]} if j.get("value") is not None else None


def score(f: str, a: str) -> dict | None:
    """{v, ci} for arm a on family f under the chosen score."""
    if metric == "judged":
        return judged(f, a)
    v = R[f][split]["arms"].get(a)
    if v and metric == FORMS and f not in sources.MT_FAMILIES:
        return v.get("forms")
    return {"v": v["v"], "ci": v["ci"]} if v else None


def change(f: str, a: str) -> dict | None:
    """Paired change a - reference on f (the chosen free score): the summary's diff, else rebuilt from the readouts."""
    r = R[f][split]
    forms = metric == FORMS and f not in sources.MT_FAMILIES
    if a not in r["arms"] or ref_name not in r["arms"] or (forms and not r.get("forms_ids")):
        return None
    if a == ref_name:
        return {"d": 0.0, "ci": [0.0, 0.0]}
    if (d := r["diffs_forms" if forms else "diffs"].get(f"{a} - {ref_name}")) is not None:
        return d
    passes = [sources.item_passes(f, split, sources.arm_dir(x), sources.readouts_mtime(f, split, sources.arm_dir(x)), forms)
              for x in (a, ref_name)]
    if None in passes:
        return None
    p = sources.paired(*passes, tuple(r["forms_ids"] if forms else r["scored_ids"]))
    return None if p["diff"] is None else {"d": p["diff"], "ci": p["ci95"]}


with st.spinner("Collecting scores…"):
    S = {(f, a.name): score(f, a.name) for f in fams for a in chosen}
    D = {(f, a.name): change(f, a.name) for f in fams for a in chosen} if PAIRED else {}

single = [f for f in fams if f not in sources.MT_FAMILIES]
multi = [f for f in fams if f in sources.MT_FAMILIES]


def macro(a: str, fs: list[str]) -> float | None:
    """Mean pass over the families of ``fs`` the arm was scored on (see ``covered``)."""
    xs = [S[f, a]["v"] for f in fs if S.get((f, a))]
    return float(np.mean(xs)) if xs else None


def macro_change(a: str, fs: list[str]) -> float | None:
    xs = [D[f, a]["d"] for f in fs if D.get((f, a))]
    return float(np.mean(xs)) if xs else None


def covered(a: str) -> int:
    return sum(1 for f in fams if S.get((f, a)))


def name_of(a) -> str:
    """Chart label: the arm's label, with its family count when it was not scored on every family."""
    n = covered(a.name)
    return a.label + (f" ({n}/{len(fams)})" if n < len(fams) else "")


def rank_key(a) -> tuple:
    """Arms scored on every picked family first (a macro over 2 families is not comparable), then by the macro."""
    v = macro_change(a.name, fams) if PAIRED else macro(a.name, fams)
    if a.name == ref_name and PAIRED:
        v = 0.0
    return (covered(a.name) == len(fams), v if v is not None else -99)


ranked = sorted(chosen, key=rank_key, reverse=True)
scored = [a for a in ranked if covered(a.name)]
unscored = [a for a in ranked if not covered(a.name)]


def bar_layout(fig, height: int, y_title: str, rng=None):
    ui.plot_layout(fig, height)
    fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.05)
    fig.update_yaxes(title=dict(text=y_title, font=dict(size=11.5)), range=rng)
    return fig


def ranked_bars(vals: dict[str, float | None], fmt: str, x_title: str, key: str):
    """Horizontal bars, one row per arm (best on top), each the macro over the picked families."""
    rows = [a for a in scored if a.name in vals]
    ys = [("· " if covered(a.name) < len(fams) else "") + name_of(a) for a in rows][::-1]
    xs = [vals[a.name] for a in rows][::-1]
    fig = go.Figure(go.Bar(y=ys, x=xs, orientation="h", marker=dict(color=[colour(a) for a in rows][::-1]),
                           text=[format(x, fmt) if x is not None else "" for x in xs], textposition="outside",
                           textfont=dict(size=10), cliponaxis=False,
                           hovertemplate=f"%{{y}}: %{{x:{fmt}}}<extra></extra>"))
    ui.plot_layout(fig, 60 + (28 if len(rows) <= 8 else 20) * len(rows))
    fig.update_layout(bargap=0.25, showlegend=False, margin=dict(r=48))
    fig.update_xaxes(title=dict(text=x_title, font=dict(size=11.5)))
    fig.update_yaxes(automargin=True, tickfont=dict(size=11.5, color=ui.c("ink-2")))
    ui.chart(fig, key)


def heatmap(z_of, fs: list[str], fmt: str, diverging: bool, key: str, zrange=None):
    rows = scored[::-1]
    z = [[z_of(f, a) for f in fs] for a in rows]
    flat = [v for r in z for v in r if v is not None]
    if diverging:
        m = max([abs(v) for v in flat] + [0.05])
        scale, lo, hi = [[0, ui.c("bad")], [0.5, ui.c("bg")], [1, ui.c("good")]], -m, m
    else:
        scale, lo, hi = "Blues", *(zrange or (0, 1))
    fig = go.Figure(go.Heatmap(
        z=z, x=fs, y=[name_of(a) for a in rows], colorscale=scale, zmin=lo, zmax=hi, xgap=1, ygap=1,
        text=[[format(v, fmt) if v is not None else "" for v in r] for r in z], texttemplate="%{text}",
        textfont=dict(size=10), showscale=False, hoverongaps=False,
        hovertemplate="%{y}<br>%{x}: %{text}<extra></extra>"))
    ui.plot_layout(fig, 90 + 24 * len(rows))
    fig.update_xaxes(side="top", tickangle=-30, tickfont=dict(size=11))
    fig.update_yaxes(automargin=True, tickfont=dict(size=11.5, color=ui.c("ink-2")))
    ui.chart(fig, key)


# ------------------------------------------------------------------ charts
if unscored:
    st.caption(f"{len(unscored)} chosen arm(s) have no {metric} score on {split}: "
               + ", ".join(a.label for a in unscored) + ".")
if not scored:
    st.info(f"None of the chosen arms has a {metric} score on {split}." + (
        " Judged runs exist only for a few finalists: switch Score to strict, or Show → Defaults." if metric == "judged" else ""))
    st.stop()

ui.section("Macro average", f"{split} · {metric} · mean of each arm's pass over the {len(fams)} picked families, best "
           "first. Arms scored on every picked family come first; an arm scored on fewer shows the count, e.g. (2/11), "
           "is averaged over those only and is listed after them.", eyebrow="Charts")
if PAIRED:
    left, right = st.columns(2, gap="large")
    with left:
        ui.label("Macro pass")
        ranked_bars({a.name: macro(a.name, fams) for a in scored}, ".3f", "pass", f"sc_macro_{split}_{aset}")
    with right:
        ui.label("Macro change vs reference", f"paired, strict · {by_name[ref_name].label}")
        ranked_bars({a.name: macro_change(a.name, fams) for a in scored if a.name != ref_name},
                    "+.3f", f"Δ pass vs {by_name[ref_name].label}", f"sc_macrod_{split}_{aset}_{ref_name}")
else:
    ui.label("Macro judged pass", "over the families each arm was judged on")
    ranked_bars({a.name: macro(a.name, fams) for a in scored}, ".3f", "judged pass", f"sc_macroj_{split}_{aset}")


def family_bars(fs: list[str], key: str, title: str):
    ui.label(title, "error bars: 95 % interval")
    fig = go.Figure()
    for a in scored:
        xs, ys, lo, hi = [], [], [], []
        for f in fs:
            s = S.get((f, a.name))
            if s:
                xs.append(f)
                ys.append(s["v"])
                lo.append(s["v"] - s["ci"][0])
                hi.append(s["ci"][1] - s["v"])
        fig.add_trace(go.Bar(x=xs, y=ys, name=a.label, marker=dict(color=a.colour),
                             error_y=dict(type="data", symmetric=False, array=hi, arrayminus=lo, thickness=1, width=2,
                                          color=ui.c("muted")),
                             hovertemplate=f"<b>{ui.esc(a.label)}</b> %{{x}}: %{{y:.3f}}<extra></extra>"))
    ui.chart(bar_layout(fig, 360, "pass", [0, 1.05]), key)


ui.section("Pass per family", "Each bar is one arm on one family; the whiskers are the item-bootstrap 95 % interval."
           if not MANY else "One row per arm (best macro first), one column per family.")
if not MANY:
    left, right = st.columns([len(single) or 1, len(multi) or 1], gap="large")
    with left:
        family_bars(single, f"sc_fam1_{split}_{metric}", "Single-token families")
    with right:
        if multi:
            family_bars(multi, f"sc_fam2_{split}_{metric}", "Multi-token families (piece proxy)")
else:
    heatmap(lambda f, a: S[f, a.name]["v"] if S.get((f, a.name)) else None, fams, ".2f", False, f"sc_hm_{split}_{metric}_{aset}")

# ------------------------------------------------------------------ by layer
# Each family's summary carries a per-layer curve per arm (sources._by_layer: share of scored items with a target in
# the top 10 at that one layer, strict, no forms). The macro curve averages them over the picked families.
LAYERS = next(R[f][split]["layers"] for f in fams)
CURVE = {(f, a.name): R[f][split]["by_layer"].get(a.name) for f in fams for a in scored}
CURVE = {k: v for k, v in CURVE.items() if v and len(v) == len(LAYERS)}


def layer_curve(a: str, fs: list[str]) -> list[float] | None:
    """Mean over ``fs`` of the arm's per-layer curve, when it has one on every family of ``fs``."""
    cs = [CURVE.get((f, a)) for f in fs]
    return None if not cs or None in cs else list(np.mean(cs, axis=0))


def layer_lines(fig, curves: dict, fmt: str, **rc):
    for a in scored:
        if (ys := curves.get(a.name)) is None:
            continue
        fig.add_trace(go.Scatter(x=LAYERS, y=ys, mode="lines+markers", name=a.label, legendgroup=a.name,
                                 showlegend=False, line=dict(color=colour(a), width=2), marker=dict(size=4),
                                 hovertemplate=f"{ui.esc(a.label)}: %{{y:{fmt}}}<extra></extra>"), **rc)


layered = [a for a in scored if layer_curve(a.name, fams) is not None]
ui.section("By layer", f"{split} · strict · share of scored items with a target in the top 10 at that one layer, "
           f"averaged over the {len(fams)} picked families. The scores above take each item's best layer, so they sit "
           "above every point here; these curves are strict only (no forms, no judge) whatever the Score above. "
           "Arms without a curve on every picked family are left out of the macro.")
if not layered:
    st.caption("No per-layer curves for the chosen arms on every picked family.")
else:
    macro_l = {a.name: layer_curve(a.name, fams) for a in layered}
    ref_l = layer_curve(ref_name, fams)
    left, right = st.columns(2, gap="large")
    with left:
        ui.label("Macro pass by layer")
        fig = go.Figure()
        layer_lines(fig, macro_l, ".3f")
        ui.plot_layout(fig, 340)
        fig.update_layout(hovermode="x unified")
        fig.update_xaxes(title=dict(text="layer", font=dict(size=11.5)), tickvals=LAYERS)
        fig.update_yaxes(title=dict(text="pass at this layer", font=dict(size=11.5)))
        ui.chart(fig, f"sc_layer_{split}_{aset}")
    with right:
        ui.label("Change vs reference by layer", f"strict · {by_name[ref_name].label}")
        if ref_l is None:
            st.caption(f"{by_name[ref_name].label} has no per-layer curve on every picked family.")
        else:
            fig = go.Figure()
            layer_lines(fig, {a: [y - r for y, r in zip(ys, ref_l, strict=True)] for a, ys in macro_l.items() if a != ref_name}, "+.3f")
            fig.add_hline(y=0, line=dict(color=ui.c("line-2"), width=1))
            ui.plot_layout(fig, 340)
            fig.update_layout(hovermode="x unified")
            fig.update_xaxes(title=dict(text="layer", font=dict(size=11.5)), tickvals=LAYERS)
            fig.update_yaxes(title=dict(text=f"Δ vs {by_name[ref_name].label}", font=dict(size=11.5)))
            ui.chart(fig, f"sc_layerd_{split}_{aset}_{ref_name}")
    ncol = min(4, len(fams))
    nrow = -(-len(fams) // ncol)
    fig = make_subplots(rows=nrow, cols=ncol, subplot_titles=fams, shared_yaxes=True,
                        horizontal_spacing=0.04, vertical_spacing=0.6 / max(nrow, 1) if nrow > 1 else 0.0)
    for i, f in enumerate(fams):
        layer_lines(fig, {a.name: CURVE[f, a.name] for a in scored if (f, a.name) in CURVE}, ".2f",
                    row=i // ncol + 1, col=i % ncol + 1)
    ui.plot_layout(fig, 230 * nrow)
    fig.update_layout(hovermode="x unified", margin=dict(l=8, r=8, t=36, b=8))
    fig.update_xaxes(tickvals=[20, 40, 60], ticktext=["L20", "L40", "L60"])
    fig.update_yaxes(range=[0, 1.02], dtick=0.5)
    for an in fig.layout.annotations:
        an.font = dict(family="IBM Plex Mono", size=12.5, color=ui.c("ink-2"))
    ui.label("Per family", "one panel per picked family")
    ui.chart(fig, f"sc_layerf_{split}_{aset}")


if PAIRED:
    ui.section("Change vs reference, per family", f"Paired item-level change against {by_name[ref_name].label}, "
               "95 % interval. A whisker that crosses 0 is not a difference." if not MANY else
               f"Paired item-level change against {by_name[ref_name].label}: green up, red down. The intervals are in "
               "the table below.")
    if not MANY:
        fig = go.Figure()
        for a in scored:
            if a.name == ref_name:
                continue
            xs, ys, lo, hi = [], [], [], []
            for f in fams:
                d = D.get((f, a.name))
                if d:
                    xs.append(f)
                    ys.append(d["d"])
                    lo.append(d["d"] - d["ci"][0])
                    hi.append(d["ci"][1] - d["d"])
            fig.add_trace(go.Bar(x=xs, y=ys, name=a.label, marker=dict(color=a.colour),
                                 error_y=dict(type="data", symmetric=False, array=hi, arrayminus=lo, thickness=1, width=2,
                                              color=ui.c("muted")),
                                 hovertemplate=f"<b>{ui.esc(a.label)}</b> %{{x}}: %{{y:+.3f}}<extra></extra>"))
        bar_layout(fig, 380, f"Δ pass vs {by_name[ref_name].label}")
        fig.add_hline(y=0, line=dict(color=ui.c("line-2"), width=1))
        ui.chart(fig, f"sc_famd_{split}_{ref_name}")
    else:
        heatmap(lambda f, a: D[f, a.name]["d"] if D.get((f, a.name)) and a.name != ref_name else None, fams, "+.2f", True,
                f"sc_hmd_{split}_{aset}_{ref_name}")

# ------------------------------------------------------------------ tables


def tag(a) -> str:
    return f'<span class="jm-armtag"><i style="background:{colour(a)}"></i>{ui.esc(a.label)}</span>'


def arm_cell(a) -> str:
    return (tag(a) + f'<br><span class="mono" style="color:var(--muted);font-size:11px">{ui.esc(a.name)} · '
            f'{ui.esc(STUDY[a.name])}</span>')


def f3(x, sign=False) -> str:
    return "–" if x is None else f"{x:+.3f}" if sign else f"{x:.3f}"


def best_in(col: list[float | None]) -> float | None:
    xs = [x for x in col if x is not None]
    return max(xs) if xs else None


ui.section("Pass per family", f"{split} · {metric}, best macro first. Bold: the best shown arm on that family. Hover "
           "a cell for its 95 % interval; “–”: not scored on that family.", eyebrow="Tables")
head = ["arm", *[f'<span class="mono">{f}</span>' for f in fams], "macro"]
best = {f: best_in([S[f, a.name]["v"] if S.get((f, a.name)) else None for a in scored]) for f in fams}


def pass_cell(f, a) -> str:
    s = S.get((f, a.name))
    if not s:
        return '<span style="color:var(--muted)">–</span>'
    txt = f"{s['v']:.2f}"
    return f'<span title="95 % CI {s["ci"][0]:.2f} to {s["ci"][1]:.2f}">{"<b>" + txt + "</b>" if s["v"] == best[f] else txt}</span>'


ui.table(head, [[arm_cell(a), *[pass_cell(f, a) for f in fams], f3(macro(a.name, fams))]
                for a in scored], num=set(range(1, len(head))))

if PAIRED:
    ui.section("Change vs reference", f"Paired, {metric}, against {by_name[ref_name].label}: the change and its 95 % "
               "interval. ▲ / ▼: the interval excludes 0.")

    def d_cell(f, a) -> str:
        if a.name == ref_name:
            return '<span style="color:var(--muted)">ref</span>'
        d = D.get((f, a.name))
        if not d:
            return '<span style="color:var(--muted)">–</span>'
        lo, hi = d["ci"]
        col = "--good" if lo > 0 else "--bad" if hi < 0 else "--ink-2"
        flag = " ▲" if lo > 0 else " ▼" if hi < 0 else ""
        return (f'<span style="color:var({col})">{d["d"]:+.2f}{flag}</span>'
                f'<br><span style="color:var(--muted);font-size:11px">[{lo:+.2f}, {hi:+.2f}]</span>')

    ui.table(head, [[arm_cell(a), *[d_cell(f, a) for f in fams],
                     "ref" if a.name == ref_name else f3(macro_change(a.name, fams), True)] for a in scored],
             num=set(range(1, len(head))))

st.caption(f"Generated from out/eval/*/{split}/summary.json"
           + (" and the newest full judge run per arm" if metric == "judged" else "")
           + ". Fit is where studies screen (most arms); val holds only each study's finalists and their controls; "
             "bench only the registered comparisons. The Leaderboard has every arm with the controls (masked pass, "
             "echo, next-token overlap).")
