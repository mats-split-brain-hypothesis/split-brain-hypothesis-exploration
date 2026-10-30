"""Readout composition (2026-10-12): what the J++ finalists page's headline arms actually read out, by depth. For the
plain J-lens, plain J++ and the J-lens centred four ways, the full-vocabulary top k of every held-out J++ eval item at
each of our 11 grid layers is split into token classes (jlm.controls.token_class): whitespace / layout and punctuation /
symbols (what J++'s Readout Filtering removes), control tokens and broken bytes, and words. Also the share that echoes
the prompt and whether a target is in the top k. Data: experiments/jpp_readout_tokens.py ->
out/analysis/jpp-readout-tokens/readouts.json (plain JSON; read on load)."""

import json
import random
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import streamlit as st

import gloss
import sources
import ui

PATH = sources.OUT / "analysis" / "jpp-readout-tokens" / "readouts.json"
JPP = "J<sup>++</sup>"
EVALS = ["multihop", "multilingual", "typo", "association", "poetry"]
#: arm -> (label, short label, colour key); order is the page's. Colours follow the J++ finalists page (the J++ paper's
#: Figure 1: J-lens grey, J++ blue); the fit-split mean, which that page's headline does not show, takes the paper's
#: R-lens orange (no R-lens here).
ARMS = {
    "jlens": ("J-Lens", "J-Lens", "jlens"),
    "jpp": ("J++ Lens", "J++", "jpp"),
    "jlens+ref": ("J-Lens, μ = fit-split mean", "μ = fit mean", "ref"),
    "jlens+s20x-jpp": ("J-Lens, fitted μ (fit on the same data as J++)", "fitted μ", "ours"),
    "jlens+s14b-knnxs8u": ("J-Lens, μ = closest 8 points + template directions removed", "closest 8 + template", "ours_lf"),
    "jlens+glosb": ("J-Lens, μ = texts the model wrote from a one-line task description", "task-description texts", "ours_blind"),
}
MAPC = {"jlens": ("#4d4d4d", "#9a9a9a"), "jpp": ("#0072b2", "#2b95d6"), "ref": ("#d97b00", "#e8901a"),
        "ours": ("#009e73", "#1fbf8f"), "ours_lf": ("#b5528c", "#d47fb0"), "ours_blind": ("#c9a000", "#e6bc1f")}
#: token classes (controls.TOKEN_CLASSES), label, (light, dark); validated with the dataviz validator (light: all
#: pass; dark: deutan ΔE 6.2 on space / punct, so every segment carries its % as a direct label)
CLASSES = [("space", "whitespace / layout", ("#eda100", "#c98500")), ("punct", "punctuation / symbols", ("#e34948", "#e34948")),
           ("control", "control tokens / broken bytes", ("#6250d6", "#9085e9")), ("word", "words (letters or digits)", ("#1baf7a", "#199e70"))]
BINS = {"early": [20, 24, 28, 32], "mid": [36, 40, 42, 44], "late": [48, 52, 56]}


def mapc(arm: str) -> str:
    return MAPC[ARMS[arm][2]][1 if ui.night() else 0]


def clsc(k: int) -> str:
    return CLASSES[k][2][1 if ui.night() else 0]


@st.cache_data(show_spinner="Reading readouts.json")
def load(path: str, _mt: float):
    doc = json.loads(Path(path).read_text())
    R = doc["result"]
    vocab = {int(t): v for t, v in R["vocab"].items()}
    ids = sorted(vocab)
    lut = np.full(max(ids) + 1, -1, dtype=np.int8)
    sem = np.zeros(max(ids) + 1, dtype=bool)
    for t in ids:
        lut[t] = [c for c, _, _ in CLASSES].index(vocab[t]["cls"])
        sem[t] = vocab[t]["sem"]
    top = {k: np.asarray(v, dtype=np.int64) for k, v in R["top"].items()}  # [items, layers, K]
    items = R["items"]
    # per item, per (arm, readout): echo of the prompt and target hits, as boolean arrays over the top K
    echo, hit = {}, {}
    for k, A in top.items():
        e = np.zeros(A.shape, dtype=bool)
        h = np.zeros(A.shape, dtype=bool)
        for i, it in enumerate(items):
            forms = set(it["forms"])
            tg = {s for ss in it["targets"].values() for s in ss}
            for t in np.unique(A[i]):
                v = vocab[int(t)]
                if v["form"] and v["form"] in forms:
                    e[i] |= A[i] == t
                if v["s"] in tg:
                    h[i] |= A[i] == t
        echo[k], hit[k] = e, h
    return {"layers": R["layers"], "items": items, "top": top, "lut": lut, "sem": sem, "vocab": vocab, "echo": echo,
            "hit": hit, "check": R["check"], "prov": doc["provenance"]}


