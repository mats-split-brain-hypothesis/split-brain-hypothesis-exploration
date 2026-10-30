"""J++ x our finalists (2026-10-12): the night-2 finalist centres (S24 / S24d arm list) read through the J-lens and the
J++ map, (A) on the J++ paper's five held-out readout evals, scored by the paper's rule (experiments/jpp_finalists.py
-> out/analysis/jpp-finalists/scores.json), and (B) on our val split, strict pass@10 (experiments/jobs/
jpp_finalists_val.sh -> out/eval/<family>/val/summary.json). Every number is read from out/ on load; B's cells show
as pending until its run has written them.
"""

import json
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

import sources
import ui

OUT = sources.REPO_ROOT / "out"
JPP = "J<sup>++</sup>"
EVALS = ["multihop", "multilingual", "typo", "association", "poetry"]
#: Part A arm keys -> label; the order is the chart's.
A_ARMS = [("zero", "plain (no centre)"), ("fam", "fam"), ("ref", "ref (J++ fit-split mean)"), ("S14k", "S14k"),
          ("S14b", "S14b"), ("S14b-knnxs8", "S14b-knnxs8"), ("S14bL", "S14bL"), ("S20x", "S20x"), ("s20xon", "s20xon"),
          ("S21b", "S21b"), ("glosb:desc", "blind entry (desc)"), ("glosb:word", "blind entry (word)"),
          ("rand.S14bL", "rand. S14bL"), ("rand.S20x", "rand. S20x")]
#: Part B: label -> (J-lens arm, J++ arm), per readout. rms uses the rms-fitted S20x corrections where they exist.
B = "s14:template:64:mean=kmx64:a=0.5"
S14BL = "sched:40:kmx64+s14:template:64:mean=knnxd8l:a=0.5"
B_ARMS = {
    "cos": [("plain (no centre)", "zero|cos"), ("fam", "fam@fit|cos"), ("S14k", "sched:40:kmx64+s14t64@fit|cos"),
            ("S14b", f"sched:40:kmx64+{B}@fit|cos"), ("S14b-knnxs8", "sched:40:kmx64+s14:template:64:mean=knnxs8:a=0.5@fit|cos"),
            ("S14bL", f"{S14BL}@fit|cos"), ("S20x", "s20xt:1@fit|cos"), ("s20xon", "s20xon:1:kmx64@fit|cos"),
            ("S21b", f"sched:40:s20xon:1:kmx64+{B}@fit|cos"), ("rand. S14bL", f"rand.{S14BL}@fit|cos"),
            ("rand. S20x", "rand.s20xt:1@fit|cos")],
    "rms": [("plain (no centre)", "zero|rms"), ("fam", "fam@fit|rms"), ("S14k", "sched:40:kmx64+s14t64@fit|rms"),
            ("S14bL", f"{S14BL}@fit|rms"), ("S20x", "s20xtrms:1@fit|rms"), ("s20xon", "s20xonrms:1:kmx64@fit|rms"),
            ("S21b", f"sched:40:s20xonrms:1:kmx64+{B}@fit|rms")],
}
FAMS = sources.ALL_FAMILIES
SINGLE = ["typo", "association", "basic_readout", "multihop", "multilingual"]
SHORT = {"typo": "typo", "association": "assoc.", "basic_readout": "basic", "multihop": "multihop",
         "multilingual": "multiling.", "user_modeling": "user mod.", "directed_modulation": "dir. mod.",
         "typo_mt": "typo_mt", "multihop_mt": "mhop_mt", "basic_readout_mt": "basic_mt", "multilingual_mt": "mling_mt"}
#: The post's numbers (rms, held-out macro recall@10), as recorded in umot's research log (upstream) on 2026-10-10.
POST = {"logit": 0.311, "jlens": 0.357, "jpp": 0.552}


def _mtime(p: Path) -> float:
    return p.stat().st_mtime if p.exists() else 0.0


@st.cache_data(show_spinner=False)
def _json(path: str, _mt: float):
    return json.loads(Path(path).read_text())


def load_a():
    p = OUT / "analysis" / "jpp-finalists" / "scores.json"
    return _json(str(p), _mtime(p))["result"] if p.exists() else None


