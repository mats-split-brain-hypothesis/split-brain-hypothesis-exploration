# Cross-check of B's S21b (A, j-lens-mean-2e, night-2, 04:46 BST)

Claim (studies/S21.md, "S21b"): S20x's early correction on A's S14b reads val +0.058 (cos) / +0.057 (rms, rms-fitted
correction) vs fam, +0.015 over S14b, all of it multihop; random-direction control +0.004 over S14b. Supervised.

1. **Numbers reproduce** from `out/eval/<family>/val/summary.json`: S21b cos 0.656 (+0.058; without UM / DM +0.040), rms
   0.668 (+0.057 vs rms fam; +0.043), random-direction control 0.646 (+0.047). Battery vs S14b on multihop
   (`out/analysis/xcheck-S21b/`): +0.096 [+0.036, +0.169], won 8, lost 0; the random control won 0, lost 0.
2. **Are the multihop wins recurring answers?** The correction is learned from the *other* families' fit targets (twins
   out), and multihop's answers are often the kind of word other families have as targets (capitals, months, seasons,
   languages). Of the 83 multihop val items, 35 (42 %) have an accepted target that is also an accepted fit target of
   another non-twin family (multilingual 16, basic_readout 15, typo 7, ...). Of S21b's 8 wins, 4 (50 %) do
   ("september", "summer", "winter", "cow" as an accepted form); the other 4 are new answers ("Italian", "German",
   "solid", "0"). So the wins are not concentrated on recurring targets beyond their base rate: the gain looks like the
   answer-*class* prior S20 found (seasons, months, nationalities), carried across families, not recalled answers. With
   8 wins the test is weak (4 / 8 vs 0.42 expected).

Verdict: the headline stands, with B's own labels (supervised; val read once after fit). The recurring-target base
rate (42 % of multihop val items) is worth stating next to any multihop gain from a target-fitted correction.
