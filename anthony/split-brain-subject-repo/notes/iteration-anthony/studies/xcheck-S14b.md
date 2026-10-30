# Cross-check of A's finalist S14b (sched:40:kmx64+s14:template:64:mean=kmx64:a=0.5)

By j-lens-mean-e1 (night-2 instance B), steward's card, 04:09 BST. A's study: studies/S14.md (S14b, val 6). Read-only on A's
files; job `experiments/jobs/e1_xcheck_s14b.sh`; seeds `src/jlm/mu/xcheck_e1.py`. Strict, val, cos. A already ran rms
(+0.037 vs rms fam).

**Status** (04:10 BST): done. S14b is seed-stable (+0.039 to +0.047) and its DM gain is not same-carrier leak. **Headline
caveat: it is not bench-free**: with chat-corpus clusters instead of bench-cell clusters it falls to +0.005 (association,
UM and DM lose their gain). The late-knnxs8 swap (+0.055) is **val-selected and unconfirmed** (seen first on val; A to
screen on fit).

| arm (S14b with ...) | typo | assoc | mhop | UM | DM | typo_mt | mhop_mt | basic_mt | mling_mt | macro | vs fam | w/o UM, DM |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fam | 0.923 | 0.745 | 0.614 | 0.721 | 0.054 | 0.378 | 0.256 | 0.688 | 0.340 | 0.599 | 0 | 0 |
| S14k (= S14b without the late kmx64 term) | 0.912 | 0.686 | 0.651 | 0.721 | 0.135 | 0.351 | 0.385 | 0.708 | 0.453 | 0.631 | +0.032 | +0.031 |
| S14b (A, k-means seed 0) | 0.934 | 0.765 | 0.651 | 0.787 | 0.230 | 0.351 | 0.359 | 0.708 | 0.321 | 0.642 | +0.043 | +0.026 |
| seed 1 | 0.945 | 0.755 | 0.627 | 0.754 | 0.230 | 0.405 | 0.359 | 0.729 | 0.377 | 0.646 | +0.047 | +0.034 |
| seed 2 | 0.934 | 0.735 | 0.627 | 0.770 | 0.203 | 0.378 | 0.359 | 0.708 | 0.358 | 0.637 | +0.039 | +0.025 |
| pool = chat-corpus clusters (k 128, no bench cells) | 0.912 | 0.618 | 0.651 | 0.639 | 0.108 | 0.378 | 0.359 | 0.708 | 0.321 | 0.604 | +0.005 | +0.010 |
| late mean = knnxs8 (fair kNN, no same-carrier members) | 0.945 | 0.784 | 0.687 | 0.770 | 0.230 | 0.351 | 0.385 | 0.750 | 0.340 | 0.654 | +0.055 | +0.043 |
| late mean = knnx8 | 0.945 | 0.784 | 0.687 | 0.787 | 0.230 | 0.351 | 0.385 | 0.750 | 0.340 | 0.655 | +0.057 | +0.043 |

(basic_readout 0.971-1.000, multilingual 0.939-0.951 throughout.)

## Findings

1. **Seed-stable**: +0.039 / +0.043 / +0.047 over three k-means seeds (without UM / DM +0.025 to +0.034).
2. **Bench-free pool fails**: chat-corpus clusters in both places give +0.005 (association 0.618, UM 0.639, DM 0.108):
   S14b's gain over S14k needs clusters of bench cells, more so than S14k did (+0.017 there).
3. **The DM caveat, sized.** S14b's DM gain over fam (+0.18) splits into the S14k part (+0.08: early kmx64 + late
   template removal) and the late kmx64 term (+0.10). Replacing that late cluster mean with the fair kNN mean (knnxs8:
   no neighbour shares the read cell's carrier) keeps DM at 0.230, as does knnx8: **the late term's DM gain does not
   come from same-carrier members**. By cell type S14b's 17 DM strict passes are 14 sentence-final and 3 mid-sentence
   only (S14k: 7 / 3; knnx8: 17 / 5): the added passes are all at sentence-final "." cells, the type pilot-1 called
   defensible. So pilot-1's same-sentence caveat does not explain S14b's DM gain. **Confirmed by the judge (A, Haiku
   DM val, L24-60)**: S14b 0.395 [0.29, 0.50], S14k 0.303, fam 0.224 (fair references u1rel 0.566, u1endcar 0.645, knnxs8 0.658).
4. **A stronger late mean (val-selected, unconfirmed)**: with knnxs8 as the late partial mean the schedule reads +0.055 (+0.043 without UM / DM;
   multihop 0.687, multilingual_mt 0.340 = fam). This was seen on val (a cross-check arm), so it is a candidate for A to
   screen on fit, not a result (passed to A).
