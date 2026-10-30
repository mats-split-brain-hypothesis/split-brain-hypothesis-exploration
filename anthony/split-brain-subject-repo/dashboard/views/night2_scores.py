"""Night 2 scores: every arm the night's studies (S13-S25) put through the pipeline, on one split, ranked by the macro
change against a reference (fam by default) with a 95 % interval from a within-family item bootstrap. Splits: fit (where
the studies screened), val (finalists), the fresh val2 / val3 and their pool (S24's 607 items, as
experiments/s24_pool.py pools them), val2b and bench. Arms are attributed to studies by dashboard/nights.py.
Generated from out/eval/*/<split>/ (per-item passes, cached next to each bank)."""

import re

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

import catalog
import nights
import sources
import ui

NIGHT = "night-2"
N = nights.NIGHTS[NIGHT]
ui.header(
    "Overnight",
    f"{N.title} scores",
    f"Every method the night's studies tried ({N.dates}; LL has its own page), on one split: the macro change against "
    "a reference with its 95 % interval, the per-family changes, and the table behind them. Strict pass (the piece "
    "proxy on the multi-token families). Ours, not WorkspaceBench scores.",
)

PROMPT_READ = ("user_modeling", "directed_modulation")  # pass can come from reading the prompt (S11, U1)
STUDY_COLOURS = ["#3b63c9", "#0f8a77", "#b9781a", "#c2417a", "#6250d6", "#008300", "#e34948", "#5f6b7a", "#8a5a00",
                 "#1b8fb5", "#9b4fd0", "#d06a1f", "#4a7d2c", "#a05195", "#00a6a6"]
KINDS = {"label-free": "label-free", "supervised": "supervised (other families' targets)", "control": "controls"}

stamp = sources.stamp()
R = sources.results(stamp)
SS = nights.studies(NIGHT, stamp)
STUDY_COLOUR = {s: STUDY_COLOURS[i % len(STUDY_COLOURS)] for i, s in enumerate(SS)}
STUDY_COLOUR["reference"] = ui.c("muted")

# ------------------------------------------------------------------ controls
splits = [s for s in nights.splits(NIGHT) if nights.families_on(R, s)]
c1, c2, c3, c4 = st.columns([2.6, 0.9, 1.1, 2.2], vertical_alignment="bottom")
split = c1.segmented_control("Split", splits, default="val", key="n2_split",
                             help="fit: where the studies screened (most arms, fit references are leave-one-out @self). "
                                  "val: the finalists. val2 / val3: the fresh splits (typo / association / multihop), "
                                  f"read once each; {nights.POOLED}: both pooled within family (607 items). val2b: "
                                  "closed-answer subfamilies. bench: the registered reads.") or "val"
readout = c2.segmented_control("Readout", ["cos", "rms"], default="cos", key="n2_readout") or "cos"
FORMS = "strict + forms"
metric = c3.segmented_control("Score", ["strict", FORMS], default="strict", key="n2_metric",
                              help="strict: a top-10 token spells the target (the night's reports use strict). strict + "
                                   "forms: also its inflections and derived words (jlm.forms). Multi-token families keep "
                                   "the piece proxy.") or "strict"
forms = metric == FORMS
all_fams = nights.families_on(R, split)
fams = st.pills("Families in the score", all_fams, selection_mode="multi",
                default=[f for f in all_fams if f not in PROMPT_READ], key=f"n2_fams_{split}",
                help="The macro averages and every chart and table use only these families. Off by default: "
                     "user_modeling and directed_modulation, whose pass a centre can buy by reading the prompt.")
fams = [f for f in all_fams if f in (fams or [])]
if not fams:
    st.info("No families selected.")
    st.stop()

# arms: the night's (attributed by nights.member), the zero / fam references, and the matched-null seeds folded into one
names = {n for n in nights.arms_on(R, split, fams) if catalog.parse(n).readout == readout}
MEM = {}
for n in sorted(names):
    a = catalog.parse(n)
    if a.inner.startswith("famr:"):  # famr:<seed>:<inner>: the three seeds become one arm famr:*:<inner>
        n = re.sub(r"^famr:\d+:", "famr:*:", n)
        a = catalog.parse(n)
    if n in MEM:
        continue
    if (m := nights.member(a, NIGHT, stamp)) is not None:
        MEM[n] = (a, m)