@st.cache_data(show_spinner=False)
def strict(arm: str, _stamp: float) -> dict[str, float | None]:
    out = {}
    for f in FAMS:
        p = OUT / "eval" / f / "val" / "summary.json"
        a = json.loads(p.read_text())["result"]["arms"].get(arm) if p.exists() else None
        out[f] = a["strict"]["value"] if a and "strict" in a else None
    return out


def stamp() -> float:
    return max(_mtime(OUT / "eval" / f / "val" / "summary.json") for f in FAMS)


def mean(xs):
    return None if not xs or None in xs else sum(xs) / len(xs)


def f3(x, missing: str = '<span class="c-mu">pending</span>') -> str:
    return missing if x is None else f"{x:.3f}"


def pts(x) -> str:
    return "–" if x is None else f"{100 * x:+.1f}"


def ci(d) -> str:
    return "–" if d is None else f"{100 * d[0]:+.1f} <span style='color:var(--muted)'>[{100 * d[1]:+.1f}, {100 * d[2]:+.1f}]</span>"


#: Categorical slots (the dataviz palette views/pca.py uses), light / dark.
CAT = [("#2a78d6", "#3987e5"), ("#eb6834", "#d95926"), ("#1baf7a", "#199e70"), ("#eda100", "#c98500"),
       ("#e87ba4", "#d55181"), ("#008300", "#008300"), ("#6250d6", "#9085e9"), ("#e34948", "#e66767")]


#: The J++ paper's Figure 1 colours (sampled from its assets/figure1.png): J-lens grey, J++ blue, R-lens orange, logit
#: light grey. Our centred lens gets a green the figure does not use (supervised S20x) and a reddish purple (label-free
#: S14b-knnxs8). Night mode lifts the dark grey for contrast.
MAPC = {"jlens": ("#4d4d4d", "#9a9a9a"), "jpp": ("#0072b2", "#2b95d6"), "rlens": ("#d97b00", "#e8901a"),
        "logit": ("#aaaaaa", "#6e6e6e"), "ours": ("#009e73", "#1fbf8f"), "ours_lf": ("#b5528c", "#d47fb0"),
        "ours_blind": ("#c9a000", "#e6bc1f")}


def mapc(k: str) -> str:
    return MAPC[k][1 if ui.night() else 0]


def cat(k: int) -> str:
    return CAT[k % 8][1 if ui.night() else 0]


def per_category(cats: list[str], labels: list[str], series: dict[str, list], key: str, title: str, all_labels: list[str]):
    """Grouped bars: one group per category, one bar per centre (colour fixed by the centre's place in all_labels)."""
    fig = go.Figure()
    for lab in labels:
        ys = series[lab]
        fig.add_trace(go.Bar(x=cats, y=ys, name=lab, marker_color=cat(all_labels.index(lab)),
                             hovertemplate=f"{lab}<br>%{{x}}: %{{y:.3f}}<extra></extra>"))
    ui.plot_layout(fig, 340)
    fig.update_layout(barmode="group", bargap=0.2, bargroupgap=0.05, showlegend=True,
                      legend=dict(orientation="h", y=1.14, x=0), title=dict(text=title, x=0, y=0.99, font=dict(size=13)))
    fig.update_yaxes(range=[0, 1.05])
    ui.chart(fig, key)


A = load_a()
ui.header(
    "J++ × our finalists · 2026-10-12",
    "Does centring add anything to J<sup>++</sup>?",
    f"The night-2 finalist centres, read through the released J-lens and through {JPP} (Ayonrinde &amp; Lindsey 2026). "
    f"(A) on the {JPP} paper's own five readout evals, scored by its rule; (B) on our val split, strict pass@10. "
    "No new forward pass: both read stored states.",
)
if A is None:
    st.info("No out/analysis/jpp-finalists/scores.json yet: run experiments/jpp_finalists.py.")
    st.stop()
S = A["scores"]
D = A["diffs"]


def a_score(lens, arm, ro, key="macro", layers="grid11"):
    v = S.get(f"{lens}|{arm}|{ro}|{layers}")
    return None if v is None else v[key]


