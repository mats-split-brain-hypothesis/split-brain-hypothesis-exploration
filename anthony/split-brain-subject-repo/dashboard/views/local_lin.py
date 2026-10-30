"""Local linearisation (programme LL): where J++'s expert Jacobians meet the centre. The argument, the design space,
the hypotheses and the plan; notes/iteration-anthony/local-linearisation/plan.md is the written record. Numbers quoted
from J++ (Ayonrinde & Lindsey 2026) are theirs; every diagram is a schematic.
"""

import streamlit as st

import figures_ll as F
import ui

H, MU, MUI, D = ui.tex("h", "h"), ui.tex("mu", r"\mu"), ui.tex("mu", r"\mu_i"), ui.tex("delta", r"\delta")
JPP = "J<sup>++</sup>"


def m(s: str, tok: str = "") -> str:
    return f'<span class="m{" c-" + tok if tok else ""}">{s}</span>'


ui.header(
    "Programme LL · local linearisation",
    "Global slope, local intercept",
    f"{JPP} improves the J-lens by treating the residual stream as piecewise linear: one expert Jacobian per cluster, "
    "badly behaved experts filtered out. It makes the <i>slope</i> local and leaves the <i>expansion point</i> at zero. "
    "Our work does the opposite: one global slope with a local anchor. This page argues the two belong together, "
    "states what would refute that, and lays out the study.",
)
st.html('<div class="jm-stats">'
        '<div class="jm-stat"><span class="v">35.7 → 55.2</span><span class="l">recall@10, J-lens → J++ (their evals, 27B)</span></div>'
        '<div class="jm-stat"><span class="v">60 %</span><span class="l">of that gain from Jacobian Filtering alone</span></div>'
        '<div class="jm-stat"><span class="v c-mu">0.81–0.98</span><span class="l">‖μ‖ / ‖h‖ in our captures: 0 is far from the data</span></div>'
        '<div class="jm-stat"><span class="v c-d">10 of 16</span><span class="l">experts at L8 / L16 under 2 % recall alone</span></div>'
        "</div>")

# ------------------------------------------------------------------ 1
ui.section("Each view of the J-lens has a slot for μ", "J++ App. D gives three complementary readings of the averaged "
           "Jacobian. None of them names an anchor, and each one needs one.", eyebrow="1 · Three views")
ui.figure(F.three_views(), "<b>The three views</b> (J++ App. D), with the place each one leaves for the centre. The workspace "
          "view asks what the model is <i>differentially</i> disposed to verbalise; the Taylor view needs an expansion point; "
          "the probe view gives one linear probe per token, and a probe without a bias is the odd choice.")
st.write("")
left, right = st.columns([1, 1.15], gap="large")
with left:
    ui.figure(F.probe_bias(), "<b>The probe view, one token.</b> The lens vector <i>p<sub>t</sub> = Jᵀ W<sub>U</sub>[t]</i> "
              "scores <i>p<sub>t</sub> · h</i>: a plane through the origin, far from every state. Centring moves the plane "
              "onto the data.", narrow=True)
with right:
    ui.prose(
        f"{JPP} remarks that the Jacobian transport is <i>“a homogeneous linear map rather than an affine map that can "
        "capture input-independent reweighting of the lens readouts”</i>. They tried a fitted bias and z-scoring, got mixed "
        "results, and removed non-semantic tokens after the fact instead (Readout Filtering, −2.9 pp when removed).",
        f"A centred lens is that affine map: {m('J (h − μ) = J h − J μ')}. The bias is not fitted to a score. It comes "
        "from the model's own geometry: the output the lens predicts at a reference state. In the probe view the bias of "
        f"token <i>t</i>'s probe is {m('− p<sub>t</sub> · μ', 'mu')}, so choosing μ chooses every probe's threshold at once.",
        "Their sample of non-semantic tokens (punctuation, “ the”, “ and”) is the readout of the wikitext mean we found "
        f"in U3: {JPP} keeps more of the corpus mean in its readout than the J-lens does. Readout Filtering removes "
        "part of what a centre removes, token by token.",
    )
    st.html(ui.note("key", "The thread through all three",
                    "The lens is a linearisation, and a linearisation is a slope plus an anchor. J++ studied the slope. "
                    "This project studies the anchor. LL studies the pair."))

