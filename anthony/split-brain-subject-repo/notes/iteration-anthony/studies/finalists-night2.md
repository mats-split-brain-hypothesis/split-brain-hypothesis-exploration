# Night-2 finalists, side by side (for the user)

Compiled by j-lens-mean-e1 (instance B) on the steward's card, 04:40 BST. **Numbers only from existing runs**; the study
files hold the details (S14.md and xcheck-S14k / xcheck-S14b for A's arms; S16.md, S20x.md, S21.md for B's; C's
fresh.md). Val split read with fit references. "Strict" = our strict score (the piece proxy on the _mt families).
"Haiku" = Haiku 5.5 via OpenRouter, an unpinned dev judge, never a WorkspaceBench score. "Guardrail" = no family's paired
95 % interval against fam lies entirely below 0 (`experiments/analyse.py`).

**Summary (for 10:00).**
1. **Label-free winner: S14bL / S14b-x** (A): cluster mean to L40, then template removal of h minus half the mean of its 8
   nearest other-carrier (and, S14bL, other-language) fit cells. Val +0.060 cos / +0.062 rms, guardrail ok; **fresh val2 +
   val3 pooled (607 items) +0.039 [+0.018, +0.059]**.
2. **Supervised (other families' labels; user to rule): S20x / S21b** (B): val +0.042 / +0.058; **pooled fresh +0.051
   [+0.030, +0.073] / +0.039 [+0.017, +0.061]**; S20x - S14bL +0.012 [-0.009, +0.033]: not separated from the label-free
   arm. A matched random-direction null (C, post-read) sits at fam's level: arm minus null +0.051 to +0.055.
   On val2b's closed-class answers the supervised gain is shared answers only.
3. **Did not replicate on val2: S14k** (+0.032 val, +0.003 val2). Every schedule is about its best single component (S23b).
4. **Judged _mt and DM:** the template centres keep the language unit; DM think-vs-don't contrast is best for S14k (+18) and
   S14b-x (+17); kNN-type centres lose multilingual_mt's language unit unless same-language neighbours are excluded (S14bL).
5. **Caveat:** val chose among many forms tonight; val2 (typo / association / multihop, English) is the honest test, and
   the _mt / UM / DM families have no fresh split yet.

## Main table

| centre | what g is | labels inside g | val strict cos (Δ fam) [fit-chosen form's val] | w/o UM, DM | val strict rms (Δ rms fam) | fresh answers, Δ fam cos / rms (C) | Haiku _mt mean (4 fam.) | DM Haiku | DM think / don't (contrast) | guardrail | vs union control (val cos: best single component / swapped order, Δ fam) | **val2** Δ fam (C, fresh, typo / assoc / mhop, cos) | **val2 + val3 pooled** Δ fam [95 %] (607 fresh items) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **fam** | family mean, own group out | family label | 0.599 | 0 | 0.610 | 0 / 0 | 0.416 | 0.224 | 14 / 2 (+12) | (ref) | - | 0 (0.807) | 0 |
| **s14t64** (A) | h's component along 64 template tokens' reading directions removed | none | 0.608 (+0.009) | +0.013 | 0.610 (-0.001) | -0.050 / -0.053 | **0.473** | 0.289 | 18 / 1 (+17) | association | single centre | not read | not read |
| **S14k** (A) | kmx64 cluster mean of fit cells up to L40, s14t64 above | none (fit cells) | 0.631 (+0.032) [near-ties, not read] | +0.031 | 0.630 (+0.020) | -0.022 / -0.012 | 0.461 | 0.303 | **19 / 1 (+18)** | ok | +0.032 (kmx64 alone) / +0.024 | +0.003 [-0.027, +0.035] | not read on val3 |
| **S14b** (A) | as S14k; above L40 the projection of h - 0.5 kmx64 | none (fit cells) | 0.642 (+0.043) [= fit pick] | +0.026 | 0.647 (+0.037) | +0.016 / +0.012 | 0.462 | **0.395** | 20 / 5 (+15) | ok | +0.036 (late form alone) / +0.029 | +0.029 [-0.001, +0.061] | not read on val3 |
| **S14b-x** (A) | S14b with the late partial mean from knnxs8 instead of kmx64 | none (fit cells) | 0.654 (+0.055) [= fit pick among late means, A] | +0.043 | 0.656 (+0.046) | n/a | 0.434 | 0.487 | 23 / 6 (+17) | ok (cos and rms; B reproduced) | not computed | **+0.052 [+0.024, +0.083]** | **+0.039 [+0.019, +0.059]** |
| **S14bL** (A) | S14b-x with the late neighbours of the cell's own (text-detected) non-English language excluded | none (fit cells; language from prompt text) | 0.659 (+0.060) [val-informed fix] | +0.049 | 0.672 (+0.062) | n/a | n/a (multilingual_mt 0.340 = fam) | 0.487 (= S14b-x: English) | 23 / 6 (+17) | ok (cos and rms; B reproduced) | not computed | **+0.052** (cos; rms +0.046; = S14b-x, A's registered read) | **+0.039 [+0.018, +0.059]** |
| **knnxs8** (B) | mean of the 8 nearest fit cells (any family), none sharing the cell's carrier | none (fit cells) | 0.639 (+0.041) [= fit pick] | +0.020 | 0.633 (+0.022) | +0.025 / +0.012 | not judged (knnx8 0.371) | 0.658 | 26 / 15 (+11) | multilingual_mt (cos and rms) | single centre | not read (S14b-knnxs8 schedule +0.052) | not read |
| **S20x** (B) | fam + mean of the other families' target-fitted corrections (S20), own family and _mt twin out | **yes** (other families' fit targets) | 0.640 (+0.042) [= fit pick] | +0.036 | 0.645 (+0.035)\* | **+0.053 / +0.050** | **0.487** | 0.171 | 11 / 1 (+10) | multilingual_mt (strict; judged it gains) | single centre | **+0.050 [+0.020, +0.082]** | **+0.051 [+0.030, +0.073]** |
| **S21** (B) | S14k + S20x's correction up to L40 | **yes** | 0.645 (+0.047) [fit pick: every layer, +0.045] | **+0.048** | 0.653 (+0.042)\* | +0.016 / +0.009 | 0.449 | 0.276 | 16 / 2 (+14) | ok (cos and rms) | (not run)  | not read | not read |
| **S21b** (B) | S14b + S20x's correction up to L40 | **yes** | **0.656 (+0.058)** [= fit pick; seeds +0.059, +0.065] | +0.040 | **0.668 (+0.057)**\* | not computed | 0.424 | 0.382 | 18 / 6 (+12) | ok (cos and rms) | +0.054 (kmx64 + correction alone) / +0.038 | **+0.049 [+0.012, +0.086]** | **+0.039 [+0.017, +0.061]** |

