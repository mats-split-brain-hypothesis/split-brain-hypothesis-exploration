# Cross-check of C's S24 val2 read

By j-lens-mean-e1 (night-2 instance B), steward's card, 05:40 BST. Offline: C's stored val2 readouts only, no new read.

1. **Arms read = arms registered = arms B sent.** The registration (mu-log S24, commit 07d3fc8, 05:07:18 BST) lists 9 cos
   arms (zero, fam, S14k, S14b, S14b-knnxs8, S20x `s20xt:1`, S21b, `s14:template:64:mean=kmx64:a=0.5`,
   `s20xon:1:kmx64`) and 3 rms arms (fam, `s14:template:64:mean=kmx64:a=0.5`, `s20xonrms:1:kmx64`); `out/eval/{typo,
   association,multihop}/val2/` holds exactly these 12 arm directories in each family. B's two single centres were sent
   with exactly these specs (cos and rms).
2. **Read once, after the registration**: every val2 readouts file was written 05:32:36-05:33:07 BST, one read window, 25
   minutes after the registration commit.
3. **The numbers reproduce**: strict per family recomputed from the readouts (`jlm.score.strict_items`, scored ids from
   each summary), Δ vs fam and a paired item bootstrap within each family for the three-family macro (5000 draws, own
   seed):

| arm | typo Δ | assoc Δ | mhop Δ | macro Δ (B) [95 %] | C's value [95 %] |
|---|---|---|---|---|---|
| S20x | +0.000 | +0.056 | +0.093 | +0.050 [+0.021, +0.080] | +0.050 [+0.020, +0.082] |
| S21b | +0.012 | +0.034 | +0.101 | +0.049 [+0.014, +0.083] | +0.049 [+0.012, +0.086] |
| s20xon:1:kmx64 | +0.000 | +0.067 | +0.101 | +0.056 [+0.026, +0.089] | +0.056 [+0.024, +0.090] |
| s20xonrms:1:kmx64 (rms) | +0.023 | +0.079 | +0.101 | +0.068 [+0.037, +0.100] | +0.068 [+0.037, +0.101] |
| S14b-late single | +0.012 | +0.011 | +0.054 | +0.026 [-0.006, +0.057] | +0.026 [-0.006, +0.060] |
| S14b-late single (rms) | +0.023 | +0.045 | +0.062 | +0.043 [+0.017, +0.072] | +0.043 [+0.017, +0.072] |
| S14b | +0.012 | +0.022 | +0.054 | +0.029 [-0.001, +0.061] | +0.029 [-0.001, +0.061] |
| S14k | +0.012 | -0.056 | +0.054 | +0.003 [-0.028, +0.034] | +0.003 [-0.027, +0.035] |
| S14b-knnxs8 (A) | +0.012 | +0.067 | +0.078 | +0.052 [+0.024, +0.084] | +0.052 [+0.024, +0.083] |

Every Δ matches C's to the third decimal; the intervals differ by at most 0.003 (bootstrap draws). Item counts 86 / 89 /
129 as C reports. Nothing to correct.

Notes: the multihop gains are the same across the supervised arms (+0.093 to +0.101) and larger than the label-free
schedules' (+0.054), A's knnxs8 variant in between (+0.078); typo is near ceiling (fam 0.953). The _mt families, UM and
DM are not in val2, so the guardrail families of the night (multilingual_mt above all) are untested there.

## S24b (val2b: multihop country / calendar / element_material / number; multilingual) audit, 05:44 BST

On C's filtered items (`data/dev/val2b-authoring/filtered/*.jsonl`; `experiments/s24_audit.py --jsonl ... --split val2b` ->
`out/analysis/S24-audit/audit-val2b.md`), before the gate / freeze.

- **Prompts**: 0 exact, normalised or near-duplicate shared with bench / fit / val, except multilingual `v2-ml-v-042`
  "El color de la leche es" (target blanco), a near-copy of val's `dev-ml-b-023` "El color de la leche es el": drop.
- **Targets (final target and accepted forms)**: multilingual: only color items repeat a bank's answer (1 / 1 / 2 vs
  bench / fit / val), all marked fresh_target = false: consistent. **multihop: fresh_target is wrong on 15 / 30 / 21
  items vs bench / fit / val** (e.g. Asia, Spanish, French, Africa, euro, F, C); **element_material shares a final target
  with some bank on 17 of 30 items** (solid, gas, C, N, M, S, 3, 4, 6, red): closed answers repeat, so the steward's
  "element_material shares no target" does not hold. Advice sent: recompute fresh_target from an actual check, report
  shared and fresh items separately, headline on the fresh subset.
- **Format**: keys match val apart from readout / split / consistency (the freeze adds them); plain render, final-token
  plan (the last-word offset plan comes with the readout field); prompt lengths multihop 13 / 20 / 35 vs val 12 / 22 / 38,
  multilingual 5 / 8 / 12 vs 5 / 8 / 19; subfamily mix multihop country 45, calendar 25, element_material 30, number 15
  (val 25 / 15 / 15 / 4 of these), multilingual close to val's mix.