# ------------------------------------------------------------------ 2
ui.section("J++ pairs each tangent with the wrong anchor",
           "An expert is the average Jacobian over one cluster, so it is the slope of the map <i>at that cluster</i>. "
           "J++ applies it to h, which anchors that slope at 0.", eyebrow="2 · The anchor mismatch")
left, right = st.columns([1.1, 1], gap="large")
with left:
    ui.figure(F.tangent_mismatch(), "<b>Schematic, one direction.</b> Each band is a cluster of real states. "
              "J<sub>2</sub> is the slope inside C<sub>2</sub>. Anchored at μ<sub>2</sub> (teal) it follows the curve. "
              "Anchored at 0 (dashed), it is wrong by a constant: the gap is the term the readout gets wrong for every "
              "state in the cluster.", narrow=True)
with right:
    ui.md(f"To first order, an expert is the tangent at its cluster's centre, "
          f"$J_i = \\mathbb{{E}}[J(h) \\mid h \\in C_i] \\approx J({MUI})$. The expansion that belongs to that tangent is")
    ui.eq(rf"f({H}) \;\approx\; f({MUI}) \;+\; J_i\,({H} - {MUI})", key=True,
          note="The consistent pair is (J<sub>i</sub>, μ<sub>i</sub>): the slope and the point it was taken at.")
    ui.md(f"J++ reads $J_i\\,{H}$. That equals the expansion above only if $f$ is linear through the origin. For a "
          "pre-norm residual stream the origin is the worst point to assume that: every block opens with an RMSNorm, "
          "which is singular at 0, and real states sit at 81–98 % of their norm away from it along the mean.")
    ui.md(f"The anchored version costs nothing at read time. With fixed weights it is one bias per layer: "
          f"$\\sum_i w_i J_i({H} - {MUI}) = J^{{++}}{H} - b$.")

# ------------------------------------------------------------------ 3
ui.section("Why the anchor should be local: the mean-value form",
           "The first-order expansion has an exact version. It says which slope goes with which anchor.", eyebrow="3 · Paths")
left, right = st.columns([1, 1.1], gap="large")
with left:
    ui.figure(F.segment_paths(), "<b>Schematic of residual space.</b> The slope that belongs to <i>h − m</i> is the "
              "Jacobian averaged along the segment from <i>m</i> to <i>h</i>. From 0 the segment leaves the RMSNorm "
              "singularity and crosses other regimes. From μ<sub>3</sub> it stays where J<sub>3</sub> was fitted. The "
              "global mean μ̄ is in between.", narrow=True)
with right:
    ui.eq(rf"f({H}) - f(m) \;=\; \Big[\int_0^1 J\big(m + t\,({H} - m)\big)\,dt\Big]\,({H} - m)", key=True,
          note="Exact for any m (fundamental theorem of calculus along the segment).")
    ui.prose(
        "A cluster-averaged Jacobian approximates the bracket well when both <i>h</i> and <i>m</i> lie in the cluster. "
        "The further apart they are, the more of the network's curvature the bracket has to average over, and the "
        "less any one fitted slope stands for it.",
        "This is integrated gradients with baseline <i>m</i>, averaged over a population: choosing μ is IG's "
        "baseline problem. IG's lesson applies here too: a zero baseline is a convention, not a neutral choice.",
        f"It also gives LL a measurable quantity. The first-order error {m('‖f(h) − f(m) − J(h − m)‖')} can be "
        "computed for each anchor by patching <i>m</i> in and running the rest of the network (H3 below), "
        "without scoring a single readout.",
    )

# ------------------------------------------------------------------ 4
ui.section("J++ relaxed the slope, never the anchor",
           "Readouts are linear in the anchor, so the design space has two axes: how local the slope is and how local "
           "the anchor is. J++ moved along one axis, this project along the other.",
           eyebrow="4 · The design space")
