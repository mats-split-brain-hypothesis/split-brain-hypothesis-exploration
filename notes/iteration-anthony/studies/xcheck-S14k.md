# Cross-check of A's finalist sched:40:kmx64+s14t64 (S14k)

By j-lens-mean-e1 (night-2 instance B), on the steward's card, 03:40 BST. A's study: studies/S14.md (S14k, val 5). Read-only
on A's files; arms run by B: `kmx64s1` / `kmx64s2` (`src/jlm/mu/xcheck_e1.py`), job `experiments/jobs/e1_xcheck_s14k.sh`,
per-unit `experiments/e1_units.py` -> `out/analysis/xcheck-S14k/mt-units.md`. Strict only (no judge: strict is not
blind here, A judged the _mt four already).

## Results (val, strict / piece proxy, references = fit)

| arm | typo | assoc | basic | mhop | mling | UM | DM | typo_mt | mhop_mt | basic_mt | mling_mt | macro | vs fam | w/o UM, DM |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fam (cos) | 0.923 | 0.745 | 0.914 | 0.614 | 0.951 | 0.721 | 0.054 | 0.378 | 0.256 | 0.688 | 0.340 | 0.599 | 0 | 0 |
| sched:40:kmx64+s14t64 (A, seed 0) | 0.912 | 0.686 | 1.000 | 0.651 | 0.939 | 0.721 | 0.135 | 0.351 | 0.385 | 0.708 | 0.453 | 0.631 | +0.032 | +0.031 |
| same, k-means seed 1 | 0.945 | 0.686 | 1.000 | 0.651 | 0.939 | 0.721 | 0.135 | 0.378 | 0.359 | 0.708 | 0.453 | 0.634 | +0.036 | +0.034 |
| same, k-means seed 2 | 0.923 | 0.657 | 1.000 | 0.651 | 0.939 | 0.721 | 0.135 | 0.378 | 0.359 | 0.708 | 0.434 | 0.628 | +0.029 | +0.027 |
| kmx64 alone, seed 0 / seed 1 | | | | | | | | | | | | 0.631 / 0.618 | +0.032 / +0.019 | +0.009 / -0.001 |
| pool = chat-corpus clusters, k 128 (no bench cells) | 0.901 | 0.618 | 1.000 | 0.639 | 0.951 | 0.639 | 0.122 | 0.378 | 0.385 | 0.708 | 0.434 | 0.616 | +0.017 | +0.023 |
| pool = chat-corpus clusters, k 32 | 0.912 | 0.608 | 1.000 | 0.639 | 0.939 | 0.656 | 0.122 | 0.378 | 0.385 | 0.708 | 0.434 | 0.616 | +0.018 | +0.021 |
| sched:40:fam+s14t64 (A) | 0.923 | 0.676 | 1.000 | 0.651 | 0.939 | 0.672 | 0.122 | 0.351 | 0.359 | 0.708 | 0.472 | 0.625 | +0.026 | +0.030 |
| **rms readout**: fam | 0.901 | 0.765 | 1.000 | 0.566 | 0.927 | 0.787 | 0.095 | 0.432 | 0.308 | 0.708 | 0.226 | 0.610 | 0 (rms) | 0 |
| rms: sched:40:kmx64+s14t64 | 0.901 | 0.706 | 1.000 | 0.590 | 0.963 | 0.803 | 0.162 | 0.378 | 0.359 | 0.750 | 0.321 | 0.630 | +0.020 | +0.015 |
| rms: same with the rms-map basis | (identical to the row above) | | | | | | | | | | | 0.630 | +0.020 | +0.015 |
| rms: sched:40:fam+s14t64 | 0.901 | 0.696 | 1.000 | 0.602 | 0.951 | 0.770 | 0.149 | 0.351 | 0.359 | 0.750 | 0.321 | 0.623 | +0.012 | +0.011 |

Per unit (_mt, val, piece proxy): multilingual_mt language 0.79 (fam 0.62, kmx64 0.49, s14t64 0.85), concept 0.92;
multihop_mt bridge2 0.67 (= zero; fam 0.22); basic_readout_mt language 0.89 (fam 0.78). Same as A's judged profile.

## Findings

1. **Seed-stable**: +0.029 / +0.032 / +0.036 over three k-means seeds (without UM / DM +0.027 to +0.034), although
   kmx64 alone moves by 0.013 between seeds: the late s14t64 sets the schedule's profile (A's insight 12), the early
   cluster mean only adds association / UM at mid depth.
2. **Holds under rms at two thirds of the size**: +0.020 vs rms fam (+0.015 without UM / DM), with the same shape
   (multilingual_mt +0.10, multihop_mt +0.05, DM +0.07, association -0.06). The cos-map and rms-map template bases give
   identical readouts: both span {J^T W_U[t]}, and the readouts differ only in per-token scaling, which a span ignores.
3. **The early pool matters, the late part does not need it**: replacing the bench k-means clusters with clusters of the
   chat-format corpus (no bench cells at all) keeps the _mt profile and multihop but loses association (0.618 vs 0.686)
   and UM: +0.017 / +0.018, below sched:40:fam+s14t64 (+0.026). So the bench-cell clusters carry the template match on
   association; a fully bench-free version exists at about half the gain.
4. Not checked: a judged rms run, and the mention control on a carrier-sharing pool for the kmx64 part (A cites S4's
   mention control with pilot-1's caveat).
