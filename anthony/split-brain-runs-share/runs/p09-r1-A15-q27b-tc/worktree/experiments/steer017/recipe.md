# steer017: label-intent contrast (task jlens-steer-assoc-017)

The submitted intervention (`submission/vectors.pt`): v_l = mean_A(h_l) − mean_B(h_l), layers 20–24,
added at the read position with scale 0.25 (total push ~20 by L24). Fit: pass@10 0.1961 (20/102) vs
baseline 0.1275 (13/102); mean log-10 best target rank 1.9811 vs 2.3277. Random control (matched
per-layer norms, same dose): 0.1176 / 2.5023. Reversed: 0.0098 / 3.2667.

## Construction (rebuilds `submission/vectors.pt`)

1. 63 self-authored scene sentences spanning the family's subfamilies (activities, places, proper
   names, foreign items, abstractions); each names a single-token target. The scenes and names are in
   `prompts.json`. No scene or name was taken from the fit bank or its targets; the fit prompts were
   looked at only to avoid reuse, never to design the contrast.
2. Two chat prompts per scene (user turn only, no assistant):
   - A (label intent): "Name the thing this sentence describes, in one word: <scene>"
   - B (narrative prior): "Continue this sentence in a few words: <scene>"
3. Capture the 4B's residual stream at the **last token** of each prompt, layers 20–24, through the
   metric server (`tools/metric.py capture`, `"positions": "last"`).
4. v_l = mean over A's 63 last-token states − mean over B's 63 last-token states.

## Why (findings during the episode)

- The unsteered L26–30 readout at the read cell is dominated by the capitalised narrative-continuation
  prior ("The", "At", "But", "She", …, per the server's baseline examples); targets sit at mean log-10
  rank 2.33 (~211).
- The direction is not a logit bias read back: at the best dose it makes the layers above the band (25–29)
  write the item's own concept field into the read cell (e.g. crater → meteor/asteroid/telescope field,
  target rank 10 → 5), which is the same "computed, not read back" mechanism as WBS (Raman et al. 2026,
  papers/raman2026-white-bear-steering.md) — that paper's think/don't-think stance is the existing
  method this submission must not reproduce, so the contrast here is deliberately different: no concept
  is named in either condition, there is no suppression stance, and the direction is built from
  self-authored prompts at the answer-intent position.
- Dose: the effect appears only at total push of order the residual norm (peak ~20 by L24, i.e.
  scale ~0.2–0.3 on v_l); below ~10 it is invisible, above ~30 it overwrites the readout (pass@10 → 0).
  Position: read cell only is best ("prefix" 0.1863, "context" 0.1275 at scale 0.25).
- Contrasts that failed (all at the read position, swept doses): name vs continue captured at the
  mean over user/assistant tokens (instruction meta-discourse dominates); "what is this a description
  of" vs yes/no question; "keep in mind what it is about" vs read; focus vs glance; count-the-letter-e
  dual task vs read; memorize vs skim; multi-exemplar ICL naming vs counting (0.1863); "Name it:" /
  "Label:" short frames (fail); blank-in-middle anticipation (fails). The full-instruction naming
  imperative with the narrative-continuation negative is the strongest found.
- Ceiling of this family: ~20/102 items at the dose peak. The WBS stance reaches 0.83 on the same
  server setup; closing that gap with a non-reproduced contrast is the open problem.