left, right = st.columns(2, gap="large")
left.html(ui.note("open", "What J++ App. E says",
                  "“There are two natural ways to relax the global linearity assumption: relax the <i>global</i> and have a "
                  "piecewise linear approximation, or relax the <i>linearity</i> and consider the second-order term.” "
                  "The piecewise experts turned out to be good across the whole distribution, and the authors came away "
                  "with <i>more</i> credence in global linearity."))
right.html(ui.note("key", "What it leaves open",
                   "Every expert in that test was anchored at 0. Our centres show that, with one global slope, a local "
                   "anchor helps a lot (fam, tok; label-free knnx8 and kmx64 in S4). Hypothesis: the slope can be global, "
                   "the intercept should be local."))
st.write("")
ui.figure(F.design_grid(), "<b>The readout family</b> R(h) = W<sub>U</sub> Σ<sub>i</sub> r<sub>i</sub>(h) J<sub>i</sub> "
          "(h − m<sub>i</sub>(h)). “In hand” cells have results in this repo or in the J++ paper; “new” cells are what LL "
          "adds. Two further axes are crossed sparingly: plain vs LRP Jacobians, and where the clusters come from.")

# ------------------------------------------------------------------ 5
ui.section("Your readout, in its two forms",
           f"Weighting each expert's own centred readout, {m('Σ<sub>i</sub> w<sub>i</sub> J<sub>i</sub> (h − μ<sub>i</sub>)')}, "
           "means two different things depending on whether the weights depend on h.", eyebrow="5 · Σ wᵢ Jᵢ (h − μᵢ)")
ui.figure(F.filter_vs_router(), "<b>Left: filter.</b> J++'s weights are fixed per layer, so the whole readout is one "
          "affine map: the released J++ map minus one bias. <b>Right: router.</b> Weights that depend on h give a "
          "piecewise-affine lens, a mixture of local linearisations; illustrative weights.")
st.write("")
left, mid, right = st.columns(3, gap="large")
left.html(ui.note("key", "Global weights: cheap, label-free",
                  "b = Σ w<sub>i</sub> J<sub>i</sub> μ<sub>i</sub> is computed once per layer. It needs no family label "
                  "and adds nothing at read time, so it is a candidate drop-in for both lenses."))
mid.html(ui.note("open", "Caveat: the weights are signed",
                 "J++'s w is unit-L2 and signed, not a convex mix. A negative-weight expert adds |w<sub>i</sub>| "
                 "J<sub>i</sub> μ<sub>i</sub> back. The offset may need its own weights v, or the weighted mean "
                 "μ<sub>w</sub> = Σ w<sub>i</sub>π<sub>i</sub>μ<sub>i</sub> / Σ w<sub>i</sub>π<sub>i</sub>."))
right.html(ui.note("open", "Routing, retried",
                   "J++ Fig 14: routing each item to its own cluster's expert hurt, since association items land on "
                   "bad experts. But those experts read J<sub>i</sub> h. If they are bad because of their anchor, "
                   "routing with anchors could work (H6)."))

# ------------------------------------------------------------------ 6
ui.section("Hypotheses, each with its refutation", eyebrow="6 · What LL tests")
ui.table(
    ["", "claim", "test", "refuted if"],
    [
        ["<b>H1</b>", "Consistent pair: J<sub>i</sub>(h − μ<sub>i</sub>) reads better than J<sub>i</sub> h and than "
         "J<sub>i</sub>(h − μ<sub>j</sub>), j ≠ i", "each expert alone × anchors", "the wrong cluster's μ<sub>j</sub> does as well (then it is generic centring)"],
        ["<b>H2</b>", "Bad-expert rescue: the experts J++ filters out gain the most from their own anchor",
         "recall alone vs anchored, per expert, L8–L56", "the filtered experts stay near zero (then they are noise, as J++ reads it)"],
        ["<b>H3</b>", "Linearisation: first-order error falls from 0 → global μ → μ<sub>i</sub> → kNN μ(h); bad experts have the largest",
         "patch m in, run forward; held-out positions", "error is flat in m (then anchors help only as counterfactuals)"],
        ["<b>H4</b>", "Global slope, local intercept: the intercept column carries most of the gain; slope locality matters only early",
         "the grid in §4, per layer", "routed slopes beat filtered ones late, or the intercept gain vanishes late"],
        ["<b>H5</b>", "Map and centre must be fitted together: refit w on centred inputs, and centring adds on J++'s own evals",
         "J++ fitter on centred / paired readouts", "centring still hurts J++ on its evals after the refit"],
        ["<b>H6</b>", "Routing returns: Σ r<sub>i</sub>(h) J<sub>i</sub>(h − μ<sub>i</sub>) beats the global-weight form",
         "routed vs filtered, same experts and anchors", "routing still hurts with anchors"],
    ],
)
st.write("")
left, right = st.columns(2, gap="large")
with left:
    ui.figure(F.rescue(), "<b>H2, schematic.</b> Experts alone (J++ Fig 3: at L8 and L16 most score under 2 %) and what "
              "H2 predicts when each reads from its own anchor.", narrow=True)
