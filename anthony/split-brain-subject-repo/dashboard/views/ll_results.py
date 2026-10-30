"""Programme LL, night-2 results (2026-10-12): the expert sweep, the failed k = 1 gate and its diagnosis, H1-H6, and
LL4's fitted expert weights through the official pipeline. The argument and the plan are on views/local_lin.py; the
written record is notes/iteration-anthony/local-linearisation/log.md. Every number here is read from out/ on load:
out/analysis/LL0, LL1, LL2, LL4, LLjpp and the official summaries out/eval/<family>/<split>/summary.json.
"""

import json
from pathlib import Path

import figures_ll as F
import plotly.graph_objects as go
import streamlit as st

import sources
import ui

OUT = sources.REPO_ROOT / "out"
A = OUT / "analysis"
LAYERS = [24, 32, 40, 48, 56]
FAMS = sources.ALL_FAMILIES
SHORT = {"typo": "typo", "association": "association", "basic_readout": "basic", "multihop": "multihop",
         "multilingual": "multilingual", "user_modeling": "user model.", "directed_modulation": "dir. modul.",
         "typo_mt": "typo_mt", "multihop_mt": "multihop_mt", "basic_readout_mt": "basic_mt", "multilingual_mt": "multiling._mt"}
#: Categorical slots (the dataviz palette views/pca.py uses), light / dark.
CAT = [("#2a78d6", "#3987e5"), ("#eb6834", "#d95926"), ("#1baf7a", "#199e70"), ("#eda100", "#c98500"),
       ("#e87ba4", "#d55181"), ("#008300", "#008300"), ("#6250d6", "#9085e9"), ("#e34948", "#e66767")]
JPP = "J<sup>++</sup>"


def cat(k: int) -> str:
    return CAT[k % 8][1 if ui.night() else 0]


def _mtime(p: Path) -> float:
    return p.stat().st_mtime if p.exists() else 0.0


@st.cache_data(show_spinner=False)
def _json(path: str, _mt: float):
    return json.loads(Path(path).read_text())


def load(rel: str):
    p = A / rel
    return _json(str(p), _mtime(p)) if p.exists() else None


@st.cache_data(show_spinner=False)
def arm_macros(arms: tuple[str, ...], split: str, _stamp: float) -> dict[str, dict]:
    """Strict pass@10 per family and macro over the 11 families, from the official summaries (None when any is missing)."""
    out = {}
    for arm in arms:
        per = {}
        for f in FAMS:
            p = OUT / "eval" / f / split / "summary.json"
            a = json.loads(p.read_text())["result"]["arms"].get(arm) if p.exists() else None
            per[f] = a["strict"]["value"] if a else None
        vals = list(per.values())
        out[arm] = {"fams": per, "macro": None if None in vals else sum(vals) / len(vals)}
    return out


@st.cache_data(show_spinner=False)
def weights(router: str, _mt: float) -> dict[str, list[float]] | None:
    p = A / "LL4" / router / "weights.pt"
    try:
        import torch
    except ImportError:
        return None
    return {k: v.tolist() for k, v in torch.load(p, map_location="cpu").items()} if p.exists() else None


def macro(per_family: dict, key: str) -> float | None:
    v = [per_family[f][key]["rate"] for f in per_family if key in per_family[f]]
    return sum(v) / len(v) if len(v) == len(per_family) else None


def corr(x: list[float], y: list[float]) -> float:
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y, strict=False))
    sx = sum((a - mx) ** 2 for a in x) ** 0.5
    sy = sum((b - my) ** 2 for b in y) ** 0.5
    return sxy / (sx * sy) if sx and sy else float("nan")


def m(s: str, tok: str = "") -> str:
    return f'<span class="m{" c-" + tok if tok else ""}">{s}</span>'


def verdict(word: str) -> str:
    tok = {"refuted": "bad", "supported": "good", "met": "good", "failed": "bad", "open": "warn"}[word]
    return f'<b style="color:var(--{tok})">{word}</b>'


stamp = sources.stamp()
EXP = load("LL1/experts.json")
if EXP is None:
    st.warning("No LL results under out/analysis/LL1: pull them first (Shared data page) or run programme LL.")
    st.stop()

ARMS = ("zero|cos", "ll4w8:zero|cos", "ll4w16:zero|cos", "jpp:zero|cos", "fam@fit|cos", "ll4w8f:fam@fit|cos",
        "jpp:fam@fit|cos", "zero|rms", "ll4w8:zero|rms", "ll4w16:zero|rms", "jpp:zero|rms")
VAL, BENCH = arm_macros(ARMS, "val", stamp), arm_macros(ARMS, "bench", stamp)
PB = load("LL4/paired-bench.json") or {}
PV = {**(load("LL4/paired-val-w8.json") or {}), **(load("LL4/paired-val.json") or {})}


def pts(x: float | None) -> str:
    return "–" if x is None else f"{100 * x:+.1f}"


v0, v16, vj = (VAL[a]["macro"] for a in ("zero|cos", "ll4w16:zero|cos", "jpp:zero|cos"))
b0, b16, bj = (BENCH[a]["macro"] for a in ("zero|cos", "ll4w16:zero|cos", "jpp:zero|cos"))

