"""Why centre: the linearisation argument, what mu holds, real cells read both ways, the mu ladder."""

import streamlit as st

import figures
import sources
import ui

ex = sources.examples(sources.stamp())

ui.header(
    "The case for centring",
    'Why read <span class="m">J<sub>l</sub> (<span class="c-h">h<sub>l</sub></span> − <span class="c-mu">μ<sub>l</sub></span>)</span> '
    'instead of <span class="m">J<sub>l</sub> <span class="c-h">h<sub>l</sub></span></span>',
    "The lens is a first-order approximation of the rest of the network. A first-order approximation is only good near the "
    'point where it is taken. The plain lens takes it at <span class="m">h = 0</span>, where no real residual lives. Centring '
    "moves the expansion point onto the data, and in doing so it turns the readout into a comparison against a chosen "
    "counterfactual.",
)

# ------------------------------------------------------------------ 1
ui.section("The plain lens expands around a point the model never visits", eyebrow="1 · The linearisation")
left, right = st.columns([1, 1], gap="large")
with left:
    ui.figure(figures.linearisation(), "<b>Schematic, one direction.</b> The curve stands in for the network from block "
              "<i>l</i> to the output. Near the data, the tangent taken at <i>μ</i> tracks it; the tangent at 0 is off by a "
              "large, input-independent offset.", narrow=True)
with right:
    ui.prose(
        'Write <span class="m">f</span> for the map from the block-<i>l</i> residual to the final residual. The lens matrix '
        '<span class="m">J<sub>l</sub></span> is the average Jacobian of <span class="m">f</span> over a corpus, so it is a '
        "slope. A slope is only a prediction once you say where it is anchored.",
        'The released lens reads <span class="m">J<sub>l</sub> h</span>. That is the first-order expansion '
        '<span class="m">f(h) ≈ f(0) + J h</span> anchored at the origin. Real residuals are nowhere near the origin: in the '
        "captures, the mean alone is 81 to 98 % of the norm of a typical state.",
        'Anchoring at a real point <span class="m c-mu">μ</span> gives',
        '<span style="font:italic 21px var(--f-display);color:var(--ink);padding-left:16px">f(h) − f(<span class="c-mu">μ</span>) '
        '≈ J<sub>l</sub> (h − <span class="c-mu">μ</span>)</span>',
        "The left side is the coherent quantity to read: how the output at this cell differs from the output at the reference "
        'point. The argument justifies centring. It does not say which <span class="m c-mu">μ</span> to use. That is the open '
        "question.",
    )
    st.page_link("views/maths.py", label="The full expansion, error terms and least-squares argument", icon=":material/function:")

# ------------------------------------------------------------------ 2
ui.section('Most of <span class="m c-h">h</span> is the same for every input', eyebrow="2 · What the centre holds")
left, right = st.columns([1, 1], gap="large")
with left:
    ui.figure(figures.decomposition("  ".join(t.strip() for t in ex[0]["fam"][:3]) if ex else "attack  Attack"),
              "<b>Schematic.</b> The plain lens reads <i>J μ + J δ</i>. The shared part <i>J μ</i> decodes to the model's "
              "continuation prior and swamps the item-specific part.", narrow=True)
with right:
    st.html('<div class="jm-stats">'
            '<div class="jm-stat"><span class="v c-mu">0.81–0.98</span><span class="l">‖μ‖ / ‖h‖ at the read layers</span></div>'
            '<div class="jm-stat"><span class="v c-d">41–69 %</span><span class="l">of the norm removed by subtracting μ</span></div>'
            '<div class="jm-stat"><span class="v">≈ 4 %</span><span class="l">of output variation the mean Jacobian explains</span></div>'
            "</div>")
    st.write("")
    ui.prose(
        "Decoded on its own, the mean reads as end-of-turn, a paragraph break and sentence starters. That is what the plain "
        "lens shows on most cells, and it is the same for every input. The item-specific signal lives in the short remainder "
        '<span class="m c-d">δ</span>.',
        'Both readouts are linear in <span class="m">h</span>, so <span class="m">L(h − μ) = L(h) − L(μ)</span>. With one '
        '<span class="m c-mu">μ</span> per layer, centring subtracts a fixed score from each vocabulary token. That alone '
        + (f"moves the target from rank {ex[0]['rank_zero']} to rank {ex[0]['rank_fam']} in the first example below."
           if ex else "moves targets from deep ranks into the top 10."),
        '<span style="font-size:13px;color:var(--muted)">Sources: jle x98 (norms), umot research log 2026-10-09 (the expansion '
        "argument), umot <code>taylor_screen.py</code> (the 4 %).</span>",
    )

# ------------------------------------------------------------------ 3
ui.section("The same cell, read plain and centred",
           "Typo dev bank, <code>val</code> split. The read cell is the misspelled word's last token. Centre: the typo family "
           "mean fitted on the <code>fit</code> split, so these items never contributed to it. Cos readout.",
           eyebrow="3 · On real cells")
for e in ex:
    prompt = ui.esc(e["prompt"]).replace(ui.esc(e["typo"]), f"<mark>{ui.esc(e['typo'])}</mark>")
    st.html(f"""<div class="jm-ex">
  <div class="hd"><span class="prompt">{prompt}</span>
    <span class="loc">{e['id']} · L{e['layer']} · read “{ui.esc(e['read'])}” · target <b style="color:var(--delta)">{ui.esc(e['target'])}</b></span></div>
  <div class="row plain"><div class="lab"><b>plain J h</b>target rank {e['rank_zero']}</div>{ui.chips(e['zero'], e['target'])}</div>
  <div class="row cent"><div class="lab"><b>centred J (h − μ)</b>target rank {e['rank_fam']}</div>{ui.chips(e['fam'], e['target'])}</div>
</div>""")
if not ex:
    st.info("The typo/val readouts are not in out/eval on this machine.")

# ------------------------------------------------------------------ 4
ui.section(
    'Choosing <span class="m c-mu">μ</span> is choosing the counterfactual',
    'Write <span class="m c-mu">μ = E[h | C]</span>: the expected state given some part <i>C</i> of the input. Whatever '
    "<i>C</i> fixes is removed from the readout, and whatever it leaves free stays. Every centre tried so far is one rung "
    "on this ladder.",
    eyebrow="4 · The choice",
)
ui.figure(figures.ladder(), "<b>The ladder, with results already in hand.</b> Bar height is a schematic of how much of the "
          "state each centre explains. The numbers are strict pass rates or judged rates from <code>notes/synthesis.md</code> "
          "(jle x97–x101, umot). Tighter matching removes more background, but past a point it starts to remove or echo the "
          "prompt itself, which the mention control detects.")
st.write("")
left, right = st.columns(2, gap="large")
left.html(ui.note("key", "What the evidence says",
                  "The gain comes from a matched counterfactual, not from a better expansion point. The lens's own fit-corpus "
                  "mean linearises better (held-out R² −0.13 → 0.15 at L42) and still reads no better. Adding the Taylor "
                  "constant back changes nothing."))
right.html(ui.note("open", "The open problem",
                   'A label-free, context-matched <span class="m c-mu">μ</span>. One mean per layer works on WorkspaceBench '
                   "because every item reads the same template cell. On free text the read cells vary, so "
                   '<span class="m c-mu">μ</span> must follow the token and context without crossing into the prompt. '
                   "First answers on the dev banks: <i>Constant μ exploration</i> (model-written references from a few "
                   "example prompts match the family mean on association)."))