ui.header(
    "J++ × our finalists · readouts",
    "What does centring take out of the readout?",
    "The headline arms of the <i>J++ × our finalists</i> page, read token by token: for every held-out item of the "
    f"{JPP} paper's five readout evals, the top tokens of the plain J-lens, plain {JPP} and the J-lens centred four ways, "
    "at each of our 11 layers, before any filtering. Each token is sorted into whitespace, punctuation, control tokens or "
    f"words; <b>semantic</b> means {JPP}'s rule (the token has a letter or digit).",
)
if not PATH.exists():
    st.info("No out/analysis/jpp-readout-tokens/readouts.json yet: run experiments/jpp_readout_tokens.py (a GPU job).")
    st.stop()
D = load(str(PATH), PATH.stat().st_mtime)
LAYERS = D["layers"]
ITEMS = D["items"]
arms = [a for a in ARMS if f"{a}|rms" in D["top"]]
#: the arms the charts draw (the table, notes and examples keep every arm)
plot_arms = [a for a in ("jlens", "jpp", "jlens+s20x-jpp", "jlens+s14b-knnxs8u") if a in arms]

c1, c2, c3, _ = st.columns([1, 1, 2.4, 1.2], vertical_alignment="bottom")
ro = c1.segmented_control("Readout", ["rms", "cos"], default="rms", key="rt_ro",
                          help="rms is the J++ paper's readout (final norm, then W_U); cos is the bench's.") or "rms"
K = c2.segmented_control("Top", [10, 20], default=10, key="rt_k", format_func=lambda k: f"top {k}") or 10
evs = c3.multiselect("Evals", EVALS, default=EVALS, key="rt_evals") or EVALS
rows = np.array([i for i, it in enumerate(ITEMS) if it["eval"] in evs])


def stats(arm: str, layers: list[int]) -> dict[str, float]:
    """Shares over the top K, mean over items and the given layers."""
    li = [LAYERS.index(L) for L in layers]
    A = D["top"][f"{arm}|{ro}"][rows][:, li, :K]
    cls = D["lut"][A]
    out = {c: float((cls == k).mean()) for k, (c, _, _) in enumerate(CLASSES)}
    out["sem"] = float(D["sem"][A].mean())
    out["echo"] = float(D["echo"][f"{arm}|{ro}"][rows][:, li, :K].mean())
    out["hit"] = float(D["hit"][f"{arm}|{ro}"][rows][:, li, :K].any(-1).mean())
    out["recur"] = float(np.mean([recurring(A[:, j]) for j in range(len(li))]))
    return out


RECUR = 0.25


def recurring(A: np.ndarray) -> float:
    """Share of the top-K tokens [items, K] (one layer) that are in the top K of at least RECUR of the items: a
    background the readout shows whatever the item, of any class."""
    ids, n = np.unique(A, return_counts=True)  # a token appears at most once per item's top K
    common = ids[n >= RECUR * len(A)]
    return float(np.isin(A, common).mean())


def pct(x: float) -> str:
    return f"{100 * x:.0f}%"


# ------------------------------------------------------------------ headline tiles
allL = stats("jlens", LAYERS)
tiles = [f'<div class="jm-stat"><span class="v">{pct(1 - allL["sem"])}</span><span class="l">of the plain J-lens top {K} '
         f"is whitespace or punctuation ({ro}, all 11 layers)</span></div>",
         f'<div class="jm-stat"><span class="v">{pct(allL["recur"])}</span><span class="l">of the plain J-lens top {K} recurs in the top {K} '
         f"of at least {RECUR:.0%} of items, whatever the item</span></div>"]
for a in ("jlens+s20x-jpp", "jlens+s14b-knnxs8u", "jpp"):
    if a in arms:
        s = stats(a, LAYERS)
        tiles.append(f'<div class="jm-stat"><span class="v" style="color:{mapc(a)}">{pct(1 - s["sem"])} · {pct(s["recur"])}</span>'
                     f'<span class="l">{ARMS[a][0]}: non-semantic · recurring</span></div>')
st.html('<div class="jm-stats">' + "".join(tiles) + "</div>")
st.caption(f"{len(rows)} held-out items ({', '.join(evs)}), every token of the top {K} at every one of the 11 layers, "
           "over the full vocabulary (no Readout Filtering).")