Frozen val2b check (05:51 BST; `data/dev/{multihop,multilingual}/val2b.json`, 94 / 75 items): the multilingual near-copy
is dropped; items with fresh_answer = true share no final answer with bench / fit / val (7 apparent clashes are
intermediates or English glosses: Mongolia behind Ulaanbaatar, Nigeria behind naira, red behind rot); fresh_target stays
true on 30 multihop items whose target-or-intermediate is shared, so the headline on fresh_answer is the right one.
Confirmed to C at 05:52.

## val3 (S24d) audit, filtered items (06:32 BST; `--jsonl data/dev/val3-authoring/filtered --split val3 --also val2,val2b`)

typo 120, association 193, multihop 133. Against bench / fit / val / val2b: 0 shared targets, 0 shared prompts, 0
near-duplicates; prompts unique within val3. Flags sent to C: (1) targets shared **within** val3, against the
shared_target rule: multihop first names Friedrich (a-011 / b-027), Robert (a-015 / b-048), Herbert (a-022 / b-010);
across families beach (typo a-046 / multihop b-064) and robin (typo a-107 / multihop a-032); (2) vs val2 by normalised
form: jaw (vs val2's film "Jaws", a different concept) and lungs (b-030), to check; (3) mix: association has no proper /
foreign items and multihop is person + object_animal only (as val2). Format matches val (the freeze adds readout / split /
consistency). The authors' overwritten helper scripts could not be audited; the packets and the filtered files could.

Frozen val3 (06:56 BST; files untracked in the main checkout at the time, audited from there): typo 120, association 81,
multihop 102, all from the audited filtered sets; 0 targets / prompts / near-duplicates shared with bench, fit, val, val2,
val2b; no target repeated within or across families; format matches val. Mix: association activity 21 / place_event 34 /
abstract 26 (no proper / foreign), multihop person 54 / object_animal 48. Confirmed to C.
Landed val3 (f0d7c33, rebuilt from the captures) is byte-identical to the files audited at 06:56; audit rerun from iteration clean. Confirmed to C at 06:56.

## Cross-check of S24d (val3) and the val2 + val3 pool (07:01 BST)

1. **Arms = registration.** The S24d card (mu-log, commit c47751c, 06:23:59 BST) registers zero, fam, S14bL, S14b-knnxs8,
   S20x `s20xt:1`, s20xon `s20xon:1:kmx64`, S21b and `rand.` of S14bL / S20x / s20xon; `out/eval/{typo,association,
   multihop}/val3/` holds exactly these 10 arm directories.
2. **One read after registration**: every val3 readouts file was written 06:56:40-06:57:53 BST. (The val3 bank was rebuilt
   from its captures at 06:56:08, f0d7c33, after the registration and before the read; A audited the frozen items.)
3. **Numbers reproduce** (B's code: strict per family from the readouts, items pooled within family, macro over the three,
   paired item bootstrap 4000 draws). Items: val3 120 / 81 / 102, val2 86 / 89 / 129 (607 pooled).

| arm | val3 Δ (typo / assoc / mhop) | val3 macro [95 %] | val2 + val3 Δ (typo / assoc / mhop) | **pooled macro [95 %]** |
|---|---|---|---|---|
| S20x | +0.017 / +0.074 / +0.059 | +0.050 [+0.024, +0.079] | +0.010 / +0.065 / +0.078 | **+0.051 [+0.030, +0.073]** |
| s20xon:1:kmx64 | +0.008 / +0.062 / +0.059 | +0.043 [+0.018, +0.070] | +0.005 / +0.065 / +0.082 | **+0.051 [+0.030, +0.072]** |
| S21b | +0.008 / +0.049 / +0.020 | +0.026 [+0.002, +0.051] | +0.010 / +0.041 / +0.065 | **+0.039 [+0.017, +0.061]** |
| S14bL (= S14b-x on both splits) | +0.008 / +0.049 / +0.010 | +0.023 [-0.004, +0.050] | +0.010 / +0.059 / +0.048 | **+0.039 [+0.018, +0.059]** |
| zero | -0.167 / -0.395 / -0.127 | -0.230 | -0.155 / -0.429 / -0.082 | -0.222 |

Pairwise, pooled: S20x - S14bL +0.012 [-0.009, +0.033]; s20xon - S14bL +0.012 [-0.007, +0.032]; S21b - S14bL -0.000
[-0.017, +0.016]: **not separated**, as C reports.

4. **A note on the `rand.` controls**: they score -0.239 to -0.262 on val3 (below zero), not "within +-0.015 of fam" as
   C's card predicted: the `rand.` wrapper replaces the whole g (fam or kmx64 included) by a random direction of g's norm,
   so it tests "a random vector of g's size", which reads like no centring or worse (baseline study). It is not a control
   for the supervised correction; that control is `s20xr` (fam + a random direction of dbar's norm: val +0.012), not
   read on val2 / val3.

Follow-up (C, S24.md): the matched null was run as a post-read control on val2 + val3: fam + a random direction with the
per-cell norm of each arm's change from fam (3 seeds) sits at fam's level (-0.002 / -0.004 / -0.012); arm minus null:
S20x +0.053, s20xon +0.055, S14bL +0.051. The pooled gains are not a norm effect.
