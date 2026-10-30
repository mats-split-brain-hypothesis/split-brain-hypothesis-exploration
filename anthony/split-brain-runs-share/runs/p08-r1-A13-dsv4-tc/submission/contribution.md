# "Occupied-mind" steering — a concept-free maintenance direction

**What it does.** `vectors.pt` adds one vector per layer at the output of blocks 20–24, at the
`prefix` positions. With the plain J-lens read at layers 26/28/30 it scores strict
pass@10 = **0.775** on association `fit` (102 items; baseline 0.1275), mean log10 best rank
2.33 → 0.73. The readout itself is untouched — only the forward pass changes.

**Where the vector comes from.** A difference-of-means between two conditions I wrote myself,
read at the tokens the model *writes* rather than reads or answers. Both conditions force the
same neutral carrier sentence verbatim in the assistant turn; they differ only in the writer's
background cognitive state:

- positive: *"Keep one unspoken thought quietly in mind as you write. Now write exactly this
  sentence: «carrier»"*
- negative: *"Keep your mind entirely blank, with no unspoken thought, as you write. Now write
  exactly this sentence: «carrier»"*

Nothing is named, no benchmark item or target word appears anywhere, and the contrast moves only
the "occupied vs empty mind" axis. Averaging over 40 arbitrary carrier sentences gives a stable
direction; `vectors.pt` is `3.5 × (mean-occupied − mean-empty)` per layer in fp32 (the dose is
baked into the magnitudes, so the given `--scale 1.0` reproduces it).

**Why it works / where it came from.** The read cell is the final prompt token. Under the plain
J-lens the implied concept is present at the read band's *inlet* (layers 20–24, rank ~20–30) and
then dropped at 26–30, where the readout collapses onto a continuation prior (`The`, `At`,
`But`, …). Steering along the occupied/empty direction just below the band makes the layers
above keep developing the implied concept instead of only continuing the sentence; the steered
top-10 keeps the generic tokens and the target joins them. The "write-while-holding-something"
device is the white-bear stance of Raman et al. 2026, but with the object of thought removed:
their direction contrasts *think about an explicitly named concept* vs *don't think about it*,
built from the benchmark's own `directed_modulation` pairs. This one needs no named concept and
no benchmark pair at all, which isolates the load-bearing part of the white-bear effect as a
content-free maintenance mode.

**Controls.** At the same dose, the reversed direction scores 0.000 and a random direction of
matched per-layer norm scores 0.010 — both below baseline — so the effect is specific to this
direction and signed.