best_j = max((a for a, _ in A_ARMS if a != "zero" and not a.startswith("rand")), key=lambda a: a_score("jlens", a, "rms") or 0)
best_p = max((a for a, _ in A_ARMS if a != "zero" and not a.startswith("rand")), key=lambda a: a_score("jpp", a, "rms") or 0)
pj0, pp0 = a_score("jlens", "zero", "rms"), a_score("jpp", "zero", "rms")
st.html('<div class="jm-stats">'
        f'<div class="jm-stat"><span class="v c-d">{pj0:.3f} → {a_score("jlens", best_j, "rms"):.3f}</span><span class="l">J-lens, plain → best centre ({best_j}); {JPP} evals, rms</span></div>'
        f'<div class="jm-stat"><span class="v c-h">{pp0:.3f}</span><span class="l">plain {JPP} on the same layers: above every centred J-lens</span></div>'
        f'<div class="jm-stat"><span class="v c-mu">{pts(a_score("jpp", best_p, "rms") - pp0)} pts</span><span class="l">best centred {JPP} ({best_p}) vs plain {JPP}, rms</span></div>'
        "</div>")
left, right = st.columns(2, gap="large")
left.html(ui.note("key", f"On the {JPP} evals",
                  "Every finalist beats fam and its random-direction control through the J-lens, so the centres "
                  f"transfer to prompts they were not chosen on. None reaches plain {JPP}, and centring {JPP} itself "
                  "costs it with the paper's rms readout. The S14 arms' smaller loss is matched by their random "
                  "controls, so it is not their content."))
right.html(ui.note("open", "Read with these caveats",
                   f"Centres read on our capture layers 20–56 (11); the paper's are 8–56 step 8. Reference pool: our "
                   f"WorkspaceBench fit captures (poetry, which has none, gets the pooled mean). The S14 template bases "
                   f"and S20x corrections are fitted through the J-lens and reused unchanged through {JPP}."))