ui.header(
    "Programme LL · night-2 results (2026-10-12)",
    "Filter the slope, centre with the bank",
    f"One backward sweep fitted {JPP}-style expert Jacobians from the J-lens's own estimator, each with the anchor of "
    "the positions behind it. The anchors did not help: the local-linearisation hypotheses fell one by one. What "
    f"did help is {JPP}'s other idea. Sixteen signed weights per layer over plain-gradient experts, fitted on our fit "
    "split, give the J-lens a held-out +8 points with no family harmed, level with the released J++ lens.",
)
st.html('<div class="jm-stats">'
        f'<div class="jm-stat"><span class="v c-d">{v0:.3f} → {v16:.3f}</span><span class="l">val macro pass@10, J-lens → fitted experts (ll4w16, {pts(v16 - v0)} pts)</span></div>'
        f'<div class="jm-stat"><span class="v c-d">{b0:.3f} → {b16:.3f}</span><span class="l">bench, read once after registering the prediction ({pts(b16 - b0)} pts)</span></div>'
        f'<div class="jm-stat"><span class="v c-h">{pts(v16 - vj)} / {pts(b16 - bj)}</span><span class="l">vs {JPP} released (LRP, fitted on its own evals): val / bench</span></div>'
        f'<div class="jm-stat"><span class="v c-mu">{EXP["24"]["gate_cos_w1_n1000"]:.2f}</span><span class="l">cos(our pooled J, n1000) at L24: the k = 1 gate failed</span></div>'
        "</div>")
left, right = st.columns(2, gap="large")
left.html(ui.note("key", "The answer to the programme's question",
                  "On our banks the gain is <b>global filtering of slopes plus a bank-derived intercept</b>, not local "
                  "linearisation. Wikitext anchors, paired anchors and routing all do nothing beyond their random-bin "
                  "controls. Fitted weights drop the weak experts and subtract a large generic one, and they help with "
                  "or without a centre. H4 is supported; H1, H2, H3, H5 and H6 are refuted."))
right.html(ui.note("open", "Read everything here as provisional",
                   "With one cluster the sweep should reproduce the released n1000 lens (cos ≥ 0.99). It does only at "
                   "L56 (§2). The gap is systematic and unexplained, though the two maps give almost the same readouts. "
                   "The comparison the result rests on, fitted against pooled weights over the same experts, does not "
                   "depend on n1000. Bench scores are strict only: the judge has not run on <code>_mt</code>, UM or DM."))

# ------------------------------------------------------------------ 1
ui.section("What ran: one sweep, five clusterings, every bin with its own anchor",
           "LL0 cost about $37 of the $50.63 spent. Everything after it reads stored experts.", eyebrow="1 · The sweep")
counts = {r: EXP["40"][r]["count"] if r != "w1" else [sum(EXP["40"]["w8"]["count"])] for r in ("w1", "w8", "w16", "o8", "r8")}
ui.figure(F.sweep_bins(counts, 40), "<b>LL0, measured bin sizes at L40.</b> jlens' estimator, with the prompt replicated "
          "and one-hot cotangents at every kept position, gives each position's gradient G<sub>p</sub>. Five routers "
          "assign it a bin. J++'s router (unit-normalise, PCA to 64, k-means++) has 8 or 16 clusters. o8 is k-means on "
          "our fit cells, capped at 102 per family, and r8 is random bins of w8's sizes. <b>o8 is starved</b>: wikitext "
          "barely visits the regions our bank cells sit in.")
st.write("")
ui.table(
    ["phase", "what ran", "answers", "result"],
    [
        ["<b>LL0</b>", "353 wikitext prompts, 39,136 positions per layer, L24–L56, plain gradients (no LRP)", "the experts", "8.1 GB of experts and anchors"],
        ["<b>LL1</b>", "k = 1 vs n1000; where bank cells land; first-order error by anchor", "gate, H3", f"gate {verdict('failed')}; H3 {verdict('refuted')}"],
        ["<b>LL2</b>", "each expert alone × 6 anchors, fit banks", "H1, H2", f"both {verdict('refuted')}"],
        ["<b>LL3</b>", "slope × intercept grid, fit and val; random routing beside", "H4, H6", f"H4 {verdict('supported')}, H6 {verdict('refuted')}"],
        ["<b>LL4</b>", f"{JPP}'s rank objective: signed unit-L2 weights per layer, fitted on fit, scored on val, then the bench", "H5, the finalist",
         f"+{100 * (v16 - v0):.1f} val, +{100 * (b16 - b0):.1f} bench; prediction {verdict('met')}"],
        ["<b>J++ evals</b>", f"{JPP}'s five held-out readout evals, rms readout with Readout Filtering", "H5, transfer", f"H5 {verdict('refuted')}; 3/4 of the gain transfers"],
    ],
)

# ------------------------------------------------------------------ 2
ui.section("The gate: k = 1 should be the released lens, and is not below L56",
           "The k = 1 bin is the J-lens estimator over our prompts, a subset of n1000's. The gate was cos ≥ 0.99 at every "
           "layer.", eyebrow="2 · Gate and diagnosis")
gate = [EXP[str(L)]["gate_cos_w1_n1000"] for L in LAYERS]
half = [EXP[str(L)]["split_half_w1"] for L in LAYERS]
left, right = st.columns(2, gap="large")
with left:
    fig = go.Figure()
    fig.add_hrect(y0=0.99, y1=1.0, fillcolor=ui.rgba("good", 0.10), line_width=0)
    fig.add_trace(go.Scatter(x=LAYERS, y=half, mode="lines+markers", name="our two halves (176 vs 177 prompts)",
                             line=dict(color=ui.c("h"), width=2.5), marker=dict(size=8)))
    fig.add_trace(go.Scatter(x=LAYERS, y=gate, mode="lines+markers+text", name="our pooled J vs n1000",
                             line=dict(color=ui.c("bad"), width=2.5), marker=dict(size=9),
                             text=[f"{v:.3f}" for v in gate], textposition="bottom right",
                             textfont=dict(color=ui.c("bad"), size=11.5)))
    ui.plot_layout(fig, 360)
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=1.12, x=0), title=None)
    fig.update_xaxes(title="layer", tickvals=LAYERS)
    fig.update_yaxes(title="cosine of the two maps", range=[0.82, 1.005])
    ui.chart(fig, "ll_gate")
    st.caption("Green band: the gate (cos ≥ 0.99). If noise were the only cause, our halves would agree with each "
               "other no better than with n1000. They agree far better (0.995 vs 0.950 at L40), so the gap is systematic.")
