# Referent-holding stance steering

**The method.** Add a fixed steering vector, one per layer, to the residual stream of Qwen3.5-4B at
layers 20-24, at the prompt positions up to the read position, and read with the plain uncentred
J-lens at layers 26, 28, 30, unchanged. The vector is a *direction*, constructed as a contrast: 16
matched prompt pairs, one telling the model to think about a given concrete concept while copying
a neutral sentence, the other telling it not to, with concept and sentence identical within a
pair. Content cancels in the per-layer difference of means, so the direction carries the stance
toward a referent but no concept content: it is stable under leave-one-pair-out (cosine >= 0.998)
and nearly orthogonal to content contrasts on the same model, which do not move the readout at
any dose.

**The dose.** The effect sits in a large, narrow band: a per-layer push of about 1.2x the contrast
norm (about 7 units). At three quarters of that the pass rate roughly halves; at about 1.8x the
steering rewrites the readout and the score has collapsed back to baseline. Conventional small
doses fall in a flat region.

**The mechanism.** The vector is not read back: the same dose injected at the read layers
themselves leaves the readout at baseline, a random direction in the principal subspace of the
residual at the same dose does nothing, and a reversed dose lowers the score. The gain is
computed: the blocks above the band write the implied concept into the read position instead of
dropping it in favour of next-token prediction.

**Result.** On association fit (102 items), strict pass@10 rises from 0.1275 to 0.7549 and mean
log10 best target rank falls from 2.33 to 0.74, with one content-free vector per layer and no
change to the readout.