# ------------------------------------------------------------------ composition by depth
ui.section("Composition by depth",
           f"Share of the top {K} in each token class, averaged over items and the layers of each band. Layers 20–32 are "
           "“early”, 36–44 “mid”, 48–56 “late” (our capture grid inside the J++ paper's 8–56).")
cols = st.columns(3, gap="medium")
S = {(a, b): stats(a, Ls) for a in arms for b, Ls in BINS.items()}
for col, (b, Ls) in zip(cols, BINS.items(), strict=True):
    with col:
        fig = go.Figure()
        xs = [ARMS[a][1] for a in plot_arms]
        for k, (c, lab, _) in enumerate(CLASSES):
            ys = [100 * S[a, b][c] for a in plot_arms]
            fig.add_trace(go.Bar(
                x=xs, y=ys, name=lab, marker=dict(color=clsc(k), line=dict(color=ui.c("surface"), width=2)),
                text=[f"{y:.0f}" if y >= 6 else "" for y in ys], textposition="inside", insidetextanchor="middle",
                textfont=dict(size=10.5, color="#ffffff"),
                hovertemplate=f"{lab}<br>%{{x}}: %{{y:.1f}}%<extra></extra>", showlegend=b == "early"))
        ui.plot_layout(fig, 400)
        fig.update_layout(barmode="stack", bargap=0.28, showlegend=b == "early",
                          legend=dict(orientation="h", y=1.2, x=0, font=dict(size=11)),
                          title=dict(text=f"{b} · L{Ls[0]}–{Ls[-1]}", x=0, y=0.99, font=dict(size=13)))
        fig.update_xaxes(tickangle=-35, tickfont=dict(size=10.5, color=ui.c("ink")), showgrid=False)
        fig.update_yaxes(range=[0, 100], dtick=25, ticksuffix="%")
        ui.chart(fig, f"rt_comp_{b}_{ro}_{K}_{'-'.join(evs)}")

def mean3(a: str, key: str) -> float:  # over the three bands, equally weighted
    return float(np.mean([S[a, b][key] for b in BINS]))


left, right = st.columns(2, gap="large")
if {"jlens", "jpp", "jlens+s20x-jpp"} <= set(arms):
    lf = [a for a in ("jlens+ref", "jlens+s14b-knnxs8u", "jlens+glosb") if a in arms]
    left.html(ui.note("key", "Centring removes the background tokens",
                      f"With the {ro} readout the plain J-lens top {K} is {pct(1 - mean3('jlens', 'sem'))} whitespace and "
                      f"punctuation (runs of underscores, blank lines, CJK punctuation) and {pct(mean3('jlens', 'echo'))} "
                      f"prompt echo. The fitted μ leaves {pct(1 - mean3('jlens+s20x-jpp', 'sem'))} non-semantic; the "
                      "centres that use no labels leave "
                      + ", ".join(f"{pct(1 - mean3(a, 'sem'))} ({ARMS[a][1]})" for a in lf)
                      + f"; plain {JPP} {pct(1 - mean3('jpp', 'sem'))}. Counted by recurrence instead of class, "
                      f"{pct(mean3('jlens', 'recur'))} of the plain J-lens top {K} are tokens it shows for at least a quarter "
                      f"of all items; every centre brings that to {pct(max(mean3(a, 'recur') for a in arms if a.startswith('jlens+')))} "
                      f"or less ({JPP}: {pct(mean3('jpp', 'recur'))}). Prompt echo stays at "
                      f"{pct(min(mean3(a, 'echo') for a in arms))}–{pct(max(mean3(a, 'echo') for a in arms))} for every "
                      "arm, so the cleaner readouts are not the prompt read back. Most of what remains after the label-free "
                      "centres sits in the early band."))
right.html(ui.note("open", "Read with these caveats",
                   "The background is mostly an rms effect: with the bench's cos readout the plain J-lens top 10 is already "
                   "mostly words at early and mid layers, and its non-semantic share grows only late. A word is not a "
                   "meaningful word: the fitted μ's commonest tokens are “New”, “The”, “May”, “Long”, “in”, and the label-free "
                   "centres' include their pool's topic (“poetic”, “poetry”), so a word share near 100 % says the "
                   "punctuation is gone, not that the readout is on topic. Those words recur less than the plain J-lens's "
                   "background (the recurring column); the target column is the check on topic. "
                   "Layers are our 11 capture layers (20–56), not the paper's 8–56."))