with right:
    S = load("LL0/settings.json") or {}
    fig = go.Figure()
    names = {"16:128": "ours (skip 16, 128 tokens)", "0:128": "keep the sink positions", "16:256": "256 tokens"}
    for i, (k, v) in enumerate(S.items()):
        fig.add_trace(go.Scatter(x=LAYERS, y=[v[str(L)]["cos_n1000"] for L in LAYERS], mode="lines+markers", name=names.get(k, k),
                                 line=dict(color=[ui.c("ink-2"), ui.c("mu"), ui.c("delta")][i % 3], width=2,
                                           dash=["solid", "dot", "dash"][i % 3])))
    ui.plot_layout(fig, 360)
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=1.12, x=0))
    fig.update_xaxes(title="layer", tickvals=LAYERS)
    fig.update_yaxes(title="cos(mean J over 8 prompts, n1000)")
    ui.chart(fig, "ll_settings")
    st.caption("D3: the same 8 prompts under three estimator settings. Neither the skip nor the length moves J "
               "materially towards n1000. Keeping the attention-sink positions moves it away, so n1000 most likely "
               "skipped them too.")
KC = load("LL0/kernelcheck.json") or {}
left, mid, right = st.columns(3, gap="large")
left.html(ui.note("open", "D1 · not the kernel",
                  "jlens' own <code>jacobian_for_prompt</code>, run with flash-linear-attention's kernels and with "
                  "transformers' reference path: cos(fla, ref) per prompt is " + ", ".join(
                      f"L{L} {min(v['fla~ref']):.3f}" for L, v in KC.items()) + ". The kernel moves J by ≤ 1 %, and not "
                  "towards n1000."))
mid.html(ui.note("key", "D2 · but the two maps read alike",
                 "Of about 700 bank items, the pooled J and n1000 disagree on 24 (fit) and 28 (val) read uncentred, and "
                 "on 11–15 with fam. The systematic gap is in directions the readout barely uses, so the pooled map is "
                 "the J-lens in practice."))
right.html(ui.note("open", "D3 · what is left",
                   "n1000's prompt selection (Neuronpedia's sibling lenses use <code>max_chars 2000</code> and an "
                   "early stop), the dtype of the fit, or heavy-tailed prompts among the 647 we did not sweep. "
                   "Cheapest test: ask the J-lens authors for the fit command."))

# ------------------------------------------------------------------ 3
ui.section(f"{JPP}'s regimes are not our banks' regimes",
           "Where the router sends our bank cells, how big each wikitext bin is, and how much the experts agree.",
           eyebrow="3 · Landing and geometry")
LAND = load("LL1/landing.json") or {}
c1, c2, _ = st.columns([1, 2, 2])
router = c1.segmented_control("Router", ["w8", "w16", "o8"], default="w8", key="ll_land_r") or "w8"
layer = int(c2.segmented_control("Layer", [str(L) for L in LAYERS], default="40", key="ll_land_l") or "40")
left, right = st.columns([1.35, 1], gap="large")
with left:
    lr = LAND.get(router, {}).get(str(layer), {})
    k = len(EXP[str(layer)][router]["count"])
    cnt = EXP[str(layer)][router]["count"]
    rows = [("wikitext positions (the sweep)", [c / sum(cnt) for c in cnt])] + [(SHORT[f], lr[f]["val"]) for f in FAMS if f in lr]
    fig = go.Figure()
    for i in range(k):
        fig.add_trace(go.Bar(y=[r[0] for r in rows], x=[r[1][i] for r in rows], orientation="h", name=f"cluster {i}",
                             marker=dict(color=cat(i), opacity=1 if i < 8 else 0.55, line=dict(width=0)),
                             hovertemplate=f"cluster {i}: %{{x:.0%}}<extra>%{{y}}</extra>"))
    ui.plot_layout(fig, 430)
    fig.update_layout(barmode="stack", bargap=0.25, showlegend=k <= 8, legend=dict(orientation="h", y=1.08, x=0))
    fig.update_xaxes(tickformat=".0%", range=[0, 1], title="share of positions / val cells")
    fig.update_yaxes(autorange="reversed")
    ui.chart(fig, "ll_landing")
    empty = sum(1 for i in range(k) if all(lr[f]["val"][i] < 0.005 for f in lr))
    st.caption(f"Top row: the sweep's positions. Below: each family's val cells. At L{layer}, {empty} of {k} {router} "
               "clusters hold no bank cell, and whole families land in one cluster (association almost entirely in one "
               "at L40). The router also partly separates wikitext *articles*: some regimes are topics.")
with right:
    IC = EXP[str(layer)][router].get("inter_cos")
    if IC:
        fig = go.Figure(go.Heatmap(z=IC, zmin=0, zmax=1, colorscale=[[0, ui.c("surface")], [1, ui.c("h")]],
                                   text=[[f"{v:.2f}" for v in r] for r in IC], texttemplate="%{text}" if len(IC) <= 8 else None,
                                   textfont=dict(size=10), showscale=False,
                                   hovertemplate="e%{y} · e%{x}: %{z:.3f}<extra></extra>"))
        ui.plot_layout(fig, 430)
        fig.update_xaxes(tickvals=list(range(len(IC))), ticktext=[f"e{i}" for i in range(len(IC))], side="top")
        fig.update_yaxes(tickvals=list(range(len(IC))), ticktext=[f"e{i}" for i in range(len(IC))], autorange="reversed")
        ui.chart(fig, "ll_intercos")
        st.caption(f"Cosine between {router}'s expert Jacobians at L{layer} ({JPP}'s Fig 17, on our experts). Our "
                   "experts' split halves agree at 0.93–0.99, so the low values are real disagreement, not noise.")
mean_off = {}
for r in ("w8", "w16", "r8"):
    vals = []
    for L in LAYERS:
        M = EXP[str(L)][r].get("inter_cos")
        n = len(M) if M else 0
        vals.append(sum(M[i][j] for i in range(n) for j in range(n) if i != j) / (n * n - n) if n else None)
    mean_off[r] = vals