if not MEM:
    st.info(f"No night-2 {readout} arms on {split}.")
    st.stop()

held_ref = "self" if split == "fit" else "fit"
refs = sorted(MEM, key=lambda n: (MEM[n][1].kind != "reference", MEM[n][0].sort_key))
ref_default = next((n for n in refs if MEM[n][0].centre == "fam" and MEM[n][0].ref == held_ref),
                   next((n for n in refs if MEM[n][0].centre == "fam"), refs[0]))


def label(n: str) -> str:
    a, m = MEM[n]
    if a.inner.startswith("famr:*:"):
        inner = catalog.parse(n.replace("famr:*:", "", 1))
        return f"Matched null (fam + random, 3 seeds) · {inner.label}"
    return a.label


ref_name = c4.selectbox("Reference (for the change)", refs, index=refs.index(ref_default),
                        format_func=lambda n: f"{label(n)} · {n}", key=f"n2_ref_{split}_{readout}")

present = sorted({s for _, m in MEM.values() for s in m.studies}, key=nights._order)
qp = st.query_params.get("study")
BEST, EVERY = "Best candidates", "Every method"
m1, m2 = st.columns([2.2, 4], vertical_alignment="bottom")
mode = m1.segmented_control("Show", [BEST, EVERY], default=EVERY if qp else BEST, key="n2_mode",
                            help="Best candidates: the night's finalists (studies/finalists-night2.md) beside the plain "
                                 "lens and the family mean. Every method: every arm the night's studies read, by study "
                                 "and kind.") or BEST
CAND: dict[str, nights.Candidate] = {}  # arm name -> candidate (best-candidates view)
if mode == BEST:
    t1, t2 = m2.columns(2)
    with_null = t1.toggle("With the matched nulls", value=False, key="n2_nulls",
                          help="fam plus a random direction with each supervised / label-free finalist's norm (C, S24; "
                               "3 seeds averaged): read on val2 / val3 only.")
    night_c, prior = nights.CANDIDATES[NIGHT], nights.PRIOR.get(NIGHT, ())
    missing = []
    for cand in (*night_c[:2], *prior, *night_c[2:]):  # zero, fam, the older references, then the night's candidates
        mine = [n for n, (a, _) in MEM.items() if cand.matches(a)]
        if not mine and cand in prior:
            missing.append(cand.short)
        pick = next((n for n in mine if MEM[n][0].ref in ("", held_ref)), next(iter(mine), None))
        if pick:
            CAND[pick] = cand
            if with_null and (null := f"famr:*:{pick}") in MEM:
                CAND[null] = nights.Candidate(f"null · {cand.short}", null, catalog._mix(cand.colour, "#ffffff", 0.55),
                                             what=nights.NULL_WHAT.format(x=cand.short), needs="fam + random")
    if ref_name not in CAND:
        CAND[ref_name] = nights.Candidate(label(ref_name), MEM[ref_name][0].centre, ui.c("muted"),
                                         what=ui.esc(MEM[ref_name][0].blurb))
    chosen = list(CAND)
    picked_studies = present
    with_prior = t2.toggle("With the older references", value=True, key="n2_prior",
                           help="Pilot-1's two best candidates (knnx8, pco16) and the plain J++ lens, wherever they "
                                "were read.")
    if not with_prior:
        CAND = {n: c for n, c in CAND.items() if c not in prior or n == ref_name}
    elif missing:
        st.caption(f"Not read on {split}: {', '.join(missing)} (pilot-1's arms and J++ were never read on the fresh "
                   "splits).")
    if len(CAND) <= 2:
        st.info(f"None of the night's best candidates was read on {split} ({readout}). Try val, or Every method.")
        st.stop()