# ------------------------------------------------------------------ by layer
ui.section("Layer by layer",
           f"The same readouts at each of the 11 layers. Left: the share {JPP}'s filter would remove (no letter or digit). "
           "Middle: tokens that repeat a word of the prompt (the item's own prompt tokens, normalised). Right: items with a "
           f"target in the full-vocabulary top {K} at that layer.")


def by_layer(metric: str, title: str, ytitle: str, key: str, ymax: float | None = None):
    fig = go.Figure()
    for a in plot_arms:
        ys = [100 * (1 - stats(a, [L])["sem"] if metric == "nonsem" else stats(a, [L])[metric]) for L in LAYERS]
        fig.add_trace(go.Scatter(x=LAYERS, y=ys, name=ARMS[a][1], mode="lines+markers", line=dict(color=mapc(a), width=2),
                                 marker=dict(size=8, line=dict(color=ui.c("surface"), width=2)),
                                 hovertemplate=f"{ARMS[a][1]}<br>L%{{x}}: %{{y:.1f}}%<extra></extra>"))
    ui.plot_layout(fig, 330)
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=-0.2, x=0, font=dict(size=10.5)), hovermode="x unified",
                      title=dict(text=title, x=0, y=0.99, font=dict(size=13)))
    fig.update_xaxes(title="layer", tickvals=LAYERS, tickfont=dict(size=10))
    fig.update_yaxes(title=dict(text=ytitle, font=dict(size=11.5)), ticksuffix="%", rangemode="tozero",
                     range=[0, ymax] if ymax else None)
    ui.chart(fig, f"{key}_{ro}_{K}_{'-'.join(evs)}")


cols = st.columns(2, gap="medium")
with cols[0]:
    by_layer("nonsem", f"Not semantic ({JPP}'s rule)", f"% of top-{K} tokens<br>non-semantic (J++ rule)", "rt_l_ns")
with cols[1]:
    by_layer("recur", f"Recurring: in the top {K} of ≥ {RECUR:.0%} of items", f"% of top-{K} tokens<br>shared by ≥ {RECUR:.0%} of items", "rt_l_rec")
cols = st.columns(2, gap="medium")
with cols[0]:
    by_layer("echo", "Echoes the prompt", f"% of top-{K} tokens<br>found in the item's prompt", "rt_l_echo")
with cols[1]:
    by_layer("hit", f"Target in the top {K}", f"% of items with a<br>target in the top {K}", "rt_l_hit", 100)
st.caption(f"Each point is one layer: the share of all top-{K} tokens of the selected held-out items at that layer (the "
           f"same as the mean over items of each item's share, since every item contributes {K}). The target chart "
           "counts items instead: an item scores when any of its targets is in its top " + str(K) + ".")

# ------------------------------------------------------------------ table
ui.label("Every number above", f"{ro} · top {K}")
trs = []
for a in arms:
    for b in BINS:
        s = S[a, b]
        trs.append([f'<span style="color:{mapc(a)}">■</span> {ARMS[a][1]}' if b == "early" else "", b]
                   + [pct(s[c]) for c, _, _ in CLASSES] + [f"<b>{pct(s['sem'])}</b>", pct(s["recur"]), pct(s["echo"]), pct(s["hit"])])
ui.table(["arm", "layers", "whitespace", "punct.", "control", "words", "semantic (J++)", "recurring", "prompt echo",
          "target in top k"], trs, num=set(range(2, 10)))
st.caption("semantic (J++) = words + the control tokens and broken bytes that contain a letter or digit, which J++'s rule "
           "keeps. Prompt echo uses the item's own prompt tokens (forms shared by half the items or more left out). "
           "Target in top k is a per-layer, full-vocabulary rate; the headline recall@10 takes the best layer after "
           "filtering, so it is higher.")

# ------------------------------------------------------------------ examples
ui.section("Representative readouts",
           "Items in a fixed random order (seed 0) within each eval, not picked for effect. Colour marks the class; a "
           "target is outlined. Non-English tokens carry an English gloss on hover.")