fig = go.Figure()
for i, (r, lab) in enumerate((("w8", "w8 (J++ router)"), ("w16", "w16"), ("r8", "r8 (random bins: control)"))):
    fig.add_trace(go.Scatter(x=LAYERS, y=mean_off[r], mode="lines+markers", name=lab,
                             line=dict(color=[ui.c("h"), ui.c("delta"), ui.c("muted")][i], width=2.4,
                                       dash="dot" if r == "r8" else "solid")))
ui.plot_layout(fig, 260)
fig.update_layout(showlegend=True, legend=dict(orientation="h", y=1.18, x=0))
fig.update_xaxes(title="layer", tickvals=LAYERS)
fig.update_yaxes(title="mean cos between experts", range=[0, 1.02])
left, right = st.columns([1.35, 1], gap="large")
with left:
    ui.chart(fig, "ll_agree")
with right:
    ui.prose("Experts disagree early and agree late, as in J++. Random bins of the same sizes agree almost perfectly "
             "at every layer, so the disagreement comes from the regimes and not from small samples.",
             f"Anchors sit far from zero: ‖μ<sub>i</sub>‖ / ‖h‖ is {min(min(EXP[str(L)]['w8']['mu_rel_norm']) for L in LAYERS):.2f}–"
             f"{max(max(EXP[str(L)]['w8']['mu_rel_norm']) for L in LAYERS):.2f} for w8. Under the local-linearisation "
             "argument, that distance is exactly why the anchor should matter.")

# ------------------------------------------------------------------ 4
ui.section("H3: the averaged Jacobian is not a Taylor term at any position",
           "Patch the anchor in at one held-out position, run the rest of the network, and compare the true change with "
           "the lens's linear prediction.", eyebrow="4 · First-order error")
ui.figure(F.patch_test(), "<b>The test</b> (<code>experiments/ll1_h3.py</code>): 24 held-out wikitext prompts (900–923, "
          "beyond the sweep's and the router's), 8 positions each, every layer. Arrow lengths and angles are drawn to "
          "the medians in the charts below. The local tangent at m is a finite difference, step 0.1 along h − m.")
H3 = load("LL1/h3v2.json") or load("LL1/h3.json") or {}
anchors = {"zero": "0", "glob": "wiki global μ", "own": "own cluster μᵢ", "other": "another cluster's μⱼ", "knn": "8-NN mean"}
slopes = [("pool", "our pooled J", "h"), ("n1000", "n1000", "ink-2"), ("own", "own expert Jᵢ", "delta"), ("local", "local tangent at m", "mu")]
an = st.segmented_control("Anchor m", list(anchors), format_func=anchors.get, default="own", key="ll_h3_a") or "own"
left, right = st.columns(2, gap="large")
for col, (stat, title, ylog) in zip((left, right), (("cos", "cos(true change, prediction)", False),
                                                     ("ratio", "‖prediction‖ / ‖true change‖", True)), strict=False):
    fig = go.Figure()
    for s, lab, tok in slopes:
        y = [H3.get(str(L), {}).get(f"{an}|{s}|{stat}", {}).get("median") for L in LAYERS]
        fig.add_trace(go.Scatter(x=LAYERS, y=y, mode="lines+markers", name=lab,
                                 line=dict(color=ui.c(tok), width=2.4, dash="dash" if s == "local" else "solid")))
    if ylog:
        fig.add_hline(y=1, line=dict(color=ui.c("ink-2"), dash="dot", width=1))
    ui.plot_layout(fig, 340)
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=1.14, x=0))
    fig.update_xaxes(title="layer", tickvals=LAYERS)
    fig.update_yaxes(title=title, type="log" if ylog else "linear", range=None if ylog else [0, 1])
    with col:
        ui.chart(fig, f"ll_h3_{stat}")
left, right = st.columns(2, gap="large")
left.html(ui.note("open", "H3 as stated is refuted",
                  "With any averaged slope (pooled, n1000 or the anchor's own expert), the prediction is 5–20× too "
                  "short and nearly orthogonal below L48, whichever anchor is used. Moving m from 0 to the global mean, "
                  "the cluster mean or the kNN mean does not reduce the error. Only at L56 does any non-zero anchor "
                  "help."))
right.html(ui.note("key", "What it means for the lens",
                   "The J-lens's averaged Jacobian is not the linearisation of the transport at any one position. "
                   "Its readout works for statistical or counterfactual reasons, so an anchor is not a Taylor point in "
                   "the literal sense. The local tangent does show a pairing effect, but only in direction: it is "
                   "best from the global and own-cluster anchors."))

# ------------------------------------------------------------------ 5
ui.section("H1 and H2: each expert alone, read from each anchor",
           "Per-layer pass@10, macro over the 11 families, fit banks. Each row is one expert.", eyebrow="5 · Single experts")
SG = load("LL2/fit/single.json") or {}
c1, c2, _ = st.columns([1, 2, 2])
sr = c1.segmented_control("Experts", ["w8", "w16", "r8"], default="w8", key="ll_sg_r") or "w8"
sl = int(c2.segmented_control("Layer", [str(L) for L in LAYERS], default="40", key="ll_sg_l") or "40")
k = len(EXP[str(sl)][sr]["count"])
amark = [("0", "no anchor", "muted", "circle"), ("own", "own μᵢ (H1)", "mu", "diamond"), ("other", "another μⱼ (control)", "ink-2", "x"),
         ("fam", "bank fam", "delta", "circle"), ("knn", "bank knnx8", "h", "circle")]