if mode == EVERY:
    s1, s2, s3 = st.columns([3.2, 1.8, 1.4], vertical_alignment="bottom")
    picked_studies = s1.pills("Studies", present, selection_mode="multi",
                              default=[qp] if qp in present else present, key=f"n2_studies_{split}_{qp}",
                              format_func=lambda s: f"{s} · {SS[s]['instance']}" if s in SS else s,
                              help="An arm shows when it belongs to any picked study (a schedule of S14's and S20x's parts "
                                   "is in S14, S20x and S21). The letter is the instance that ran the study.")
    picked_kinds = s2.pills("Kinds", list(KINDS), selection_mode="multi", default=["label-free", "supervised"],
                            key="n2_kinds", format_func=lambda k: KINDS[k],
                            help="supervised: g holds other families' fit targets (S20x's corrections, S20u); the digest "
                                 "asks whether these count as centres. controls: shuf. / rand. / matched nulls / random "
                                 "subspaces.")
    flt = s3.text_input("Filter", placeholder="e.g. knnxd8l, sched:40", key="n2_filter").strip().lower()

    chosen = [n for n, (a, m) in MEM.items()
              if n == ref_name or m.kind == "reference"
              or (m.kind in (picked_kinds or []) and m.studies & set(picked_studies or []))]
    if flt:
        chosen = [n for n in chosen if n == ref_name or flt in n.lower() or flt in label(n).lower()]

# ------------------------------------------------------------------ scores
with st.spinner(f"Scoring {len(chosen)} arms on {split}…"):
    P = {n: {f: nights.passes(R, f, split, n, forms) for f in fams} for n in chosen}
REF = P[ref_name]
if not any(REF.values()):
    st.info(f"The reference {label(ref_name)} has no per-item scores on {split} for the picked families.")
    st.stop()


def rate(p: dict | None) -> float | None:
    return float(np.mean(list(p.values()))) if p else None


ROWS = []
for n in chosen:
    pf = {f: rate(P[n][f]) for f in fams}
    got = [f for f in fams if pf[f] is not None]
    if not got:
        continue
    ch = nights.macro_change(P[n], REF, fams) if n != ref_name else {"d": 0.0, "ci": [0.0, 0.0], "per": {f: 0.0 for f in got}, "n": len(got)}
    ROWS.append({"name": n, "arm": MEM[n][0], "m": MEM[n][1], "pass": pf, "macro": float(np.mean([pf[f] for f in got])),
                 "cov": len(got), "ch": ch})
full = [r for r in ROWS if r["cov"] == len(fams) and r["ch"]]
part = [r for r in ROWS if r not in full]
full.sort(key=lambda r: r["ch"]["d"], reverse=True)
part.sort(key=lambda r: (r["cov"], r["macro"]), reverse=True)
ROWS = full + part
if not full:
    st.info("No chosen arm is scored on every picked family: narrow the families.")
    st.stop()

if mode == BEST:
    nlab = {r["name"]: CAND[r["name"]].short + (" (sup.)" if r["m"].kind == "supervised" else "") for r in ROWS}
else:
    nlab = {r["name"]: (("sup. · " if r["m"].kind == "supervised" else "") + label(r["name"])) for r in ROWS}


def colour(r: dict) -> str:
    return CAND[r["name"]].colour if mode == BEST else STUDY_COLOUR.get(r["m"].study, ui.c("muted"))


if mode == BEST:
    st.html('<div class="jm-legend">' + "".join(
        f'<span title="{ui.esc(label(r["name"]) + " · " + r["name"])}"><i style="background:{colour(r)}"></i>'
        f'{ui.esc(nlab[r["name"]])}</span>' for r in sorted(full, key=lambda r: list(CAND).index(r["name"]))) + "</div>")
    st.caption(f"{len(full)} of the night's best candidates scored on all {len(fams)} picked families"
               + (f"; {len(part)} on fewer (table only)" if part else "")
               + f". “(sup.)”: supervised (other families' fit targets inside g). Reference: {label(ref_name)}. "
                 "Hover a legend entry for the full name.")
else:
    here = [s for s in SS if any(r["m"].study == s for r in full)] + (["reference"] if any(r["m"].kind == "reference" for r in full) else [])
    st.html('<div class="jm-legend">' + "".join(
        f'<span><i style="background:{STUDY_COLOUR[s]}"></i>{ui.esc(s if s == "reference" else f"{s} · {SS[s]["title"]}")}</span>'
        for s in here) + "</div>")
    st.caption(f"{len(full)} arms scored on all {len(fams)} picked families"
               + (f"; {len(part)} on fewer (table only)" if part else "")
               + f". Colour: the arm's study. “sup.”: supervised. Reference: {label(ref_name)}.")

