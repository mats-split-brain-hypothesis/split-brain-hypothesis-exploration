# Steering for the plain J-lens: activation vs. preference-suppression

**The vectors** (`vectors.pt`, one 2560-d vector per layer at layers 20–24, added at `prefix`
positions with `--scale 1.0`) raise strict pass@10 on the association `fit` split (102 items,
read at L26/28/30) from **0.1275 to 0.784** (mean log10 best target rank 2.33 → 0.73).

**The method.** Each vector is the difference of two condition means of the residual stream,
taken at the carrier cells of WorkspaceBench `directed_modulation` bench items — the same
family that white-bear steering (Raman et al. 2026) used, but a *different contrast*. The
positive pole is the 35 `think` items: five variants of an instruction to actively think
about a named concept (Think about / Keep in your thoughts / Hold in mind / Try to focus on /
Concentrate on, across ~20 concept categories) while copying a fixed carrier sentence. The
negative pole is the family's 15 `preference` items, which impose a **behavioural constraint
rather than a metacognitive instruction**: "You love {concept}, but you must not mention
this or hint at it in any way. Now write exactly this sentence: …". The contrast is thus
*engaging a named target in the imminent writing* minus *being constrained to keep that same
kind of target out of the writing* — no "don't think" command anywhere. Nothing was built
from, or optimised against, association items or their targets; both conditions come from
another family's bank through `capture`.

**Where it came from, and the mechanism.** I first screened a bank of generic contrasts
(narrowing/answer-slot, topic-settling, simultaneity, copy-tracking, plain-space slot
contrasts, and a mid-depth *velocity* construction: see `notes/steering-task.md` for the full
table) and found that the readout responds to exactly one axis of activation space: a
thought-control axis. Off-axis directions (cos ≤ 0.31) either do nothing or degrade
pass@10 monotonically with dose; on-axis directions improve it, at matched dose in
proportion to alignment (cos 0.84 → 0.34, 0.94 → 0.57, 1.0 → 0.69 at total push 20). Along
that axis the *suppression pole is exchangeable*: the "don't think about X" and "keep X
secret" states are geometrically indistinguishable (their difference is orthogonal to the
axis), and the three on-axis contrasts I could build — white-bear's think vs don't-think
(cos 1.0), think vs secret (cos 0.84), and this think vs preference-suppression (cos 0.94) —
all reach the same peak on the fit split (0.755 / 0.775 / 0.784, within three items), with
the dose optimum following 21/cos θ, θ the angle to the axis (observed total push 21 / 26 /
22, predicted 21 / 25 / 22 — only the on-axis component of the push is effective). The axis
selects for *single-concept* engagement: a contrast whose activation pole is a multi-concept
scene (think about a 2–3-concept picture vs no concept, cos 0.78) is on-axis but peaks
clearly lower (≈ 0.55 at a much higher dose). The steering effect is a property of the
axis, not of any particular pair. The
gain is computed, not read back: the push at 20–24 changes what layers 25–30 write at the
read position (they keep developing the passage's implied concept instead of collapsing to
the continuation prior), which the plain lens then reads — at total push 20 the read cell
alone carries 0.37 of the 0.57 prefix effect, and reversing the vector hurts (0.07). The
dose is narrow: 0.26 at 14, 0.44 at 18, 0.57 at 20, 0.65 at 21, **0.78 at 21.5–22**, 0.66 at
23, 0.46 at 28 (comparable in size to the read-cell residual norm); band 19–23
underperforms 20–24 (0.33).

**Relation to white-bear steering.** WBS reaches 0.83 on the bench split; the identical
recipe peaks at 0.755 on this fit split (total push 21; I reproduced it as a calibration
control). Our direction peaks at 0.784 — the same peak, three items higher, at a shifted
dose, which also shows it is a distinct direction on the axis rather than a rescaling of
WBS's vector (a rescaling would share u's curve and peak height). The novelty here is the
contrast, not the recipe: a new negative pole (behavioural preference suppression, no
metacognitive command) on the same control axis, justified by the exchangeability test and
by the off-axis screening showing that the readout selects for the axis rather than for any
particular content contrast. I would call this a new member of the thought-control steering
family — the first with a non-metacognitive suppression pole — rather than a different
family; the family itself was established by Raman et al.
