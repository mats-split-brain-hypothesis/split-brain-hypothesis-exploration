I steer Qwen3.5-4B's residual stream with a stance vector built from contrast
pairs I authored myself, not from the association targets or the bench's
`directed_modulation` family. Each pair shares a neutral carrier sentence and a
held concept; the two conditions differ only in stance: "Keep the {concept} in
your thoughts as you write exactly: {carrier}" versus "Keep ... out of your
thoughts as you write exactly: {carrier}". Concept and carrier match within each
pair, so they cancel; only the think/don't-think stance remains. I average the
residual at the carrier cells over 24 self-written pairs and take the difference of the two condition means as the per-layer vector. It is added at
blocks 20-24 (the mid-depth band where the model assembles implied concepts), at
the prefix position, at a large dose (≈1.13× the difference-of-means per layer).
The J-lens at L26/28/30 is unchanged.

To confirm the stance, not content surfacing, does the work, I built two
content-based alternatives from the same scenes: a concept-surfacing priming
contrast and a function-vector from few-shot scene→concept demonstrations. Both
are nearly orthogonal to the stance (cos ≤ 0.12 at L20-24) and both degrade
pass@10 below baseline at every dose. Only the stance lifts the targets. The
self-authored stance aligns at cos 0.89 with an independently constructed bench
stance, confirming a stable model direction, not an artefact of one prompt set.

Raman et al. (2026) showed a think/don't-think stance from the bench's
`directed_modulation` pairs lifts association pass@10 on a 5-read-layer window.
This submission is independent of that: the vector comes from self-authored
pairs (no bench stance items), the stance is isolated by two further failing
content contrasts, and delivery uses the prefix position with a dose re-tuned
for the 3-read-layer protocol.

Fit strict pass@10 rises 0.1275 → 0.7843; mean log10 best target rank
falls 2.33 → 0.72.