# ------------------------------------------------------------------ what each arm is
ARM_HEAD = ["arm", "mechanism (every arm reads J<sub>l</sub>(h − g))", "g built from"]


def what_row(r: dict) -> list[str]:
    tag = (f'<span class="jm-armtag"><i style="background:{colour(r)}"></i>{ui.esc(nlab[r["name"]])}</span><br>'
           f'<span class="mono" style="color:var(--muted);font-size:10.5px">{ui.esc(r["name"])}</span>')
    if mode == BEST:
        c = CAND[r["name"]]
        return [tag, c.what or ui.esc(r["arm"].blurb), c.needs or "–"]
    a, m = r["arm"], r["m"]
    if a.inner.startswith("famr:*:"):
        what = nights.NULL_WHAT.format(x=ui.esc(catalog.parse(r["name"].replace("famr:*:", "", 1)).label))
    else:
        what = ui.esc(a.blurb)
    return [tag, what, {"supervised": "<b>other families' fit targets</b>", "reference": "–"}.get(m.kind, m.kind)]


if mode == BEST:
    ui.section("What each arm does", "The mechanism behind every arm shown, in the night's own terms. L40 is the layer "
               "where the schedules switch (centring acts at L ≥ 40, S17).", eyebrow="Arms")
    ui.table(ARM_HEAD, [what_row(r) for r in sorted(ROWS, key=lambda r: list(CAND).index(r["name"]))])
else:
    with st.expander(f"What each arm does ({len(ROWS)} arms)"):
        ui.table(ARM_HEAD, [what_row(r) for r in ROWS])

# ------------------------------------------------------------------ charts
ui.section("Macro change vs reference", f"{split} · {readout} · {metric} · mean over the {len(fams)} picked families of "
           f"each family's paired change against {label(ref_name)}, best first; whiskers: 95 % interval from resampling "
           "items within each family (2,000 draws). A whisker that crosses 0 is not a difference.", eyebrow="Charts")