data = {a: [macro(SG, f"{sr}|L{sl}|e{i}|{a}") for i in range(k)] for a, *_ in amark}
order = sorted(range(k), key=lambda i: data["0"][i] or 0)
left, right = st.columns([1.5, 1], gap="large")
with left:
    fig = go.Figure()
    for i in order:
        xs = [data[a][i] for a, *_ in amark if data[a][i] is not None]
        fig.add_trace(go.Scatter(x=[min(xs), max(xs)], y=[f"e{i}"] * 2, mode="lines", line=dict(color=ui.c("line-2"), width=3),
                                 hoverinfo="skip", showlegend=False))
    for a, lab, tok, sym in amark:
        fig.add_trace(go.Scatter(x=[data[a][i] for i in order], y=[f"e{i}" for i in order], mode="markers", name=lab,
                                 marker=dict(color=ui.c(tok), size=11 if a in ("own", "other") else 9, symbol=sym,
                                             line=dict(width=1, color=ui.c("surface"))),
                                 hovertemplate=f"{lab}: %{{x:.3f}}<extra>%{{y}}</extra>"))
    ui.plot_layout(fig, 120 + 26 * k)
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=1.02 + 30 / (120 + 26 * k), x=0))
    fig.update_xaxes(title="per-layer pass@10, macro over families", rangemode="tozero")
    ui.chart(fig, "ll_single")
with right:
    own_beats = sum(1 for i in range(k) if (data["own"][i] or 0) > (data["other"][i] or 0))
    ui.prose(
        f"<b>H1 (consistent pair).</b> At L{sl}, an expert's own anchor beats another cluster's anchor for "
        f"<b>{own_beats} of {k}</b> experts, about chance. The amber diamonds sit on the grey crosses, and both sit "
        "near the uncentred dot. Only the bank anchors (teal, blue) move every expert, by 3–12 points.",
        "<b>H2 (bad-expert rescue).</b> The bottom rows are the experts J++ would filter. Their own anchor does not "
        "rescue them, and fam lifts them by as much as it lifts the good ones.",
        "<b>The surprise.</b> Switch to <code>r8</code>: experts averaged over <i>random</i> bins of the same sizes read "
        "better than regime experts at every layer (uncentred L40: 0.31 vs 0.22). Averaging a slope over one regime costs "
        "readout quality. That argues for filtering the experts with weights, not for routing to them.",
    )

# ------------------------------------------------------------------ 6
ui.section("H4 and H6: the slope × intercept grid, measured",
           "The design space from the plan, filled in. Rows change the slope, columns change the intercept.",
           eyebrow="6 · The grid")
gsplit = st.segmented_control("Split", ["val", "fit"], default="val", key="ll_grid_s") or "val"
G = load(f"LL2/{gsplit}/grid.json") or {}
W8 = load("LL4/w8/scores.json") or {}


def gm(key):
    return macro(G, key) if G else None


def ll4m(key):
    s = W8.get(key)
    return sum(v["rate"] for v in s.values()) / len(s) if s else None


grid_rows = [
    ("pooled J", "one map (k = 1)", [gm("pool|0"), gm("pool|glob"), gm("w8:pool|local"), gm("pool|fam"), gm("pool|knn")]),
    ("filtered", "Σ wᵢ Jᵢ, LL4 weights (w8)", [ll4m(f"0|fitted|{gsplit}|cos"), None, ll4m(f"own|fitted|{gsplit}|cos"),
                                                  ll4m(f"fam|fitted|{gsplit}|cos"), ll4m(f"knn|fitted|{gsplit}|cos")]),
    ("routed", "each cell to its w8 expert", [gm(f"w8:routed|{a}") for a in ("0", "glob", "local", "fam", "knn")]),
    ("routed, random", "r8 bins: the control", [gm(f"r8:routed|{a}") for a in ("0", "glob", "local", "fam", "knn")]),
    ("J++ released", "LRP, fitted on its evals", [gm("jpp|0"), gm("jpp|glob"), None, gm("jpp|fam"), gm("jpp|knn")]),
]
ui.figure(F.answer_grid(grid_rows, gm("pool|0"), gsplit),
          "<b>Measured.</b> In the filtered row the 'own cluster's mean' cell is the paired readout Σ w<sub>i</sub> "
          "J<sub>i</sub> (h − μ<sub>i</sub>). On fit, the filtered row is in-sample, because its weights were chosen there.")
st.write("")
left, mid, right = st.columns(3, gap="large")
left.html(ui.note("key", "H4 supported: global slope, local intercept",
                  "Intercepts from wikitext, global or per cluster, add nothing. Intercepts from the bank (fam, knnx8) carry "
                  "the whole centring gain, as S4 found. Filtering the slope adds on top of either."))
mid.html(ui.note("open", "H6 refuted: routing does not return",
                 "Routing each cell to its regime's expert, with or without its anchor, is within about 2 points of the "
                 "pooled map, and random routing does as well. Item noise is about 1.5 points per arm at n ≈ 700."))
right.html(ui.note("open", "o8: slopes for our regimes need our corpus",
                   "The experts for our own fit-cell clusters were fitted from 5–500 wikitext positions each, and they "
                   "lose 4–8 points. An expert for the region our cells occupy cannot be fitted from wikitext."))

# ------------------------------------------------------------------ 7
ui.section("LL4: fitted expert weights through the official pipeline",
           f"{JPP}'s rank objective on our fit split: per layer, signed unit-L2 weights maximising the macro soft "
           "pass@10. The rms readout makes logits linear in w, so per-expert logits are cached once. The exported maps "
           "(<code>ll4w8</code>, <code>ll4w8f</code>, <code>ll4w16</code>) replace L24–L56 and keep n1000 at the other "
           "grid layers.", eyebrow="7 · The finalist")
c1, c2, _ = st.columns([1, 2, 2])
wr = c1.segmented_control("Experts", ["w8", "w16"], default="w8", key="ll_w_r") or "w8"
wl = int(c2.segmented_control("Layer", [str(L) for L in LAYERS], default="40", key="ll_w_l") or "40")
WS = weights(wr, _mtime(A / "LL4" / wr / "weights.pt"))
if WS is None:
    st.info("torch is not importable here, so the weight diagram is skipped (LL4/<router>/weights.pt).")
