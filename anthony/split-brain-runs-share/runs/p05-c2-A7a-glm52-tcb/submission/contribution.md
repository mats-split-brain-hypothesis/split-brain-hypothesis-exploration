# Bank-free stance steering for the plain J-lens

I steer the forward pass with a **stance direction built entirely from self-authored
contrast prompts**, with no dependency on any WorkspaceBench bank. The contrast mimics the
*form* of a thought-suppression stance — "think about concept X while you copy this sentence"
versus "do not think about concept X while you copy the same sentence" — but the 32
concept/carrier pairs are my own, chosen across domains unrelated to the association targets.
Within each pair the concept and carrier are matched, so they cancel and only the stance
remains.

For each layer `l` in 18–26 I captured the residual at the assistant's carrier tokens for both
conditions (chat render, `positions=assistant`) and took the contrast

    d_l = mean_think(h_l) − mean_don't-think(h_l).

This is a contrast between two conditions, not a mean or centring term. The per-layer gap
`‖d_l‖` is 4.45–5.83 at layers 20–24, matching the magnitude of bank-derived stance
directions. The submitted vector at each steered layer is `0.13·d_l`, so `--scale` is the dose.

The reading-list stance-steering paper (Raman et al. 2026) lifts association pass@10 but
builds its direction from WorkspaceBench's `directed_modulation` bank. I removed the bank
entirely to test whether the direction is a property of the bench or of the stance. The stance
wording and the mid-depth band (layers 20–24, where concepts assemble) come from that work; the
contrast source, the dose and the bank-free constructibility are this submission's contribution.

Vectors at layers 20–24, added at every position up to and including the read cell
(`--positions prefix`), dose `--scale 7.0`. On association `fit` (102 items) this raises strict
pass@10 from 0.1275 to **0.716** (mean log10 best rank 2.33 → 0.75). The dose curve peaks
sharply at 7 (k=6 → 0.52, k=8 → 0.54); the useful region is narrow and well above
conventional doses.
