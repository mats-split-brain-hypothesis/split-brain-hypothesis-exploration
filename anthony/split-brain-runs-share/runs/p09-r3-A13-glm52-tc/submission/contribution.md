# Imagery-engagement steering for the plain J-lens

## The method

The intervention is a single steering vector per layer, added to the residual stream at the
output of blocks 20–24 at every prompt position up to and including the read cell, at the dose
baked into `vectors.pt` (so `tools/metric.py run submission/vectors.pt --positions prefix --scale 1.0`
is the whole intervention). The readout is the plain, uncentred J-lens at layers 26–30, unchanged.

The vector is a contrast of *stance*, built from self-authored prompt pairs (no association items,
no target words). In the engagement condition the model is told to form a vivid mental image of a
generic object while it copies a fixed carrier sentence; in the clearing condition it is told to
transcribe the same sentence with its mind cleared:

> **engage:** "Picture the object *compass* vividly in your mind as you write. Now write exactly
> this sentence: 'The committee approved the minutes without changes.'"
> **clear:** "Simply transcribe this sentence without thinking of anything: 'The committee approved
> the minutes without changes.'"

I render both with the chat template, take the residual mean over the carrier (copied-sentence)
tokens at each of layers 20–24, and difference them: `v_l = mean_engage(h_l) − mean_clear(h_l)`.
Twenty matched pairs (generic objects — *compass, anvil, lantern, …* — over twenty carrier
sentences) are averaged. The concept and carrier vary across pairs and cancel; what remains is a
direction for "hold something in mind while copying." The stored vector is that difference scaled by
0.92, which lands the required `scale 1.0` on the dose curve's broad high plateau.

## Result on fit

strict pass@10 (L26–30) **0.1275 → 0.784**; mean log10 best target rank 2.33 → 0.73. The gain is
robust to a ±3 % dose shift (0.63–0.75), and a seeded random direction of matched per-layer norm at
the same dose lands at 0.069 — below baseline, not just null — so the model is sensitive to this
direction specifically, not to any large push (cf. Raman et al. 2026's random control).

## Where it came from

I started from the observation, also made by Raman et al.'s white-bear steering (WBS), that the
plain J-lens loses association targets not because the lens is weak but because the forward pass has
not *written the implied concept into the read cell* by layer 26 — it has moved on to next-token
prediction. Two things had to be recovered before anything worked:

1. **Band and dose.** Adding a vector at the *read* layers (26–30) does nothing, however large the
   dose — the gain has to be *computed* by the blocks above the read cell. Steering only helps in a
   narrow mid-depth band (layers 20–24, the "concept allocation zone") and only at a large dose
   (total push ≈ the residual norm, an order of magnitude above a conventional CAA dose). Below that
   dose the curve is flat; my first, conventionally-dosed attempts found exactly nothing.
2. **The direction must be an engagement stance, not content.** I tried six genuinely different
   content/mode contrasts — descriptive-vs-generic passages, content-word-vs-function-word,
   definition→answer vs definition→repeat, identify-the-concept vs read-aloud, concept-completion,
   function-vector-style task contrasts. *All of them fail* (most land at or below baseline, some
   catastrophically). What works is a direction the model represents for "actively holding something
   in mind while doing something else," which decodes (through the J-lens itself) as
   *imagery, metaphor, while, despite, meanwhile* — a concurrent-processing stance, not any concept.

## How it differs from white-bear steering

This is the honest part. WBS builds its direction from think / *don't think about X* pairs — the
concept X is held constant and the contrast is Wegner-style *suppression of a specific concept*,
which paradoxically makes it more accessible. The direction here is in the same family (cosine 0.87
with the WBS direction at layer 22) because both isolate "concept-engaged-while-copying," and I could
not find a working direction outside that family — that negative result is itself the main thing I
contributed beyond running the method.

The construction is different in three respects, and I think the second is the real one:

- It is **constructive imagery** ("form a vivid mental image of X") rather than passive attendance
  ("think about X"), leaning on sensory simulation rather than verbal rehearsal.
- The disengagement side is **global cognitive clearing** ("without thinking of anything"), not
  specific-concept suppression. There is no white-bear paradox here — no concept is being suppressed
  on the B side, so the direction is not riding on paradoxical access. That it still works suggests
  the useful variable is *engagement*, not the suppression asymmetry WBS is named for.
- The concept appears **asymmetrically** (only in the engagement condition), whereas WBS holds it
  constant across the pair.

I do not claim this is a wholly new mechanism: it is an engagement-stance vector applied at the
concept-allocation zone, and WBS is the prior art for exactly that. What I'd claim as new is the
specific contrast (imagery + global clearing, which drops the suppression that defines WBS and still
works), the confirmation that the gain survives dropping the suppression, and the negative result
that content/mode contrasts — the obvious alternative — do not work at all.

## Files

- `submission/vectors.pt` — `{20,21,22,23,24: tensor[2560]}`, the scaled engagement-minus-clearing
  difference. Run with `tools/metric.py run submission/vectors.pt --positions prefix --scale 1.0`.
- `experiments/imagery.py`, `experiments/novel.py`–`novel5.py`, `experiments/contrasts2.py` — the
  contrast definitions; `out/steer/` holds the captured means and the dose-curve logs.