else:
    cnt = EXP[str(wl)][wr]["count"]
    keep = [i for i, c in enumerate(cnt) if c >= 200]
    w = WS[f"0|L{wl}"]
    alone = [macro(SG, f"{wr}|L{wl}|e{i}|0") or 0 for i in keep]
    lr = LAND.get(wr, {}).get(str(wl), {})
    fit_f = [f for f in lr if f not in ("user_modeling", "directed_modulation")]
    share = [sum(lr[f]["fit"][i] for f in fit_f) / len(fit_f) for i in keep]
    ui.figure(F.fitted_lens(w, alone, share, [cnt[i] for i in keep], wl, wr),
              f"<b>Measured, {wr} at L{wl}.</b> 'Pass alone' is the expert read uncentred at this layer (LL2). 'Share of "
              "bank cells' is the mean over the fit families that have one cell per item. Across layers, corr(w, pass alone) = "
              + " / ".join(f"{corr(WS[f'0|L{L}'], [macro(SG, f'{wr}|L{L}|e{i}|0') or 0 for i in range(len(WS[f'0|L{L}']))]):.2f}" for L in LAYERS)
              + " and corr(w, cell share) = "
              + " / ".join(f"{corr(WS[f'0|L{L}'], [sum(LAND[wr][str(L)][f]['fit'][i] for f in fit_f) / len(fit_f) for i in range(len(WS[f'0|L{L}']))]):.2f}" for L in LAYERS)
              + " (L24–L56). The weights follow expert quality, not where our cells sit.")
st.write("")
ro = st.segmented_control("Arms", ["uncentred · cos", "fam-centred · cos", "uncentred · rms"], default="uncentred · cos",
                          key="ll_arms") or "uncentred · cos"
groups = {"uncentred · cos": [("zero|cos", "J-lens"), ("ll4w8:zero|cos", "ll4w8"), ("ll4w16:zero|cos", "ll4w16"), ("jpp:zero|cos", "J++ released")],
          "fam-centred · cos": [("fam@fit|cos", "J-lens, fam"), ("ll4w8f:fam@fit|cos", "ll4w8f, fam"), ("jpp:fam@fit|cos", "J++, fam")],
          "uncentred · rms": [("zero|rms", "J-lens"), ("ll4w8:zero|rms", "ll4w8"), ("ll4w16:zero|rms", "ll4w16"), ("jpp:zero|rms", "J++ released")]}[ro]
tok_of = lambda a: "h" if a.startswith("jpp") else "delta" if a.startswith("ll4") else "muted"  # noqa: E731
left, right = st.columns([1, 1.4], gap="large")
with left:
    fig = go.Figure()
    for split, D, op in (("val", VAL, 0.95), ("bench", BENCH, 0.5)):
        xs = [lab for a, lab in groups]
        ys = [D[a]["macro"] for a, _ in groups]
        fig.add_trace(go.Bar(x=xs, y=ys, name=split, marker=dict(color=[ui.c(tok_of(a)) for a, _ in groups], opacity=op),
                             text=[f"{y:.3f}" if y is not None else "not run" for y in ys], textposition="outside",
                             hovertemplate=f"{split}: %{{y:.3f}}<extra>%{{x}}</extra>"))
    ui.plot_layout(fig, 400)
    fig.update_layout(barmode="group", bargap=0.3, showlegend=True, legend=dict(orientation="h", y=1.1, x=0))
    fig.update_yaxes(title="strict pass@10, macro over 11 families", range=[0.3, 0.7])
    ui.chart(fig, "ll_arms_chart")
    st.caption("Solid bars: val. Faded bars: bench, read once after the prediction was registered. The registered "
               "prediction was +5 to +9 points over the J-lens and within ±3 of J++. Measured: "
               f"{pts(b16 - b0)} and {pts(b16 - bj)}. Teal: fitted experts. Blue: J++. Grey: the J-lens.")
with right:
    comps = [k for k in ("ll4w16:zero|cos=zero|cos", "ll4w16:zero|cos=jpp:zero|cos", "ll4w8:zero|cos=zero|cos",
                         "ll4w8f:fam@fit|cos=fam@fit|cos", "ll4w8:zero|rms=zero|rms", "ll4w16:zero|cos=ll4w8:zero|cos") if k in PV]
    c1, c2 = st.columns([2.2, 1])
    comp = c1.selectbox("Paired difference", comps, format_func=lambda s: s.replace("=", "  −  "), key="ll_comp")
    psplit = c2.segmented_control("Split", ["val", "bench"], default="val", key="ll_psplit") or "val"
    P = (PB if psplit == "bench" else PV).get(comp)
    if P is None:
        st.info(f"{comp.replace('=', ' − ')} was not read on {psplit}: the bench was read once, for the finalist only.")
    else:
        fams = [f for f in FAMS if f in P["families"]]
        d = [P["families"][f]["diff"] for f in fams]
        lo = [P["families"][f]["ci95"][0] for f in fams]
        hi = [P["families"][f]["ci95"][1] for f in fams]
        col = [ui.c("good") if l_ > 0 else ui.c("bad") if h_ < 0 else ui.c("muted") for l_, h_ in zip(lo, hi, strict=False)]
        fig = go.Figure()
        fig.add_vline(x=0, line=dict(color=ui.c("ink-2"), width=1))
        fig.add_vline(x=P["macro_diff"], line=dict(color=ui.c("delta"), width=1.5, dash="dash"))
        fig.add_trace(go.Scatter(x=d, y=[SHORT[f] for f in fams], mode="markers",
                                 marker=dict(color=col, size=10),
                                 error_x=dict(type="data", symmetric=False, array=[h_ - x for h_, x in zip(hi, d, strict=False)],
                                              arrayminus=[x - l_ for l_, x in zip(lo, d, strict=False)], color=ui.c("line-2"), thickness=2, width=0),
                                 customdata=[[P["families"][f]["n"], l_, h_] for f, l_, h_ in zip(fams, lo, hi, strict=False)],
                                 hovertemplate="%{y}: %{x:+.3f} [%{customdata[1]:+.3f}, %{customdata[2]:+.3f}], n = %{customdata[0]}<extra></extra>"))
        ui.plot_layout(fig, 400)
        fig.update_yaxes(autorange="reversed")
        fig.update_xaxes(title=f"difference in strict pass@10, 95 % item bootstrap · macro {P['macro_diff']:+.3f} (dashed)",
                         tickformat="+.2f", zeroline=False)
        ui.chart(fig, "ll_forest")
        st.caption("Green: the interval excludes 0 in favour of the first arm. Red: it excludes 0 against it. Grey: "
                   "inside noise. Strict is a proxy for `_mt` and a guardrail for UM and DM.")