# ------------------------------------------------------------------ headline
_h = OUT / "analysis" / "jpp-finalists" / "headline.json"
if _h.exists():
    H = _json(str(_h), _mtime(_h))["scores"]
    left, right = st.columns([1.2, 1], gap="large")
    with left:
        ro_h = st.segmented_control("Readout  ", ["rms", "cos"], default="rms", key="jf_ro_h",
                                    help="rms is the paper's readout (final norm, then W_U); cos is the bench's.") or "rms"
        bars = [("J-Lens", "jlens", "jlens"),
                ("J-Lens, μ = texts the model wrote<br>from a one-line task description", "jlens+glosb", "ours_blind"),
                ("J-Lens, μ = closest 8 points<br>+ template directions removed", "jlens+s14b-knnxs8u", "ours_lf"),
                ("J-Lens, fitted μ<br>(fit on the same data as J++)", "jlens+s20x-jpp", "ours"), (f"J++ Lens", "jpp", "jpp")]
        bars = [b for b in bars if f"{b[1]}|{ro_h}" in H]  # an older headline.json lacks the later arms
        ys = [H[f"{k}|{ro_h}"]["macro"] for _, k, _ in bars]
        fig = go.Figure(go.Bar(
            x=[b[0] for b in bars], y=[100 * y[0] for y in ys], marker_color=[mapc(c) for _, _, c in bars], width=0.62,
            error_y=dict(type="data", symmetric=False, array=[100 * (y[2] - y[0]) for y in ys],
                         arrayminus=[100 * (y[0] - y[1]) for y in ys], color=ui.c("ink"), thickness=1.5, width=7),
            text=[f"{100 * y[0]:.1f}" for y in ys], textposition="outside", textfont=dict(size=15, color=ui.c("ink")),
            hovertemplate="%{x}: %{y:.1f}<extra></extra>"))
        ui.plot_layout(fig, 400)
        fig.update_layout(bargap=0.3, uniformtext=dict(minsize=12, mode="show"))
        fig.update_xaxes(tickfont=dict(size=14, color=ui.c("ink")), showgrid=False)
        fig.update_yaxes(title="Recall@10 (%)", range=[0, 75], dtick=10, title_font=dict(size=14))
        ui.chart(fig, f"jf_headline_{ro_h}")
    with right:
        st.write("")
        st.write("")
        st.html(ui.note("key", "One centre closes most of the gap",
                        f"Held-out recall@10 on the {JPP} paper's five readout evals (macro), read on our 11 capture layers. "
                        f"S20x refitted leave-one-eval-out on {JPP}'s own fit split lifts the J-lens from "
                        f"{100 * H['jlens|' + ro_h]['macro'][0]:.1f} to {100 * H['jlens+s20x-jpp|' + ro_h]['macro'][0]:.1f}; "
                        f"plain {JPP} reads {100 * H['jpp|' + ro_h]['macro'][0]:.1f}. S20x learns from the other evals' "
                        "fit-split answers (supervised). "
                        + (f"With no answers at all, S14b-knnxs8 (template removal, then half the mean of the 8 nearest "
                           f"fit cells of another carrier; pool: our fit cells plus {JPP}'s) reads "
                           f"{100 * H['jlens+s14b-knnxs8u|' + ro_h]['macro'][0]:.1f}. "
                           if f"jlens+s14b-knnxs8u|{ro_h}" in H else "")
                        + (f"With no data from the task at all, μ = the mean final-token state of 64 texts the model wrote "
                           f"from a glossary entry it wrote itself from one sentence of the benchmark's README (x13's blind "
                           f"entry; poetry, which has no README, gets the mean of the five single-token families' sets) reads "
                           f"{100 * H['jlens+glosb|' + ro_h]['macro'][0]:.1f}. "
                           if f"jlens+glosb|{ro_h}" in H else "")
                        + "Error bars: 95 % bootstrap, items resampled within eval."))
        st.caption(f"Colours follow the {JPP} paper's Figure 1 (J-lens grey, {JPP} blue); purple is the J-lens centred on "
                   "the 8 closest points with template directions removed (no labels), yellow the J-lens centred on the mean "
                   "state of 64 texts the model wrote from a task description it wrote itself from one sentence of the "
                   "benchmark's README (no data from the task), green the J-lens with a fitted μ "
                   f"(fitted on the same data {JPP} was fitted on).")
    fig = go.Figure()
    for lab, k, c in bars:
        v = [H[f"{k}|{ro_h}"][e] for e in EVALS]
        fig.add_trace(go.Bar(
            x=EVALS, y=[100 * y[0] for y in v], name=lab.replace("<br>", " "), marker_color=mapc(c),
            error_y=dict(type="data", symmetric=False, array=[100 * (y[2] - y[0]) for y in v],
                         arrayminus=[100 * (y[0] - y[1]) for y in v], color=ui.c("ink"), thickness=1.2, width=4),
            text=[f"{100 * y[0]:.0f}" for y in v], textposition="outside", textfont=dict(size=11.5, color=ui.c("ink-2")),
            hovertemplate=f"{lab.replace('<br>', ' ')}<br>%{{x}}: %{{y:.1f}}<extra></extra>"))
    ui.plot_layout(fig, 380)
    fig.update_layout(barmode="group", bargap=0.5, bargroupgap=0.15, showlegend=True,
                      legend=dict(orientation="h", y=1.12, x=0, font=dict(size=13)), uniformtext=dict(minsize=10, mode="show"))
    fig.update_xaxes(tickfont=dict(size=14, color=ui.c("ink")), showgrid=False)
    fig.update_yaxes(title="Recall@10 (%)", range=[0, 112], dtick=20)
    ui.chart(fig, f"jf_headline_evals_{ro_h}")
    st.caption("Per eval, same arms and readout as above; 95 % bootstrap intervals, items resampled within the eval. "
               "Poetry has no WorkspaceBench counterpart and is the hardest eval for every lens.")

# ------------------------------------------------------------------ A
ui.section(f"A · The {JPP} paper's readout evals",
           "Held-out recall@10 (329 items), Readout Filtering, min rank over layers. Macro over the five evals, or "
           "over the four with a WorkspaceBench counterpart (poetry left out).", eyebrow="A · Their evals")
c1, c2, _ = st.columns([1, 1, 3])
ro = c1.segmented_control("Readout", ["rms", "cos"], default="rms", key="jf_ro",
                          help="rms is the paper's (final norm, then W_U); cos is the bench's.") or "rms"
key = c2.segmented_control("Macro", ["macro", "macro4"], default="macro", key="jf_macro",
                           format_func=lambda k: {"macro": "5 evals", "macro4": "4 (no poetry)"}[k]) or "macro"

