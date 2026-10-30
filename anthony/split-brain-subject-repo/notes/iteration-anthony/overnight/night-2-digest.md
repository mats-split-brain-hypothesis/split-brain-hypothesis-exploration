# night-2 digest (2026-10-12)

Final, 09:01 BST. All three instances reported done (A, B, C by 09:01); LL done at 07:31. No pods running.

Steward j-lens-mean-19. Instances: A = j-lens-mean-2e (S13-S15: priors and template subspaces), B = j-lens-mean-e1
(S16-S18: neighbours, depth, outliers), C = j-lens-mean-19c (session j-lens-mean-19 [21b77e]; the board name has a "c"
because our names clashed; S19-S20: learned centres and ceilings). LL ran independently as j-lens-mean-a3.

## The night in five lines

1. **A label-free centre beats fam on fresh data.** `S14bL`: the k-means cluster mean of fit cells up to L40, then the
   template-subspace projection of h minus half the mean of h's 8 nearest fit cells. Those neighbours exclude the
   item's own carrier and its prompt language, which is detected from the prompt text. Over **607 freshly authored
   items** (val2 + val3, S24/S24d) it gains **+0.039 [+0.018, +0.059]** strict over fam, and **+0.051 [+0.032, +0.070]**
   over its matched random null. On val: +0.060 cos / +0.062 rms, guardrail ok, judged multilingual_mt = fam, DM
   judged 0.487 with a fair think/don't-think contrast (+17).
2. **The supervised transfer centre is no better on fresh data.** `S20x` (fam + the mean of the other families'
   target-fitted corrections) gets +0.051 [+0.030, +0.073] pooled. Its margin over S14bL is +0.012 [-0.009, +0.033],
   not separated. Whether supervised transfer counts as a centre at all is a decision for you (below).
3. **Most of tonight's gain is re-ranking, and part of it is the scorer's preference for English.** Of the val2 flips,
   64-76 % had the target already at fam's ranks 11-50, often with its Chinese form above it. 19-32 % were absent from
   fam's top 50 (random directions of the same norm: 0 %), so there is a real "reads more" share (S24c). S20x's
   correction mostly changes word form (punctuation down, capitalised names up, CJK down), not the concept.
4. **Fresh data was the night's best tool.** val was also used to choose among forms (about 17 arms in S14 alone). C
   authored three fresh splits (S24 / S24b / S24d), gated through the 27B, audited by A before each one-time read, and
   cross-checked by B. S14k, a val finalist, did not replicate on val2 (+0.003).
5. **Headroom (C, S20 / S24):** a constant g fitted with targets gains +0.10 over fam on val for the single-token
   families and +0.09 judged on DM. Under the judge it has no headroom on the _mt families. On the 607 fresh items the
   ceiling is +0.073 over fam. S14bL reaches **53 % [28, 80]** of it and S20x 70 % [45, 102]. Association's headroom is
   used up (91-100 % for every arm). What remains is multihop (S14bL 35 %, S20x 58 %); typo has almost no headroom.

## Per instance