\* rms rows use corrections refitted through the rms map (C's rms constants); the cos-fitted correction read through
rms gives S20x +0.016 and S21 +0.006. "Fresh answers" (C, studies/fresh.md): the 5 single-token families, items whose
accepted answers occur in no other family's fit targets (321 of 393).

DM polarity (A, studies/xcheck-S16.md): Haiku val passes on "think about X" vs "don't think about X" items (26 each).
A centre that reads what the model holds should pass the first and not the second, so the contrast is a fairer DM number
than the total. References: zero 11 / 0 (+11), u1rel 21 / 13 (+8), u1endcar 22 / 15 (+7), kmx64 20 / 13 (+7), pco16
23 / 11 (+12), knnx8 and tok 26 / 21 (+5).

## Val-selection audit (steward's card, 04:40 BST; offline, from existing runs)

For each finalist: how its form was chosen, the variant **fit alone** would pick from the same candidate set, that
variant's val number next to the headline, and how many candidate forms of the study were read on val (cos, all 11
families; controls and robustness reads such as rms or source subsets not counted). Fit macro is vs fam@self, val vs
fam@fit.

| finalist | candidate set screened on fit | fit picks | fit / val of the fit pick | headline val | candidate forms read on val | verdict |
|---|---|---|---|---|---|---|
| s14t64 (A) | s14t16 / 64 / 128 and token sets | (A's S14 screens) | | +0.009 | several (S14) | single-arm; not audited further |
| S14k (A) | label-free "X early, s14t64 late" schedules, X in kmx64 / kmx128 / knnx8 / pco16, L 40 / 48 | `sched:48:knnx8+s14t64` (+0.026) if knnx8 is allowed; `sched:40:kmx128+s14t64` (+0.023) or `sched:48:kmx64+s14t64` (+0.022) among cluster means | not read on val | +0.032 (fit +0.020) | 4 (kmx64, fam, pco16 versions; s14t64) | fit picks are within 0.006 of the headline on fit (noise); the kmx64 L40 form was chosen by A's rule "label-free, early centre barely matters" (insight 12), not on val |
| S14b (A) | alpha 0 / 0.25 / 0.5 / 0.75 / 1 on the kmx64 late mean | alpha 0.5 (+0.032) | +0.032 / **+0.043** | +0.043 | 2 (alpha 0.5, kmxr64 control) | **fit-consistent** |
| (S14b's late mean) | kmx64 / knnxs8 / s22nn / fam at alpha 0.5 | knnxs8 (+0.037) | +0.037 / +0.055 | | | the knnxs8 swap is the fit pick (A screened it after B's val read): the val-first sighting is now fit-confirmed |
| knnxs8 (B) | k = 8 inherited from S4 (fit); one form | k = 8 | | +0.041 | 1 (+ shuf control) | fit-consistent (no choice made on val) |
| S20x (B) | alpha 0.5 / 1 / 2 / 3 (with twin, and twin-out 0.5 / 1 / 2) | alpha 1 (+0.043; twin-out +0.041) | +0.043 / +0.044; twin-out +0.041 / **+0.042** | +0.042 | 2 (with / without twin) | **fit-consistent**; twin-out is a fairness rule, not a val choice |
| S21 (B) | correction every layer / early only / late only | **every layer** (+0.040; early only +0.038) | +0.040 / **+0.045** (w/o UM, DM +0.037) | +0.047 (early only) | 3 + random control | **val-informed**: the early-only headline was picked over the fit pick for its _mt units (language unit kept, a val reason); fit-only headline: +0.045 |
| S21b (B) | one form (designed from S21's val deep dive) | that form (+0.056) | +0.056 / **+0.058** | +0.058 | 1 + random control | fit-consistent as a screen, but the *idea* came from a val deep dive (S21 insight 5) |

**Summary.** Re-picking every finalist on fit alone changes one headline (S21: +0.047 -> +0.045, w/o UM / DM +0.048 ->
+0.037) and confirms the others (S14b, S20x, S21b, knnxs8), with S14k's choice among near-ties made by a stated rule.
The val reads tonight: S14 about 17 cos arms, S20x 2 forms (+ 4 robustness), S21 3 forms, S21b 1, knnxs8 1. So the
val split has been looked at many times for the S14 schedules and the S20x / S21 family; differences under about 0.01
between their variants are not evidence, and the fresh dev split remains the honest test.

## Fresh held-out read (C's val2, S24; read once after this table's choices)

Typo, association and multihop only (86 / 89 / 129 items authored after tonight's choices, no target in any earlier
bank); Δ vs fam, strict cos, macro over the three (studies/S24.md): **S20x +0.050 [+0.020, +0.082], S21b +0.049
[+0.012, +0.086], s20xon:1:kmx64 +0.056 [+0.024, +0.090]** (rms +0.068), **A's S14b-knnxs8 +0.052 [+0.024, +0.083]**
(label-free), S14b +0.029 (borderline), the one-centre S14b form +0.026 (rms +0.043), **S14k +0.003 (does not
replicate)**. The _mt families, UM and DM are not in val2.

B's cross-check of S14b-x (studies/xcheck-S14bx.md): every number above reproduces; its late neighbours are 78-100 %
same family and, on the _mt banks, 58-83 % same prompt language, which is where its judged multilingual_mt cost
(-0.094 [-0.189, 0.000]) comes from; mention control 0.76 / 0.14 with a carrier-sharing pool. A's follow-up S14bL (late neighbours of other prompt languages
only) removes that cost: val +0.060 cos / +0.062 rms, guardrail ok, judged multilingual_mt 0.340 = fam (val-informed;
not on a fresh split).

## Caveats per centre

- **s14t64**: no reference cells at all (the most data-free); loses association (-0.13: it leaves the family's rewrite
  frame on top) and is below fam on fresh answers; best judged _mt profile (language unit kept).
- **S14k**: label-free, but needs bench fit cells (chat-corpus clusters instead: +0.017); seed-stable (+0.029 to +0.036);
  best DM contrast (+18); below fam on fresh answers (its gain tilts to common-word answers).
- **S14b**: label-free, needs bench fit cells (chat pool: +0.005); seed-stable; its DM gain survives the judge and is not
  same-carrier leak; a swap of its late mean to knnxs8 read +0.055 but is val-selected and unconfirmed.
- **knnxs8**: fair on the mention control with a carrier-sharing pool; its DM total includes the end-of-copy cell
  surfacing the forbidden concept (8 of 15 don't-think passes); fails the multilingual_mt guardrail (language unit);
  outside UM / DM its gain is cos-only.
- **S20x / S21 / S21b**: **supervised** (other families' fit targets inside g): the night-2 rules leave it to the user
  whether this is a method. S20x keeps ~80 % of its gain on fresh answers; S21's fresh gain is +0.016; S20x's DM strict
  gain is not confirmed by the judge. S21b is val-read once after fit selection. Under Haiku the correction adds nothing on
  top of its base: S21 vs S14k _mt 0.449 vs 0.461, DM 0.276 vs 0.303 (contrast +14 vs +18); S21b vs S14b _mt 0.424 vs
  0.462, DM 0.382 vs 0.395 (+12 vs +15). Its gain is on the strict single-token families (multihop, typo).

## How to read it

Without labels, A's S14b (+0.043 cos / +0.037 rms, guardrail ok) and S14k (+0.032 / +0.020, the best DM contrast and _mt
profile) are the night's finalists; both need bench fit cells. knnxs8 is the fair form of knnx8 but fails the
multilingual_mt guardrail. With other families' labels allowed, S21b is the best strict macro under both readouts
(+0.058 / +0.057, guardrail ok) and S20x the best on fresh answers and on the judged _mt mean. **Union controls (S23b, `studies/S23.md`)**: each schedule finalist is within about 0.01 of its best single
component used at every layer (val, Δ fam, cos / rms): S14k vs kmx64 alone +0.032 vs +0.032 / +0.020 vs +0.023; S14b vs its
late form alone +0.043 vs +0.036 / +0.037 vs +0.041; S21b vs kmx64 + correction alone +0.058 vs +0.054 / +0.057 vs +0.049.
The same two centres in the swapped order are below the best component (no free union gain); S23's union effect comes
from many-centre random mixtures. So the schedules' gains are their components' gains; the single centres
`s14:template:64:mean=kmx64:a=0.5` (label-free) and `s20xon:1:kmx64` (supervised) are simpler leads (fit-screened since: +0.025 / +0.054 cos; sent to C's registered val2 read). The
supervised single centre fails the multilingual_mt guardrail on val (cos -0.13): S21b's late template part adds little
score but keeps the guardrail. **Every number here is on
val, which tonight's studies also used to choose among forms**: a fresh dev split is the honest confirmation of any of them.