with right:
    ui.figure(F.depth(), "<b>H4, schematic.</b> J++ Fig 17: experts disagree early and agree late, so a local slope "
              "can only matter early. A local intercept has no such reason to fade.", narrow=True)

# ------------------------------------------------------------------ 7
ui.section("The plan", "Six phases. LL0 is the only large spend; everything after it reads stored experts.",
           eyebrow="7 · Programme")
ui.figure(F.roadmap())
st.write("")
ui.table(
    ["phase", "what", "gate / output", "cost"],
    [
        ["<b>LL0</b>", "Clone <code>jpp_lens</code> (LRP, router, fitter). One backward sweep that bins every source "
         "position into several clusterings at once (k = 8, 16, 64; wikitext and our corpus), accumulating Σ J, the "
         "count and Σ h per bin, so μ<sub>i</sub> is exactly the anchor of the positions behind J<sub>i</sub>. Plain "
         "gradient first, LRP second, J++'s 7 layers.",
         "k = 1 reproduces the pooled J-lens (cos ≥ 0.99); refit w on our LRP experts ≈ released J++ (recall@10 ≈ 0.594)",
         "≈ $100 (time one prompt first)"],
        ["<b>LL1</b>", "Cluster geometry, Fig 17 on ours, where val cells land; first-order error by anchor (H3)",
         "<code>out/analysis/LL1/</code>", "&lt; $5"],
        ["<b>LL2</b>", "Each expert × anchors {0, global μ, μ<sub>i</sub>, μ<sub>j</sub>, fam, knnx8} on our banks and "
         "J++'s held-out evals (H1, H2)", "the dumbbell plot, per layer", "reads only"],
        ["<b>LL3</b>", "The design grid, both Jacobian types, both router corpora; new map prefixes in "
         "<code>jlm.lens</code> so every centre composes (H4, H6)", "fit chooses, val confirms", "reads + judge"],
        ["<b>LL4</b>", "Refit w on centred inputs; separate offset weights; learned per-cluster offsets as a ceiling (H5)",
         "both scorers", "small"],
        ["<b>LL5</b>", "Path-integrated slope (JVPs along m → h), the second-order term, soft routing, depth schedule",
         "open", "open"],
    ],
)
st.write("")
left, right = st.columns(2, gap="large")
left.html(ui.note("key", "Controls",
                  "Random cluster assignment with the same sizes; μ<sub>j</sub> for j ≠ i (the pairing control); "
                  "<code>shuf.</code> / <code>rand.</code> of every new arm; k = 1 equals the pooled lens exactly. Echo, "
                  "prompt-masked pass@10, the mention control where a bank has one. Experts and anchors are fitted on "
                  "text that contains no val or bench item."))
right.html(ui.note("open", "Two scorers",
                   "Our banks are the primary objective (pass@10, fit chooses, val confirms, bench records). J++'s "
                   "held-out readout evals are the second: H5 is a claim about their ground, and a result there is "
                   "one they can check."))
st.caption("Written record: notes/iteration-anthony/local-linearisation/plan.md · source: Ayonrinde & Lindsey (2026), "
           "LessWrong nc9dHfcB22JdMzGbr, Methods, App. D, E, G.")
