# Cross-check of A's label-free finalist S14b-x

By j-lens-mean-e1 (night-2 instance B), steward's card, 06:05 BST. Arm `sched:40:kmx64+s14:template:64:mean=knnxs8:a=0.5`
(A, studies/S14.md, finalist battery 05:43). Offline, from stored readouts and judged results; no new judge or read.

## Every headline number reproduces (independent code)

| claim (A) | B's recomputation | how |
|---|---|---|
| val strict cos +0.055, guardrail ok | **+0.055**, no family's 95 % paired interval below 0 (typo_mt -0.027 [-0.081, 0.000] is the closest) | per-item passes from the readouts (strict / piece proxy, `s23_select.tables`), item bootstrap per family |
| val strict rms +0.046, guardrail ok | **+0.046**, guardrail ok (typo_mt -0.054 [-0.162, +0.054], multilingual_mt -0.038 [-0.151, +0.057]) | same |
| DM Haiku 0.487, think 23 / dont_think 6 / suppress 8 | **0.487; 23 / 6 / 8** (fam 0.224; 14 / 2 / 1) | pass = gold picked with a content-bound basis at any judged cell, own code, split by the bank's polarity |
| mention control 0.76 / 0.14 (carrier-sharing pool) | **0.76 / 0.14** (bench pool 0.68 / 0.10; no carrier exclusion 0.81 / 0.18) | `out/analysis/S14/mention-final/summary.json` |
| judged multilingual_mt -0.094 [-0.189, 0.000] | **-0.094 [-0.189, +0.000]**, 1 won / 6 lost of 53 | paired item bootstrap on the judged rows |

## Who the late neighbours are (`experiments/e1_knn_composition.py`, val read cells, L52)

| bank | same family | base rate | same family + subfamily (template) | base rate |
|---|---|---|---|---|
| typo | 0.99 | 0.04 | 0.33 | 0.01 |
| association | 1.00 | 0.04 | 0.59 | 0.01 |
| basic_readout | 0.89 | 0.01 | 0.89 | 0.01 |
| multihop | 0.95 | 0.03 | 0.68 | 0.01 |
| multilingual | 0.91 | 0.03 | 0.61 | 0.01 |
| user_modeling | 1.00 | 0.50 | 0.87 | 0.29 |
| directed_modulation | 1.00 | 0.27 | 0.66 | 0.14 |
| typo_mt | 0.83 | 0.02 | 0.78 | 0.01 |
| multihop_mt | 0.83 | 0.02 | 0.54 | 0.01 |
| basic_readout_mt | 0.78 | 0.02 | 0.69 | 0.01 |
| multilingual_mt | 0.94 | 0.02 | 0.94 (one subfamily) | 0.02 |

Same family **and same prompt language** (the _mt banks' `lang`): multilingual_mt 0.58 (base 0.002), basic_readout_mt
0.59 (0.008), typo_mt 0.83 (0.019).

**Findings.**
1. All of A's numbers reproduce exactly; nothing to correct.
2. **The late knnxs8 mean is in effect a within-family, mostly within-template mean, found without a label**: 78-100 % of
   the 8 neighbours come from the read cell's family (base 1-50 %), 33-94 % from its subfamily. The template it subtracts
   (half of it, alpha 0.5) is the same shared form fam subtracts; the item's own sentence is excluded (carriers), so the
   template carries no item content. The prompt-reading risk that remains is the one the mention control measures
   (0.14 mentioned, carrier-sharing pool), which is at u1rel's level.
3. **The multilingual_mt cost has S10's mechanism**: on the _mt banks the neighbours share the item's prompt language
   58-83 % of the time (base under 2 %), so the late half-mean subtracts half of the language direction; the judged
   language unit is where multilingual_mt loses (-0.094, upper bound 0.000). Any label-free kNN late mean will do this
   unless neighbours of the same prompt language are excluded (a cheap variant: knnxs8 with a same-script exclusion).

**Follow-up (A, studies/S14.md):** finding 3's suggestion, the late knnxs8 neighbours restricted to other prompt languages
(language detected from the prompt text; "S14bL"), reads val +0.060 cos / +0.062 rms, guardrail ok under both, and judged
multilingual_mt 0.340 = fam (S14b-x 0.245), language unit 0.87; the bank-field version 0.358. Val-informed (the fix was
designed from this val cross-check), and the fresh splits test only the English families: an untested candidate for a
future held-out _mt split.

## Cross-check of S14bL (steward's card, 06:16 BST)

Arm `sched:40:kmx64+s14:template:64:mean=knnxd8l:a=0.5` (A, studies/S14.md, screen 20).

1. **The language is detected from prompt text only.** `S14.detect_language` reads `prompt` (or the messages' content):
   the dominant non-Latin script (>= 30 % of letters), else Latin-script function words and diacritics from a hand list;
   `detected_language` maps every bank item id to that guess. No bank field, label or target is read. One process-level
   caveat (not affecting S14bL): the pool's `langs` is shared and the bank-field class (`knnxl8`, "S14bl") only sets it
   when absent, so a bank-field arm evaluated after a detected one in the same process would reuse the detected
   languages; S14bl's numbers should be checked for run order.
2. **Val reproduces** (independent per-item scoring + bootstrap): cos +0.060 vs fam (+0.049 without UM / DM), rms +0.062
   (+0.050), **guardrail ok under both**; vs S14b-x +0.005 cos / +0.016 rms, all of it multilingual_mt (+0.075 cos,
   +0.189 rms) with association -0.020 cos / +0.010 rms (the detector's misreads of English association prompts).
3. **Not an exact no-op on val2.** Detected languages on val2: typo 88 / 88 and multihop 129 / 129 English (exact no-op
   there: S14bL = S14b-x), but association 82 English and 7 not (es 3, fr 2, de 1, it 1; some may be genuinely
   foreign-language items, which association contains). So val2's S14b-x number (+0.052) transfers to S14bL exactly on two
   families; on association it can differ on at most 7 of 89 items (macro at most +-0.026). Confirming S14bL on val2 needs
   one read of that arm (association only would suffice).

Follow-up (A): the shared-language-list issue was real and fixed (S14bl's `knnxl8|rms` val 0.666 withdrawn, the others
stand); S14bL's registered val2 read: +0.052 cos / +0.046 rms vs fam, association 0.899 = S14b-x (the 7 detected cells
pass the same), so S14bL = S14b-x on val2.
