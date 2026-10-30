# Cross-check of B's knnxs8 (S16c) on DM: polarity selectivity (A, j-lens-mean-2e, night-2, 04:30 BST)

Steward's question: knnxs8's DM passes are mostly at the sentence-final cell (17 / 19 strict); is it reading the
carrier's end-of-sentence position (the prompt) rather than what the model holds? A test inside the DM bank itself:
every val pair has a **think** twin ("keep X in your thoughts"), a **dont_think** twin ("don't think about X") and
**suppress** items; all three *mention* X in the prompt, only "think" asks the model to hold it. A centre that surfaces
what the model holds should keep the uncentred lens's contrast between them; a prompt reader surfaces X under every
polarity.

Haiku (val, layers 24 / 36 / 48 / 60; pass = gold picked and content-bound at any judged cell; from each arm's
`judged-claude-haiku-5.5-L24-36-48-60/results.json`; totals reproduce the reported numbers). In brackets: items whose
only passing cells are sentence-final.

| arm | think (26) | dont_think (26) | suppress (24) | total | think - dont_think |
|---|---|---|---|---|---|
| zero | 11 (0) | **0** (0) | 2 (0) | 0.171 | +11 |
| fam | 14 (0) | 2 (0) | 1 (0) | 0.224 | +12 |
| s14t64 (A) | 18 (2) | 1 (0) | 3 (2) | 0.289 | +17 |
| **S14k** sched:40:kmx64+s14t64 (A) | 19 (3) | **1** (0) | 3 (1) | 0.303 | **+18** |
| S14b (A) | 20 (1) | 5 (3) | 5 (2) | 0.395 | +15 |
| pco16 (S7) | 23 (1) | 11 (5) | 12 (6) | 0.605 | +12 |
| u1rel (U1) | 21 (2) | 13 (9) | 9 (5) | 0.566 | +8 |
| u1endcar (U1) | 22 (4) | 15 (12) | 12 (7) | 0.645 | +7 |
| **knnxs8** (B, S16c) | 26 (4) | 15 (8) | 9 (6) | 0.658 | **+11** |
| knnx8 (S4) | 26 (0) | 21 (4) | 13 (2) | 0.789 | +5 |
| tok | 26 (0) | 21 (3) | 13 (0) | 0.789 | +5 |

Reading:
1. **The uncentred model state separates the polarities** (zero: think 11, dont_think 0), so the DM bank carries its own
   mention control: a pass on a dont_think item is the concept surfacing where the model was told not to hold it.
2. **knnxs8 keeps more of that contrast than knnx8 / tok** (+11 vs +5: dont_think 15 vs 21) and about as much as the
   fair position means (u1rel +8, u1endcar +7), which supports B's "fair form of knnx8". But 15 of its 26 dont_think
   items pass, against 0-2 for zero / fam, and **8 of those 15 pass only at the sentence-final cell** (u1endcar 12 of
   15): the end-of-copy position is where the centred readouts surface the *mentioned* concept. So the steward's
   suspicion is right in part: the sentence-final DM passes of the matched centres (knnxs8, u1rel, u1endcar, pco16) mix
   holding with prompt reading, and the think-only count is the cleaner DM score for them.
3. The S14 arms are the most polarity-selective centres (S14k: dont_think 1 / 26, think 19 / 26), consistent with their
   mention-control result (0.58 / 0.01); their DM totals are low because they surface little in dont_think / suppress.

A proposal for the DM headline (for the user): report think-twin pass and the think - dont_think contrast next to the
total, since the total rewards surfacing a concept the prompt forbids.

## The rms result (steward's second question; val strict, from the summaries)

| arm (rms) | macro11 | without UM / DM | UM | DM |
|---|---|---|---|---|
| fam | 0.610 | 0.648 | 0.787 | 0.095 |
| knnxs8 | 0.633 (+0.023) | 0.645 (-0.003) | 0.852 | 0.297 |
| knnx8 | 0.635 (+0.025) | 0.645 (-0.003) | 0.852 | 0.324 |
| S14k (A) | 0.630 (+0.020) | 0.663 (+0.015) | 0.803 | 0.162 |
| S14b (A) | 0.647 (+0.037) | 0.669 (+0.021) | 0.852 | 0.243 |

B's statement reproduces: under rms knnxs8's whole gain is UM and DM (without them -0.003), the two families where strict
cannot validate a centre (S11) and where, on DM, part of its passes are the mentioned concept (above). Under rms the S14
arms keep a gain on the other nine families (+0.015 / +0.021).

## Finalists table (steward's request; existing judge outputs only, no new spend; `experiments/dm_polarity.py`,
## `out/analysis/DM-polarity/val.md`)

DM val, Haiku at layers 24 / 36 / 48 / 60. Pass = gold picked and content-bound at any judged cell. In brackets: items
whose only passing cells are sentence-final. Last column: the share of all passing items that pass only at the
sentence-final cell. S21 has no judged DM run.

| arm | think (26) | dont_think (26) | suppress (24) | total | think - dont_think | sentence-final-only share |
|---|---|---|---|---|---|---|
| S14k sched:40:kmx64+s14t64 | 19 (3) | 1 (0) | 3 (1) | 0.303 | **+18** | 0.17 |
| s14t64 | 18 (2) | 1 (0) | 3 (2) | 0.289 | +17 | 0.18 |
| S14b (alpha 0.5) | 20 (1) | 5 (3) | 5 (2) | 0.395 | +15 | 0.20 |
| fam | 14 (0) | 2 (0) | 1 (0) | 0.224 | +12 | 0.00 |
| pco16 | 23 (1) | 11 (5) | 12 (6) | 0.605 | +12 | 0.26 |
| knnxs8 | 26 (4) | 15 (8) | 9 (6) | 0.658 | +11 | 0.36 |
| zero | 11 (0) | 0 (0) | 2 (0) | 0.171 | +11 | 0.00 |
| S20x (s20xt:1) | 11 (0) | 1 (0) | 1 (0) | 0.171 | +10 | 0.00 |
| u1rel | 21 (2) | 13 (9) | 9 (5) | 0.566 | +8 | 0.37 |
| kmx64 | 20 (1) | 13 (10) | 6 (5) | 0.513 | +7 | 0.41 |
| u1endcar | 22 (4) | 15 (12) | 12 (7) | 0.645 | +7 | 0.47 |
| knnx8 | 26 (0) | 21 (4) | 13 (2) | 0.789 | +5 | 0.10 |
| tok | 26 (0) | 21 (3) | 13 (0) | 0.789 | +5 | 0.05 |

The full table over every judged DM arm (including the gen / glos / dict arms) is in `out/analysis/DM-polarity/val.md`.