def chips(arm: str, i: int, L: int) -> str:
    A = D["top"][f"{arm}|{ro}"][i, LAYERS.index(L), :K]
    H = D["hit"][f"{arm}|{ro}"][i, LAYERS.index(L), :K]
    out = []
    for t, h in zip(A, H, strict=True):
        v = D["vocab"][int(t)]
        k = [c for c, _, _ in CLASSES].index(v["cls"])
        s = v["s"]
        vis = s.replace("\n", "↵").replace("\t", "⇥") if s.strip() else (s.replace(" ", "␣").replace("\n", "↵") or "∅")
        g = gloss.gloss(s) if v["cls"] == "word" else None
        style = f"border-left:3px solid {clsc(k)};" + ("" if k == 3 else "color:var(--muted);")
        cls = "jm-chip hit" if h else "jm-chip"
        out.append(f'<span class="{cls}" style="{style}" title="{ui.esc(g or CLASSES[k][1])}">{ui.esc(vis)}'
                   + (f' <span style="font-size:10.5px;color:var(--muted)">({ui.esc(g)})</span>' if g else "") + "</span>")
    return '<div class="jm-chips">' + "".join(out) + "</div>"


st.html('<div class="jm-chips">' + "".join(
    f'<span class="jm-chip" style="border-left:3px solid {clsc(k)}">{lab}</span>' for k, (_, lab, _) in enumerate(CLASSES))
    + '<span class="jm-chip hit">target</span></div>')
c1, c2 = st.columns([1, 3], vertical_alignment="bottom")
ev = c1.selectbox("Eval", EVALS, key="rt_ex_eval")
order = [i for i, it in enumerate(ITEMS) if it["eval"] == ev]
random.Random(0).shuffle(order)
pick = c2.select_slider("Item (fixed random order)", options=list(range(len(order))), value=0, key=f"rt_ex_item_{ev}",
                        format_func=lambda j: f"{j + 1}: {ITEMS[order[j]]['item']}")
i = order[pick]
it = ITEMS[i]
prompt = it["prompt"]
st.html(f'<div class="jm-ex"><div class="hd"><span class="jm-eyebrow">{ev} · {ui.esc(it["item"])}</span>'
        f'<span class="jm-n">read token “{ui.esc(it["read_token"])}”</span></div>'
        f'<div class="prompt">{ui.esc(prompt[-600:])}</div>'
        f'<div class="jm-n">targets: {ui.esc(", ".join(sorted({s.strip() for ss in it["targets"].values() for s in ss})))}</div></div>')

c1, c2, _ = st.columns([1.2, 1.2, 1])
labels = {a: ARMS[a][1] for a in arms}
left = c1.selectbox("Left", arms, index=0, format_func=labels.get, key="rt_ex_l")
right = c2.selectbox("Right", arms, index=arms.index("jlens+s20x-jpp") if "jlens+s20x-jpp" in arms else 1,
                     format_func=labels.get, key="rt_ex_r")
trs = [[f"L{L}", chips(left, i, L), chips(right, i, L)] for L in LAYERS]
ui.table(["layer", f'<span style="color:{mapc(left)}">■</span> {labels[left]}',
          f'<span style="color:{mapc(right)}">■</span> {labels[right]}'], trs)

L1 = st.select_slider("Every arm at one layer", options=LAYERS, value=44, key="rt_ex_L")
ui.table(["arm", f"top {K} at L{L1}"], [[f'<span style="color:{mapc(a)}">■</span> {ARMS[a][1]}', chips(a, i, L1)] for a in arms])

# ------------------------------------------------------------------ provenance
with st.expander("How this was computed, and a check against the headline bars"):
    ui.prose(
        "<code>experiments/jpp_readout_tokens.py</code> builds each arm's states with <code>experiments/jpp_finalists.py</code>'s "
        "own functions (same items, read cells, layers and fits), reads them through the lens and keeps the full-vocabulary "
        "top 20 per item and layer. Token classes: <code>jlm.controls.token_class</code> on each id's decode; "
        f"“semantic” is {JPP}'s Readout Filtering rule (<code>controls.non_semantic_ids</code>).",
        "The S20x refit (fitted μ) is re-run here (150 Adam steps, leave-one-eval-out on the J++ fit split), so it can "
        "differ from the stored headline arm by the fit's noise. The table recomputes each arm's held-out recall@10 "
        "(Readout Filtering, best of the 11 layers) from these states, beside the headline bars' value.",
    )
    ui.table(["arm", "readout", "recall@10 here", "headline bars"],
             [[ARMS[k.split("|")[0]][1], k.split("|")[1], f"{v['macro']:.3f}",
               f"{v['headline']:.3f}" if "headline" in v else "–"] for k, v in D["check"].items()], num={2, 3})
    st.caption(f"git {D['prov'].get('git_sha', '')[:7]} · host {D['prov'].get('host', '')}")
