# Label-intent contrast

**Method.** For 63 self-authored scene sentences (activities, places, proper names, foreign
items, abstractions) I render two prompts sharing the sentence, differing only in the
instruction: (A) "Name the thing this sentence describes, in one word: scene" and
(B) "Continue this sentence in a few words: scene". I capture the 4B's residual stream at the
last token of each prompt and set v_l = mean_A(h_l) − mean_B(h_l) for layers 20–24. I add
0.25·v_l at the read position only, then read with the plain J-lens at layers 26/28/30. The
total push by layer 24 is about 20, on the order of the residual norm.

**Effect.** fit strict pass@10: 0.196 (20/102) vs 0.1275 unsteered (13/102); mean log-10 best
target rank 1.98 vs 2.33. The effect is signed and direction-specific: a matched-norm random
direction at the same dose scores 0.118, and the sign-reversed vector 0.010. Steered readouts
put the target inside the item's own concept field (crater joins meteor/telescope), so the gain
is written by the layers above the band, not read back as a logit bias.

**Where it came from.** The unsteered readout at the read cell is dominated by the
narrative-continuation prior; the depicted target sits a few hundred ranks below it. Condition B
is exactly that prior, condition A is the "about to name the depicted thing" state, so the
difference is a content-agnostic label-intent mode that lifts whatever the scene depicts.
Unlike white-bear steering (Raman et al., 2026) no concept is named in either condition, there
is no think/don't-think stance or thought suppression, and the direction comes from my own
prompts at the answer-intent position, not from directed-modulation bank items. Unlike the
attitude vectors of Herrera et al. (2026), this contrast targets an intermediate readout at
residual-norm dose, where generic steering becomes visible.