left, right = st.columns([1.4, 1], gap="large")
with left:
    labels = [lab for _, lab in A_ARMS]
    fig = go.Figure()
    for lens, name, tok in (("jlens", "J-lens", "jlens"), ("jpp", "J++", "jpp")):
        ys = [a_score(lens, a, ro, key) for a, _ in A_ARMS]
        fig.add_trace(go.Bar(x=labels, y=ys, name=name, marker_color=mapc(tok),
                             text=[f"{y:.2f}" if y is not None else "" for y in ys], textposition="outside",
                             textfont=dict(size=10.5, color=ui.c("ink-2"))))
    fig.add_hline(y=a_score("jpp", "zero", ro, key), line=dict(color=mapc("jpp"), dash="dot", width=1.5),
                  annotation_text="plain J++", annotation_position="top right")
    ui.plot_layout(fig, 400)
    fig.update_layout(barmode="group", bargap=0.25, showlegend=True, legend=dict(orientation="h", y=1.1, x=0))
    fig.update_yaxes(title=f"recall@10 ({'5' if key == 'macro' else '4'}-eval macro)", range=[0, 0.85])
    ui.chart(fig, f"jf_bars_{ro}_{key}")
with right:
    rows = []
    for a, lab in A_ARMS[1:]:
        r = [lab]
        for lens in ("jlens", "jpp"):
            r.append(ci(D.get(f"{lens}|{a}|{ro}|grid11 - fam", {}).get(key)) if a != "fam" else "–")
            r.append(ci(D.get(f"{lens}|{a}|{ro}|grid11 - zero", {}).get(key)))
        rows.append(r)
    ui.table(["centre", "J-lens Δ fam", "J-lens Δ plain", f"{JPP} Δ fam", f"{JPP} Δ plain"], rows, num={1, 2, 3, 4})
    st.caption("Points, 95 % paired bootstrap (items resampled within eval). 'Δ plain' compares with the same map, "
               "uncentred, on the same layers.")

st.write("")
ui.label("Per eval")
a_labels = [lab for _, lab in A_ARMS]
pick_a = st.multiselect("Centres", a_labels, default=["plain (no centre)", "fam", "S14bL", "S20x"], key="jf_pick_a")
cols = st.columns(2, gap="large")
for col, (lens, name) in zip(cols, (("jlens", "J-lens"), ("jpp", "J++")), strict=True):
    with col:
        series = {lab: [(S.get(f"{lens}|{a}|{ro}|grid11") or {}).get(e) for e in EVALS] for a, lab in A_ARMS}
        per_category(EVALS, pick_a, series, f"jf_cat_a_{lens}_{ro}", f"{name} · {ro} · recall@10", a_labels)

rows = []
for lens, name in (("jlens", "J-lens"), ("jpp", "J++")):
    for a, lab in A_ARMS:
        v = S.get(f"{lens}|{a}|{ro}|grid11")
        if v:
            rows.append([name, lab, f"<b>{v['macro']:.3f}</b>", f"{v['macro4']:.3f}"] + [f"{v[e]:.3f}" for e in EVALS])
with st.expander(f"Per eval, every arm ({ro})"):
    ui.table(["map", "centre", "macro", "macro4"] + EVALS, rows, num=set(range(2, 9)))

left, right = st.columns(2, gap="large")
with left:
    ui.section("Parity with the paper", "Uncentred maps, rms. Our scorer on the paper's seven layers, our eleven, and "
               "the post's figures.")
    rows = [[n, f"{POST[k]:.3f}" if k in POST else "–", f3(a_score(k, "zero", "rms", layers="recipe7")),
             f3(a_score(k, "zero", "rms"))] for k, n in (("jlens", "J-lens (n1000)"), ("jpp", "J++"))]
    ui.table(["map", "the post", "ours, 8–56 step 8", "ours, 20–56 (11)"], rows, num={1, 2, 3})
with right:
    st.write("")
    ui.prose(
        "Our scorer reproduces the paper's released <code>evaluate</code> exactly (umot, 2026-10-10: every top-10 hit "
        "agrees). The post's own figures differ: its J++ is lower and its J-lens higher than the released code gives, "
        f"so the post's gap ({100 * (POST['jpp'] - POST['jlens']):.1f} pts) is narrower than ours. The order is the "
        "same. The likely cause is another item set, seed or lens version behind the post; it is not verified.",
        "Our layers lift both uncentred maps a little, so every Δ above is against the uncentred map on those same layers.",
    )

# ------------------------------------------------------------------ A2
P2 = None
_p2 = OUT / "analysis" / "jpp-finalists" / "pool-jpp.json"
if _p2.exists():
    P2 = _json(str(_p2), _mtime(_p2))["result"]