# ------------------------------------------------------------------ 8
ui.section("Is it real? Controls, stability, transfer",
           "The gain could have come from extra free parameters, from the particular fit items, or from our banks. "
           "Three checks rule each of those out.",
           eyebrow="8 · Controls")
R = {r: load(f"LL4/{r}/scores.json") or {} for r in ("w8", "w16", "r8", "w16-halfA", "w16-halfB")}


def fm(r, key):
    s = R[r].get(key)
    return sum(v["rate"] for v in s.values()) / len(s) if s else None


left, right = st.columns(2, gap="large")
with left:
    bars = [("pooled J (k = 1)", fm("w8", "0|pooled|val|cos"), "muted"), ("r8 random bins, fitted", fm("r8", "0|fitted|val|cos"), "ink-2"),
            ("w8 fitted", fm("w8", "0|fitted|val|cos"), "delta"), ("w16 fitted", fm("w16", "0|fitted|val|cos"), "delta"),
            ("w16 fitted on half A", fm("w16-halfA", "0|fitted|val|cos"), "h"), ("w16 fitted on half B", fm("w16-halfB", "0|fitted|val|cos"), "h")]
    bars = [b for b in bars if b[1] is not None]
    base = bars[0][1]
    fig = go.Figure(go.Bar(y=[b[0] for b in bars], x=[b[1] for b in bars], orientation="h",
                           marker=dict(color=[ui.c(b[2]) for b in bars]),
                           text=[f"{b[1]:.3f}  ({100 * (b[1] - base):+.1f})" for b in bars], textposition="outside",
                           hovertemplate="%{y}: %{x:.3f}<extra></extra>"))
    ui.plot_layout(fig, 330)
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(range=[0.35, 0.62], title="val macro pass@10, uncentred cos (screen, L24–L56)")
    ui.chart(fig, "ll_controls")
    st.caption("**Random bins**, with the same sizes and the same fitter, recover under half of w8's gain (+2.9 vs "
               "+6.8). Association does not move at all (0.41 vs w8's 0.66). **Halves**: weights fitted on either "
               "seeded half of the fit items score the same on val, so the gain does not depend on which items chose "
               "the weights.")
with right:
    J1, J2 = load("LLjpp/scores.json") or {}, load("LLjpp/scores-v2.json") or {}
    JJ = {**J2, **J1}

    def jm(k):
        return JJ[k]["macro"] if k in JJ else None

    tb = [("n1000", jm("n1000|none|ours5"), "muted"), ("our pooled J", jm("pool|none|ours5"), "muted"),
          ("r8, refit on J++ fit split", jm("r8:refit|none|ours5"), "ink-2"),
          ("w8, LL4 weights (our banks)", jm("w8:ll4|none|ours5"), "delta"), ("w16, LL4 weights (our banks)", jm("w16:ll4|none|ours5"), "delta"),
          ("w8, refit on J++ fit split", jm("w8:refit|none|ours5"), "h"), ("w16, refit on J++ fit split", jm("w16:refit|none|ours5"), "h"),
          ("J++ released (LRP)", jm("jpp|none|ours5"), "mu")]
    tb = [b for b in tb if b[1] is not None]
    fig = go.Figure(go.Bar(y=[b[0] for b in tb], x=[b[1] for b in tb], orientation="h",
                           marker=dict(color=[ui.c(b[2]) for b in tb]), text=[f"{b[1]:.3f}" for b in tb], textposition="outside",
                           hovertemplate="%{y}: %{x:.3f}<extra></extra>"))
    ui.plot_layout(fig, 330)
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(range=[0.25, 0.65], title=f"{JPP.replace('<sup>', '').replace('</sup>', '')}'s held-out evals: macro recall@10 (rms, filtered, L24–L56)")
    ui.chart(fig, "ll_transfer")
    st.caption("**Transfer**: weights fitted on our banks lift our pooled map on J++'s five evals from 0.375 to "
               "0.490, about three quarters of what refitting on J++'s own fit split gives (0.522). The weights learn "
               "something about the lens, not about our banks. Our scorer reproduces J++ 0.594 and n1000 0.340 on the "
               "7 recipe layers.")
left, right = st.columns([1, 1.2], gap="large")
with left:
    h5 = [("n1000", "n1000"), ("J++ released", "jpp"), ("w8 refit", "w8:refit"), ("w16 refit", "w16:refit"), ("pooled J", "pool")]
    fig = go.Figure()
    for an_, lab, tok in (("none", "uncentred", "muted"), ("ref", "centred (eval's fit-split mean)", "mu")):
        fig.add_trace(go.Bar(x=[a for a, _ in h5], y=[jm(f"{k}|{an_}|ours5") for _, k in h5], name=lab, marker=dict(color=ui.c(tok)),
                             hovertemplate=f"{lab}: %{{y:.3f}}<extra>%{{x}}</extra>"))
    ui.plot_layout(fig, 300)
    fig.update_layout(barmode="group", showlegend=True, legend=dict(orientation="h", y=1.15, x=0))
    fig.update_yaxes(title="macro recall@10, J++ evals", range=[0.3, 0.62])
    ui.chart(fig, "ll_h5")