### A (j-lens-mean-2e): priors and template subspaces
| study | verdict |
|---|---|
| [S13](../studies/S13.md) | negative: unigram priors read below zero, head-only = zero, the next-token prior removes multihop_mt's bridge. |
| [S15](../studies/S15.md) | diagnostic: J does not attenuate fam; fam is spread through J's mid-spectrum (corrected for the massive coordinates after B's S18). Centres negative. |
| [S14](../studies/S14.md) | **the night's label-free line.** `s14t64` (remove h's component in the reading directions of 64 template tokens; no reference cells) keeps multilingual_mt's language unit (judged 0.92 vs fam 0.79) and lifts its concept. Schedules: S14k (kmx64 up to L40, template above; val +0.032) did not replicate on val2 (+0.003). S14b (the late step on h - 0.5 kmx64; val +0.043; bench strict +0.022, registered, one read) gives val2 +0.029 [-0.001, +0.061]. **S14bL** (late step on h - 0.5 knnxs8, same-language neighbours dropped): val +0.060 cos / +0.062 rms, judged multilingual_mt = fam, DM 0.487 (think/don't +17), mention control fair; **val2+val3 +0.039 [+0.018, +0.059]**. n-scaling: 25 % of the fit pool (~16 items per family) holds. |
| [S22](../studies/S22.md) | negative: item-free neutral fills recover association's late prior but lose macro to S14k. |
| S14f (in S14.md) | no token list isolates the "answer frame"; it is local to item types, which is why kNN beats the cluster mean late. |
| cross-checks | [xcheck-S16](../studies/xcheck-S16.md) (the DM polarity split: knnxs8's DM total includes surfacing the forbidden concept), [xcheck-S21](../studies/xcheck-S21.md), [xcheck-S21b](../studies/xcheck-S21b.md), [xcheck-S24c](../studies/xcheck-S24c.md); pre-read audits of every fresh split ([xcheck-S24](../studies/xcheck-S24.md)). |
| round 3 | four proposed cards in mu-log ("Round 3 cards", R3a-R3d). |

### B (j-lens-mean-e1): neighbours, depth, outliers
| study | verdict |
|---|---|
| [S16](../studies/S16.md) | **knnxs8** (knnx8 without same-carrier neighbours) is the fair knnx8: val +0.041, DM Haiku 0.658, fair on the mention control with a carrier-sharing pool (knnx8 leaks once it can: 0.12 -> 0.33). Caveats: its DM total includes surfacing the forbidden concept (A's polarity split), its gain without UM/DM is cos-only, and it fails the multilingual_mt guardrail. |
| [S17](../studies/S17.md) | centring matters at L >= 40. Negative as a method, but it located where centring acts. |
| [S18](../studies/S18.md) | fam's 8 outlier coordinates hold 60-90 % of its norm and none of its gain. No corpus mean replaces fam (a chat-format corpus reaches a quarter). |
| [S20x](../studies/S20x.md) | **supervised transfer**: fam plus the mean of the other families' S20 corrections. Val +0.042, val2 +0.050, val2+val3 +0.051; needs 4-6 source families. Mechanism: it changes the readout's word form (punctuation down, names up, English over CJK), not the concept. Label-free statements of it fail (S20z, S20w, S25). |
| [S21](../studies/S21.md) | S21b (S14b + S20x's early correction): val +0.058, val2 +0.049, pooled +0.039; under the judge it adds nothing to S14b on _mt / DM. |
| [S23](../studies/S23.md) | per-layer selection buys little over one switch (+0.010 val), and random per-layer maps come close: the any-layer item rule rewards mixing. S23b: the finalists sit within ~0.01 of their best single component, so the union effect does not inflate them. |
| tables | [finalists-night2.md](../studies/finalists-night2.md) (**the main table**: val / rms / judged / DM polarity / val2 / pooled / labels / caveats / val-selection audit), [mt-units-round2.md](../studies/mt-units-round2.md) (per-unit _mt). |
| cross-checks | [xcheck-S14k](../studies/xcheck-S14k.md), [xcheck-S14b](../studies/xcheck-S14b.md) (the bench-free pool fails: +0.005), [xcheck-S14bx](../studies/xcheck-S14bx.md) (the late neighbours are 78-100 % same family and 58-83 % same language: the multilingual cost's mechanism, which S14bL then fixed), S24 / S24d reads reproduced. |

### C (j-lens-mean-19c): learned centres, ceilings, fresh data
| study | verdict |
|---|---|
| [S19](../studies/S19.md) | negative: removal-only learned g has a degenerate optimum (it crowds the top 10). |
| [S20](../studies/S20.md) | headroom: the const ceiling is +0.096 over fam on val strict (single-token families) and +0.09 judged on DM; target-fitted classes give no _mt headroom under the judge, and on DM they fall below the fair position means. S20b null, S20u -0.02, S20r null. Cross-check of S20x: part of its transfer is answers shared across families; on fresh-answer items S21 is +0.015. |
| [S24](../studies/S24.md) | **fresh dev splits.** val2 (typo / association / multihop, 304 items) and val3 (303), authored by subagents from jle's briefs with avoid lists, gated through the 27B, audited by A, read once each against committed predictions, and reproduced by B. val2b (closed-answer subfamilies, multilingual) cannot separate the arms (at ceiling, or shared answers). S24c: the share of gains that "reads more" (target absent from fam's top 50) is 19-32 %, against 0 % for random directions of the same norm. Matched null: fam plus a random direction of each arm's norm stays at fam. |

### LL (j-lens-mean-a3, own pot)
Done. Provisional headline: J++-style weights over our plain wikitext experts, fitted on fit, give val 0.602 against
0.519 and bench 0.532 against 0.445 (J++ 0.519), with no family harmed. The k=1 gate fails at L24-48 (pooled J vs
n1000 cos 0.85-0.98, unexplained). Next: resolve the gate; experts on our own corpus. `local-linearisation/log.md`;
**LL pot $50.63 of $100**, all pods terminated.

## Spend

**Studies pot: $30.59 of $50.** Judge $15.12 (A $5.21, B $4.09, C $5.82). That matches OpenRouter's usage_daily of
$15.16; LL logged no judge spend, and the key has [amount] left. Pods $15.47:

| pod | $ |
|---|---|
| shared eval L40S, 01:53-08:17 | 6.99 |
| four stuck A100-PCIe pods (machine g95, never started) | 2.21 |
| round-2 precompute, H100, 21 min | 2.58 |
| fresh-split captures: S24 / S24b / S24d, H100 | 1.70 / 0.52 / 1.47 |

**LL pot: $50.63 of $100** (pods only; LL ran one small bench job on the shared eval pod at no cost to its pot).
All pods are terminated (`runpodctl pod list`: none running). Results are synced to the Mac: `out/eval`, `out/analysis`,
and the val2 / val2b / val3 captures. Not synced: `out/priors/pullback/nt-*` (2.4 GB) and `out/ctx/corpus-chat.pt`
(10 GB) stay on the volume.

## What broke, and the fix

1. **RunPod machine [host] (A100 PCIe, US-MO-1) never started a pod**: `uptimeSeconds 0`, no IP, for 25+ minutes,
   for mine (twice) and LL's. It cost $2.21 and 40 minutes. I wrongly terminated the first pair after 11 minutes, so
   let a pod boot for 15 minutes before calling it stuck. Fixes: LL's `GPU_IDS` override in `pod.sh` (4b7e295)
   [pipeline candidate]. Also order `GPU=eval` 48 GB cards before the A100 PCIe, and have `ssh-config` report
   `uptimeSeconds` and stop waiting on a stuck machine.
2. **No 48 GB GPU was free for a second eval pod** ("no instances currently available", twice), so one L40S (46 GB)
   served all three instances.
3. **Six jobs OOMed the 46 GB pod at load**: podrun's free-memory gate let them all pass at once. Fixed in 387da0f
   [pipeline candidate]: jobs pass the gate one at a time, each with 120 s to allocate (tested on the pod).
4. **Two evaluate.py crashes**, both fixed by the instances: 755ce1e (a local `forms` shadowed `jlm.forms`: every run
   crashed) and 956acdf (KeyError `diffs_forms` on every _mt re-run). Both bugs are also on `eval-pipeline`.
5. **Priors were missing on the volume**: I pushed them, and A pushed the Mac's 6 GB of lens caches, so the round-2
   precompute skipped them. The precompute script's final `ls | head` exits 141 under pipefail, which is harmless.
6. **I terminated cap24d before C had copied val3.json off the pod's own disk.** C rebuilt it exactly from the
   captures (they carry item ids); only the per-item gate rates are lost. Rule: capture jobs write banks and gate
   outputs to `/workspace`, and the steward terminates only once the owner confirms the files are home.
7. **The steward's open list was stale**: S2's neutral fills were already done in pilot-1. Fix the template.
8. **Name clash**: instance C's session was also called j-lens-mean-19, so it used `j-lens-mean-19c` on the board.
   Steward and instance names should be assigned so they cannot collide.
9. New pipeline candidate from C: dc860e5 (`banks`: held-out splits such as val2 are read by name, outside SPLITS,
   with a test).

## Decisions for the user

1. **Supervised transfer (S20x, S21b, s20xon).** Their g contains other families' fit targets, which the night's
   "no targets inside g" rule allows only for `ceil.` arms. They are labelled supervised everywhere, with prefixes kept.
   On fresh data they are no better than label-free S14bL (+0.012 [-0.009, +0.033]). Do they count as centres?
2. **Second bench read.** S14k / S14b were read on the bench once (strict, registered at ecc253a): S14b +0.022 and
   S14k +0.020 vs fam; S14k fails the association guardrail. S14bL's registration is written and not run
   (`S14.md`, "s14bL-bench"). Run it, and the judged halves (~$4 each)?
3. **DM scoring.** A proposes reporting DM's think-twin pass and the think - dont_think contrast next to the total.
   knnxs8 / u1endcar totals include surfacing the forbidden concept at the end of the copy.
4. **The English-surface-form share.** Part of every centre's gain is the scorer accepting the English form of a
   concept fam already held in Chinese (S20x mechanism, S24c). Should the strict scorer accept cross-script forms?
   That would also make it closer to the judge.
5. **Fresh splits as a standing practice.** val2 + val3 (607 items, $3.17 of capture pods; authoring by subagents) changed the ranking
   (S14k fell out, the val-selected S14b-x / S14bL held). Make "fit chooses, val screens, a fresh split confirms" the
   rule, with one fresh split per round?
6. **Dashboard.** The paste-ready `catalog.py` block is `studies/e1-catalog-lines.md`, with suggested `DEFAULT_CENTRES`
   = zero, fam, S14bL, s20xt:1. It was not applied, because your checkout has uncommitted edits to `catalog.py`.
7. **eval-pipeline.** Cherry-pick 755ce1e, 956acdf, 387da0f, 4b7e295 and dc860e5?
8. **HF data.** Push `out/priors` and the val2 / val3 banks and captures (`tools/hfdata.py push priors lens captures`)?

## What is next

- Round-3 cards proposed in mu-log (A): R3a DM with a position-matched late kNN, judged by the polarity split; R3b a
  label-free answer-class prior (fit cells grouped by the model's own next token), the only lead toward S20x's early
  multihop gain without labels; R3c per-cell answer-frame directions; R3d a fresh multi-token split for the _mt families.
- The headroom that remains is multihop: S14bL reaches 35 % of the ceiling there, S20x 58 %.
- LL: resolve the k=1 gate; experts fitted on our own corpus.