def ranked(rows: list[dict], key: str, height_per: int):
    rows = rows[::-1]
    ys = [nlab[r["name"]] for r in rows]
    xs = [r["ch"]["d"] for r in rows]
    lo = [r["ch"]["d"] - r["ch"]["ci"][0] for r in rows]
    hi = [r["ch"]["ci"][1] - r["ch"]["d"] for r in rows]
    cols = [colour(r) for r in rows]
    fig = go.Figure(go.Bar(
        y=list(range(len(rows))), x=xs, orientation="h", marker=dict(color=cols, line=dict(width=0)),
        error_x=dict(type="data", symmetric=False, array=hi, arrayminus=lo, thickness=1, width=2, color=ui.c("muted")),
        customdata=[[ys[i], r["name"], r["ch"]["ci"][0], r["ch"]["ci"][1], r["m"].study, r["macro"]] for i, r in enumerate(rows)],
        hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<br>Δ %{x:+.3f} [%{customdata[2]:+.3f}, "
                      "%{customdata[3]:+.3f}] · pass %{customdata[5]:.3f} · %{customdata[4]}<extra></extra>"))
    fig.add_vline(x=0, line=dict(color=ui.c("line-2"), width=1))
    ui.plot_layout(fig, 70 + height_per * len(rows))
    fig.update_layout(bargap=0.3, margin=dict(r=24))
    fig.update_yaxes(tickvals=list(range(len(rows))), ticktext=[y if len(y) <= 70 else y[:67] + "…" for y in ys],
                     automargin=True, tickfont=dict(size=11, color=ui.c("ink-2")))
    fig.update_xaxes(title=dict(text=f"Δ pass vs {label(ref_name)}", font=dict(size=11.5)), tickformat="+.2f")
    ui.chart(fig, key)


left, right = st.columns([1.7, 1] if mode == EVERY else [1, 1], gap="large")
with left:
    ui.label("Every arm" if mode == EVERY else "Best candidates", f"{len(full)} arms")
    ranked(full, f"n2_rank_{mode}_{split}_{readout}_{metric}_{ref_name}_{len(full)}",
           22 if len(full) <= 40 else 17 if mode == EVERY else 30)
if mode == BEST:
    with right:
        ui.label("Macro pass", f"mean pass over the {len(fams)} picked families")
        rows = sorted(full, key=lambda r: r["macro"])
        fig = go.Figure(go.Bar(
            y=[nlab[r["name"]] for r in rows], x=[r["macro"] for r in rows], orientation="h",
            marker=dict(color=[colour(r) for r in rows]), text=[f'{r["macro"]:.3f}' for r in rows], textposition="outside",
            textfont=dict(size=10.5), cliponaxis=False, hovertemplate="%{y}: %{x:.3f}<extra></extra>"))
        ui.plot_layout(fig, 70 + 30 * len(rows))
        fig.update_layout(bargap=0.3, margin=dict(r=44))
        fig.update_yaxes(automargin=True, tickfont=dict(size=11.5, color=ui.c("ink-2")))
        fig.update_xaxes(title=dict(text="pass", font=dict(size=11.5)), rangemode="tozero")
        ui.chart(fig, f"n2_macro_{split}_{readout}_{metric}")
else:
    with right:
        best = {}
        for r in full:
            if r["m"].kind in ("label-free", "supervised") and r["name"] != ref_name:
                for s in r["m"].studies & set(picked_studies or []):
                    if s not in best or r["ch"]["d"] > best[s]["ch"]["d"]:
                        best[s] = r
        ui.label("Best of each study", "highest macro change among the study's non-control arms")
        if best:
            order = sorted(best, key=lambda s: best[s]["ch"]["d"], reverse=True)
            rows = [best[s] for s in order]
            fig = go.Figure(go.Bar(
                y=[f"{s} · {SS[s]['title'][:34]}" if s in SS else s for s in order][::-1], x=[r["ch"]["d"] for r in rows][::-1],
                orientation="h", marker=dict(color=[STUDY_COLOUR.get(s, ui.c("muted")) for s in order][::-1]),
                error_x=dict(type="data", symmetric=False, array=[r["ch"]["ci"][1] - r["ch"]["d"] for r in rows][::-1],
                             arrayminus=[r["ch"]["d"] - r["ch"]["ci"][0] for r in rows][::-1], thickness=1, width=2,
                             color=ui.c("muted")),
                customdata=[[nlab[r["name"]], sum(1 for x in full if s in x["m"].studies and x["m"].kind != "control")]
                            for s, r in zip(order, rows, strict=True)][::-1],
                hovertemplate="%{y}<br>best: %{customdata[0]}<br>Δ %{x:+.3f} · %{customdata[1]} arms tried<extra></extra>"))
            fig.add_vline(x=0, line=dict(color=ui.c("line-2"), width=1))
            ui.plot_layout(fig, 70 + 30 * len(order))
            fig.update_layout(bargap=0.3)
            fig.update_yaxes(automargin=True, tickfont=dict(size=11.5, color=ui.c("ink-2")))
            fig.update_xaxes(title=dict(text=f"Δ vs {label(ref_name)}", font=dict(size=11.5)), tickformat="+.2f")
            ui.chart(fig, f"n2_best_{split}_{readout}_{metric}_{ref_name}")
            ui.table(["study", "best arm", "Δ", "arms"],
                     [[f'<a href="/study?study={s}" target="_self">{s}</a>', ui.esc(nlab[best[s]["name"]]),
                       f'{best[s]["ch"]["d"]:+.3f}',
                       str(sum(1 for x in full if s in x["m"].studies and x["m"].kind != "control"))] for s in order],
                     num={2, 3})
        else:
            st.caption("No non-control arms among the chosen.")


if mode == BEST:
    ui.section("Family by family", f"{split} · {readout} · {metric} · one panel per picked family, one bar per candidate "
               "(same order and colours in every panel); whiskers: the item-bootstrap 95 % interval. "
               "On Pass, the dashed line is the reference's pass.")
    show = st.segmented_control("Bars", ["Pass", "Change vs reference"], default="Pass", key="n2_fambars",
                                help=f"Pass: each candidate's pass on the family. Change: the paired change against "
                                     f"{label(ref_name)} on the family's items.") or "Pass"
    delta = show != "Pass"
    order = [r for r in sorted(full, key=lambda r: list(CAND).index(r["name"])) if not (delta and r["name"] == ref_name)]
    ncol = min(3, len(fams))
    nrow = -(-len(fams) // ncol)
    n_items = {f: len(REF.get(f) or {}) for f in fams}
    fig = make_subplots(rows=nrow, cols=ncol, shared_yaxes=False, horizontal_spacing=0.05,
                        vertical_spacing=0.32 / nrow if nrow > 1 else 0.0,
                        subplot_titles=[f"{f} · {n_items[f]} items" for f in fams])
    for i, f in enumerate(fams):
        rc = dict(row=i // ncol + 1, col=i % ncol + 1)
        ys, lo, hi = [], [], []
        for r in order:
            v = (nights.per_family_ci(P[r["name"]][f], REF[f]) if delta else nights.rate_ci(P[r["name"]][f])) \
                if P[r["name"]].get(f) and (not delta or REF.get(f)) else None
            ys.append(v[0] if v else None)
            lo.append(v[0] - v[1] if v else 0)
            hi.append(v[2] - v[0] if v else 0)
        xs = [nlab[r["name"]] for r in order]
        fig.add_trace(go.Bar(
            x=xs, y=ys, marker=dict(color=[colour(r) for r in order], line=dict(width=0)),
            error_y=dict(type="data", symmetric=False, array=hi, arrayminus=lo, thickness=1, width=2, color=ui.c("muted")),
            customdata=[[label(r["name"]), y - l if y is not None else 0, y + h if y is not None else 0]
                        for r, y, l, h in zip(order, ys, lo, hi, strict=True)],
            hovertemplate=f"<b>{f}</b> · %{{x}}<br>%{{customdata[0]}}<br>%{{y:{'+.3f' if delta else '.3f'}}} "
                          "[%{customdata[1]:.3f}, %{customdata[2]:.3f}]<extra></extra>"), **rc)
        if delta:
            fig.add_hline(y=0, line=dict(color=ui.c("line-2"), width=1), **rc)
        elif (rv := nights.rate_ci(REF.get(f))) is not None:
            fig.add_hline(y=rv[0], line=dict(color=ui.c("muted"), width=1, dash="dash"), **rc)
    ui.plot_layout(fig, 300 * nrow)
    fig.update_layout(bargap=0.18, margin=dict(l=8, r=8, t=36, b=8))
    fig.update_xaxes(tickangle=-40, tickfont=dict(size=10.5, color=ui.c("ink-2")))
    if delta:
        fig.update_yaxes(tickformat="+.2f", zeroline=False)
    else:
        fig.update_yaxes(range=[0, 1.05], dtick=0.25)
    for an in fig.layout.annotations:
        an.font = dict(family="IBM Plex Mono", size=12.5, color=ui.c("ink-2"))
    ui.chart(fig, f"n2_fams_{split}_{readout}_{metric}_{ref_name}_{show}_{len(order)}")

if mode == EVERY:
    ui.section("Change per family", f"Paired change against {label(ref_name)} on each picked family (rows as above). "
               "Green up, red down; the macro column is the bar above.")
    rows = full[::-1]
    z = [[r["ch"]["per"].get(f) for f in fams] + [r["ch"]["d"]] for r in rows]
    m_abs = max([abs(v) for row in z for v in row if v is not None] + [0.05])
    fig = go.Figure(go.Heatmap(
        z=z, x=[*fams, "macro"], y=list(range(len(rows))), colorscale=[[0, ui.c("bad")], [0.5, ui.c("bg")], [1, ui.c("good")]],
        zmin=-m_abs, zmax=m_abs, xgap=1, ygap=1, showscale=False, hoverongaps=False,
        text=[[f"{v:+.2f}" if v is not None else "" for v in row] for row in z], texttemplate="%{text}", textfont=dict(size=10),
        customdata=[[nlab[r["name"]]] * (len(fams) + 1) for r in rows],
        hovertemplate="%{customdata}<br>%{x}: %{text}<extra></extra>"))
    ui.plot_layout(fig, 90 + (22 if len(rows) <= 40 else 17) * len(rows))
    fig.update_xaxes(side="top", tickangle=-30, tickfont=dict(size=11))
    ys = [nlab[r["name"]] for r in rows]
    fig.update_yaxes(tickvals=list(range(len(rows))), ticktext=[y if len(y) <= 70 else y[:67] + "…" for y in ys],
                     automargin=True, tickfont=dict(size=11, color=ui.c("ink-2")))
    ui.chart(fig, f"n2_hm_{split}_{readout}_{metric}_{ref_name}_{len(rows)}")

# ------------------------------------------------------------------ table
READ_ON = [s for s in nights.splits(NIGHT) if s not in (split, nights.POOLED)]


def read_on(n: str) -> str:
    """The other splits this arm (a matched null: any of its seeds) was read on."""
    pat = re.compile("^" + re.escape(n).replace(r"famr:\*:", r"famr:\d+:") + "$")
    hit = [s for s in READ_ON if any(pat.match(a) for f in sources.ALL_FAMILIES for a in R.get(f, {}).get(s, {}).get("arms", {}))]
    return " ".join(hit) or "–"


def tag(r) -> str:
    col = STUDY_COLOUR.get(r["m"].study, ui.c("muted"))
    return (f'<span class="jm-armtag"><i style="background:{col}"></i>{ui.esc(label(r["name"]))}</span><br>'
            f'<span class="mono" style="color:var(--muted);font-size:11px">{ui.esc(r["name"])}</span>')


def d_cell(r) -> str:
    if r["name"] == ref_name:
        return '<span style="color:var(--muted)">ref</span>'
    c = r["ch"]
    if not c:
        return "–"
    lo, hi = c["ci"]
    col = "--good" if lo > 0 else "--bad" if hi < 0 else "--ink-2"
    flag = " ▲" if lo > 0 else " ▼" if hi < 0 else ""
    return (f'<span style="color:var({col})">{c["d"]:+.3f}{flag}</span><br>'
            f'<span style="color:var(--muted);font-size:11px">[{lo:+.3f}, {hi:+.3f}]</span>')


def fam_cell(r, f) -> str:
    v = r["pass"].get(f)
    if v is None:
        return '<span style="color:var(--muted)">–</span>'
    d = (r["ch"] or {}).get("per", {}).get(f)
    col = "--good" if d and d > 0 else "--bad" if d and d < 0 else "--muted"
    return f'{v:.2f}' + (f'<br><span style="color:var({col});font-size:11px">{d:+.2f}</span>' if d is not None and r["name"] != ref_name else "")


ui.section("Every arm", f"{split} · {readout} · {metric}. Per family: the pass, and under it the change against "
           f"{label(ref_name)}. ▲ / ▼: the macro interval excludes 0. “read on”: the other splits that read this arm. "
           "Arms scored on fewer families come last, averaged over those only.", eyebrow="Table")
head = ["arm", "study", "kind", *[f'<span class="mono">{f}</span>' for f in fams], "macro pass", "macro Δ [95 %]", "read on"]
ui.table(head, [[tag(r), " ".join(f'<a href="/study?study={s}" target="_self">{s}</a>' for s in sorted(r["m"].studies, key=nights._order)) or "–",
                 r["m"].kind, *[fam_cell(r, f) for f in fams], f'{r["macro"]:.3f}' + (f" ({r['cov']}/{len(fams)})" if r["cov"] < len(fams) else ""),
                 d_cell(r), read_on(r["name"])] for r in ROWS],
         num=set(range(3, 3 + len(fams) + 2)))

st.caption(f"Generated from out/eval/*/{split if split != nights.POOLED else 'val2, val3'}/ per-item passes "
           "(sources.item_passes). Studies: dashboard/nights.py attributes each arm from its card and its centre's "
           "jlm.mu module. Judged scores (val, Haiku) are on Loop → Scores; the night's own tables are in "
           "studies/finalists-night2.md.")