if P2:
    ui.section(f"A2 · The same evals, centres fitted in distribution",
               f"Every centre refitted on the {JPP} evals' own fit split (80 items, never scored; the split {JPP} fitted "
               "its expert weights on) instead of our WorkspaceBench fit pool. Same scoring as A.", eyebrow="A2 · In distribution")
    A2 = [("zero", "plain (no centre)"), ("ref", "ref"), ("loo", "loo (transductive)"), ("knn8", "knn8"), ("km8", "km8"),
          ("T:ref+knn8", "T: ref + knn8"), ("T:km8+knn8", "T: km8 + knn8"), ("S14b-knnxs8∪", "S14b-knnxs8 (both pools)"),
          ("s20x-jpp", "S20x refit"), ("s20xon-jpp", "s20xon refit"), ("rand.s20x-jpp", "rand. S20x refit")]
    S2, D2 = P2["scores"], P2.get("diffs", {})

    def s2(lens, arm, r, k="macro"):
        v = S2.get(f"{lens}|{arm}|{r}|grid11") or (S.get(f"{lens}|{arm}|{r}|grid11") if arm == "zero" else None)
        return None if v is None else v[k]

    left, right = st.columns([1.4, 1], gap="large")
    with left:
        labs = [lab for _, lab in A2]
        fig = go.Figure()
        for lens, name, tok in (("jlens", "J-lens", "jlens"), ("jpp", "J++", "jpp")):
            ys = [s2(lens, a, ro, key) for a, _ in A2]
            fig.add_trace(go.Bar(x=labs, y=ys, name=name, marker_color=mapc(tok),
                                 text=[f"{y:.2f}" if y is not None else "" for y in ys], textposition="outside",
                                 textfont=dict(size=10.5, color=ui.c("ink-2"))))
        fig.add_hline(y=a_score("jpp", "zero", ro, key), line=dict(color=mapc("jpp"), dash="dot", width=1.5),
                      annotation_text="plain J++", annotation_position="top right")
        ui.plot_layout(fig, 400)
        fig.update_layout(barmode="group", bargap=0.25, showlegend=True, legend=dict(orientation="h", y=1.1, x=0))
        fig.update_yaxes(title=f"recall@10 ({'5' if key == 'macro' else '4'}-eval macro)", range=[0, 0.85])
        ui.chart(fig, f"jf2_bars_{ro}_{key}")
    with right:
        rows = []
        for a, lab in A2[1:]:
            rows.append([lab] + [ci(D2.get(f"{lens}|{a}|{ro}|grid11 - {ref}", {}).get(key))
                                 for lens, ref in (("jlens", "ref"), ("jlens", "jpp|zero|" + ro + "|grid11"),
                                                   ("jpp", "zero"))])
        ui.table(["centre", "J-lens Δ ref", "J-lens Δ plain J++", f"{JPP} Δ plain {JPP}"], rows, num={1, 2, 3})
        st.caption("Points, 95 % paired bootstrap. Readout and macro follow the switches in A. T: = the S14b form "
                   "(early mean up to L40, then the template projection of h minus half the late kNN mean).")
    ui.label("Per eval")
    a2_labels = [lab for _, lab in A2]
    pick2 = st.multiselect("Centres  ", a2_labels, default=["plain (no centre)", "ref", "T: km8 + knn8", "S20x refit"],
                           key="jf_pick_a2")
    cols = st.columns(2, gap="large")
    for col, (lens, name) in zip(cols, (("jlens", "J-lens"), ("jpp", "J++")), strict=True):
        with col:
            series = {lab: [s2(lens, a, ro, e) for e in EVALS] for a, lab in A2}
            per_category(EVALS, pick2, series, f"jf_cat_a2_{lens}_{ro}", f"{name} · {ro} · recall@10, in distribution", a2_labels)
    st.html(ui.note("key", "What fitting in distribution changes",
                    "The label-free centres gain about nothing from the in-distribution pool. The learned correction "
                    "does: S20x refitted leave-one-eval-out on the J++ fit split lifts the J-lens most of the way to plain "
                    f"{JPP} (level with it under cos), well beyond its random-direction control. It is supervised: it learns "
                    f"from the other evals' fit-split answers. Centred {JPP} still does not beat plain {JPP} under rms."))

# ------------------------------------------------------------------ B
ui.section(f"B · Our val split, through {JPP}",
           "Strict pass@10 per family (the free score: a lower bound on the single-token families, a piece proxy on "
           "_mt, not a proxy on user modelling or DM). Each finalist read through the J-lens and through J++.",
           eyebrow="B · Our val")
