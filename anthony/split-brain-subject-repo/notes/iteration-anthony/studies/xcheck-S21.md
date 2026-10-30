# Cross-check of B's S21 headline (A, j-lens-mean-2e, night-2, 03:58 BST)

Claim (studies/S21.md): `sched:40:s20xon:1:kmx64+s14t64` (S14k with S20x's leave-one-family-out correction below L40)
is +0.047 vs fam on val strict, +0.014 over S14k, guardrail ok; under rms only +0.006 vs rms fam.

Checked from `out/eval/<family>/val/summary.json` (synced 03:57), independently of B's tables:

| arm (val, strict) | typo | assoc | basic | mhop | mling | UM | DM | typo_mt | mhop_mt | basic_mt | mling_mt | macro |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S21 early-only, cos | 0.967 | 0.696 | 1.000 | 0.747 | 0.951 | 0.738 | 0.122 | 0.324 | 0.410 | 0.708 | 0.434 | 0.645 |
| S21 early-only, rms | 0.923 | 0.598 | 1.000 | 0.602 | 0.976 | 0.721 | 0.149 | 0.351 | 0.385 | 0.750 | 0.321 | 0.616 |
| S14k, rms | 0.901 | 0.706 | 1.000 | 0.590 | 0.963 | 0.803 | 0.162 | 0.378 | 0.359 | 0.750 | 0.321 | 0.630 |
| fam, rms | 0.901 | 0.765 | 1.000 | 0.566 | 0.927 | 0.787 | 0.095 | 0.432 | 0.308 | 0.708 | 0.226 | 0.610 |

- The cos numbers reproduce exactly (0.645, i.e. +0.046 vs fam's 0.599; B's +0.047 rounds the per-family differences).
- The rms caveat reproduces: under rms S21 (0.616) is below S14k (0.630); its multihop gain disappears (0.602 vs cos
  0.747) and association drops to 0.598. The correction was fitted through the cos map, so its gain is tied to that
  readout; S14k's gain is not (cos +0.032, rms +0.020).
- Mechanism check: S21's gain over S14k is typo (+0.055) and multihop (+0.096), the single-token families where S20's
  ceilings found the answer-class prior; S20x's correction is leave-one-family-out with twins out, so multihop's own
  targets do not enter it.

Verdict: B's headline stands as stated, including its own rms caveat; nothing to correct.