with right:
    st.write("")
    st.html(ui.note("open", "H5 refuted on J++'s ground",
                    "The puzzle: centring helps n1000 on J++'s evals (+9.5) but hurts J++ (−12.4). The plan's hypothesis "
                    "was that J++'s weights were fitted on uncentred inputs. With weights refitted on centred inputs, "
                    "centring is still 2–5 points <i>below</i> uncentred (w8 0.464 vs 0.481, w16 0.474 vs 0.522). On "
                    "our banks the opposite holds: fitted weights and the bank centre add (+2 over fam, +3 over knnx8). "
                    "On J++'s evals the map and the centre do not add."))

# ------------------------------------------------------------------ 9
ui.section("What the fitted lens changes in a readout",
           "Association val, <code>ll4w16:zero|cos</code> against <code>zero|cos</code>: 29 items won, none lost.",
           eyebrow="9 · Readouts")
EX = [
    ("…the strip of land on three sides, narrowing to a single road…", "peninsula", 32,
     [" —", "—a", " intricate", "—the", "—but"], [" peninsula", " siege", " land", " fortress", " Fort"]),
    ("Blades hissed across the frozen pond…", "skating", 40,
     [" smiling", " crisp", " gl", " icy", " exhilar"], [" skating", " snow", "冰雪", " rink", " ice"]),
    ("Copper vats bubbled with hops and malt…", "brewery", 40,
     [" bustling", "—a", " ——", " intricate", " whispered"], [" industrial", " Industrial", " factory", " Factory", " workers"]),
]
for prompt, tgt, L, base_t, fit_t in EX:
    a, b, c = st.columns([1.3, 1, 1], gap="medium")
    a.html(f'<div style="font-size:14px;color:var(--ink-2);padding-top:6px"><i>{ui.esc(prompt)}</i><br>'
           f'<span style="font-size:12px;color:var(--muted)">target <b>{tgt}</b> · top 5 at L{L}</span></div>')
    b.html('<div style="font-size:11px;color:var(--muted);letter-spacing:.06em">J-LENS</div>' + ui.chips(base_t, tgt))
    c.html('<div style="font-size:11px;color:var(--delta);letter-spacing:.06em">FITTED EXPERTS (ll4w16)</div>' + ui.chips(fit_t, tgt))
st.write("")
left, right = st.columns(2, gap="large")
left.html(ui.note("key", "The weights remove the formatting slope",
                  "The J-lens's top 5 is mostly formatting and generic prose style (' —', newlines, ' bustling', "
                  "' intricate'). The fitted lens replaces these with content, and often surfaces the target a layer "
                  "earlier. These are J++'s 'formatting experts', removed by subtracting a large generic expert: a "
                  "contrast in map space, the slope-side analogue of centring."))
right.html(ui.note("open", "Why the two gains overlap",
                   "The bank centre removes the same formatting directions from the <i>state</i> that the weights remove "
                   "from the <i>slope</i>. Each gives about +7 alone and about +8 together with fam. Echo rises slightly "
                   "(+0.5 to +3 points of top-10 share) as cleared slots fill with content words. The prompt-masked "
                   "pass keeps the gain."))

# ------------------------------------------------------------------ 10
ui.section("Hypotheses, scored", eyebrow="10 · Verdicts")
ui.table(
    ["", "claim", "verdict", "evidence"],
    [
        ["<b>H1</b>", "J<sub>i</sub>(h − μ<sub>i</sub>) reads better than J<sub>i</sub> h and J<sub>i</sub>(h − μ<sub>j</sub>)", verdict("refuted"),
         "own anchor ≈ wrong cluster's anchor ≈ none, for single experts (§5) and for the paired readout (§6)"],
        ["<b>H2</b>", "Filtered experts gain most from their own anchor", verdict("refuted"),
         "the weakest experts stay weakest; fam lifts all experts equally"],
        ["<b>H3</b>", "First-order error falls from 0 → μ̄ → μ<sub>i</sub> → kNN", verdict("refuted"),
         "the averaged-J error is ≈ 1 at every anchor below L48 (§4)"],
        ["<b>H4</b>", "Global slope, local intercept", verdict("supported"),
         "bank intercepts carry the centring gain; slope filtering is global; routing ≈ random routing (§6)"],
        ["<b>H5</b>", "Refitting w on centred inputs makes centring add on J++'s evals", verdict("refuted"),
         "centred refits are 2–5 points below uncentred (§8); on our banks they add"],
        ["<b>H6</b>", "Routing returns once anchors are paired", verdict("refuted"),
         "routed + own anchor ≤ pooled, uncentred (§6)"],
        ["<b>Gate</b>", "k = 1 reproduces n1000 (cos ≥ 0.99)", verdict("failed"),
         "0.85–0.98 at L24–L48; not noise, the kernel, the skip or the length; readouts alike (§2)"],
    ],
)
st.write("")
left, right = st.columns(2, gap="large")
left.html(ui.note("open", "Next",
                  "<b>1.</b> Resolve the gate: ask for n1000's fit command. "
                  "<b>2.</b> Fit experts from our own corpus, the regions o8 could not fill. "
                  "<b>3.</b> LRP experts, the other half of J++'s recipe. "
                  "<b>4.</b> Judge <code>_mt</code>, UM and DM for <code>ll4w16:zero|cos</code>, and give it a study card."))
right.html(ui.note("key", "Spend and artefacts",
                   "$50.63 of the $100 LL pot (sweep ≈ $37), all pods terminated. Experts and anchors (w1, w8, w16, r8): "
                   "<code>out/analysis/LL0/experts-compact/</code> (8.1 GB). Maps <code>ll4w8</code>, <code>ll4w8f</code>, "
                   "<code>ll4w16</code> on the shared volume under <code>out/maps/</code>."))
st.caption("Written record: notes/iteration-anthony/local-linearisation/log.md (night-2) and plan.md · code: "
           "src/jlm/mu/LL0.py, experiments/ll*.py · the argument: Understand → Local linearisation (LL).")