ro_b = st.segmented_control("Readout ", ["cos", "rms"], default="cos", key="jf_ro_b") or "cos"
t = stamp()
rows, done = [], 0
for lab, arm in B_ARMS[ro_b]:
    for lens, name in (("", "J-lens"), ("jpp:", "J++")):
        per = strict(lens + arm, t)
        done += lens == "jpp:" and None not in per.values()
        miss = '<span class="c-mu">pending</span>' if lens else "–"
        rows.append([name, lab, f"<b>{f3(mean(list(per.values())), miss)}</b>", f3(mean([per[f] for f in SINGLE]), miss)]
                    + [f3(per[f], miss) for f in FAMS])
n_b = len(B_ARMS[ro_b])
m11 = {(lens, lab): mean(list(strict(lens + arm, t).values())) for lab, arm in B_ARMS[ro_b] for lens in ("", "jpp:")}
cands = [lab for lab, _ in B_ARMS[ro_b] if lab not in ("plain (no centre)", "fam") and not lab.startswith("rand")
         and m11["jpp:", lab] is not None]
if cands and m11["jpp:", "plain (no centre)"] is not None:
    top = max(cands, key=lambda lab: m11["jpp:", lab])
    p0, pt = m11["jpp:", "plain (no centre)"], m11["jpp:", top]
    rnd = m11.get(("jpp:", "rand. S14bL"))
    bj = max((m11["", lab] for lab, _ in B_ARMS[ro_b] if m11["", lab] is not None and not lab.startswith("rand")), default=None)
    st.html('<div class="jm-stats">'
            f'<div class="jm-stat"><span class="v c-h">{p0:.3f} → {pt:.3f}</span><span class="l">{JPP} on val ({ro_b}), plain → best centre ({top}), macro 11</span></div>'
            + (f'<div class="jm-stat"><span class="v c-mu">{pts(rnd - p0)} pts</span><span class="l">its random-direction control (rand. S14bL)</span></div>' if rnd is not None else "")
            + (f'<div class="jm-stat"><span class="v c-d">{bj:.3f}</span><span class="l">best centred J-lens on val ({ro_b})</span></div>' if bj is not None else "")
            + "</div>")
    st.html(ui.note("key", "On our banks, centring does help J++",
                    f"Unlike on the {JPP} evals, every finalist lifts {JPP} on val, with cos and with rms, and with cos well beyond the random-direction "
                    "control (the controls were read with cos only). The likely difference is the setting: chat-template prompts with template-heavy read cells, "
                    "where the template prior the centres remove is large, against short raw-text prompts read at one cell. "
                    "Strict only; no intervals yet, and strict is not a proxy on user modelling or DM."))
if done < n_b:
    st.html(ui.note("open", "Part B is still running",
                    f"{done} of {n_b} {JPP} arms have every family. Pending cells fill in on reload."))
ui.table(["map", "centre", "macro 11", "macro 5"] + [SHORT[f] for f in FAMS], rows, num=set(range(2, 15)))
st.caption("macro 5 = the single-token families (typo, association, basic, multihop, multilingual). The J-lens rows "
           "are the arms already on val (– where that arm was never read on val); 'pending' marks a J++ cell not yet read.")

ui.label("Per family")
b_labels = [lab for lab, _ in B_ARMS[ro_b]]
pick_b = st.multiselect("Centres ", b_labels, default=[x for x in ["plain (no centre)", "fam", "S14bL", "S20x"] if x in b_labels],
                        key=f"jf_pick_b_{ro_b}")
cols = st.columns(2, gap="large")
for col, (lens, name) in zip(cols, (("", "J-lens"), ("jpp:", "J++")), strict=True):
    with col:
        series = {lab: [strict(lens + arm, t)[f] for f in FAMS] for lab, arm in B_ARMS[ro_b]}
        per_category([SHORT[f] for f in FAMS], pick_b, series, f"jf_cat_b_{lens or 'j'}_{ro_b}",
                     f"{name} · {ro_b} · strict pass@10 (val)", b_labels)


st.caption("Record: out/analysis/jpp-finalists/summary.md (A), out/eval/<family>/val/summary.json (B); scripts "
           "experiments/jpp_finalists.py and experiments/jobs/jpp_finalists_val.sh.")
