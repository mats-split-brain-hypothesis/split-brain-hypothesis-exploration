# Constant-mu exploration: screen and status (moved from notes/eval-pipeline.md, 2026-10-11)

The study x1-x25 (registrations and outcomes: `notes/predictions.md`; reading of x1-x12: `notes/abstract-mu.md`).
The status sections below the conclusions were kept in the shared pipeline notes until the study moved to this branch.

## Conclusions (x1-x25; section closed 2026-10-12)

Question: which **constant** μ_l (one vector per layer, the same for every input of a task) to use in
J_l(h_l − μ_l), and what it needs. Scores: the bench's strict rule, rms readout, dev val, pooled over the five
plain families (n = 393), paired against the plain J-lens (0.593). Bench: pinned judge, cos, n = 100 per family.

| μ | needs | gain, val |
|---|---|---|
| family mean (`fam@fit`) | the task's own read cells | +0.216 |
| glossary word (`glos:word`, x11; words picked after x1-x10) | one word per task | +0.196 |
| blind glossary (`glosb`, x13; the model wrote it from one README sentence) | one README sentence | +0.165 (desc +0.198) |
| one μ for every family (`glosall:word`, x14 A) | nothing per task | +0.170 |
| **no entry: 64 "varied short texts" the model writes (`glos:none`, x14 B)** | **nothing** | **+0.176** |
| the same, model-written in an encyclopedia's style (x24) | nothing | +0.117 |
| short wikitext sentences (x24) | nothing | +0.046 |
| the no-entry texts read one word before their end (x24) | nothing | +0.010 |
| corpus mean, minimal prompts, unconditional samples, top PCs or massive dimensions removed, the lens's own fit data (x1, x14, x20) | nothing | −0.04 to +0.06 |
| per-input situation word (x23 / x23b) | one generation per input | +0.115 / +0.130 |
| per-input topic word (x23) | one generation per input | −0.109 |
| J++ (another map, no centre) | — | +0.216 |
| J++ + glossary word / + family mean (x25) | as above | +0.237 / +0.247 |

1. **A data-free constant gets about 80 % of the family mean's gain**: the mean final-token state of short texts
   the model writes itself. Naming the task adds little: no entry minus glossary word −0.020 [−0.046, +0.005].
   Typo is the one family where naming may matter (strict + forms, fit: −0.098 [−0.174, −0.033]). One μ shared by
   every family works as well (+0.170).
2. **What makes those texts work (x24), per family (val):** they are read at the sentence-final token; read one word
   earlier they lose most of it on association (−0.37 [−0.47, −0.27]), typo (−0.19) and multihop (−0.12).
   Model-written vs wikitext then matters in different ways: on **typo** it is the source (model vs wikitext in the
   same encyclopedic style +0.19 [+0.10, +0.27]; generic vs encyclopedic from the model +0.04, n.s.), on
   **association** the style (+0.20 [+0.11, +0.28]; source +0.05, n.s.; +0.13 on fit). basic_readout and
   multilingual are near their ceilings and move by 0.06 or less; length adds 0.06 at most (association,
   multihop). Means of mid-text states are null or harmful although the bank prompts are themselves read mid
   sentence. Why the sentence end matters is untested (a hypothesis is in x24's reading).
3. **A per-input μ does worse than a constant.** Naming each input's situation gives +0.115 (+0.130 with rules),
   naming its topic −0.109, and the input's own prefix mean −0.08 to −0.28 (x23 A). The 8 nearest inputs by prefix
   help only when the read family's own items are in the pool (+0.181; other families only +0.028).
4. **Statistical constants are null**, including the mean over the lens's own fitting cells (x20; with x21 this
   closes the average-derivative route at the read layers).
5. **On the bench's own judge** the glossary word keeps 54 % of the family mean's gain pooled: typo +0.18,
   association +0.20, multihop −0.08 (x19). On directed_modulation it adds +0.07 [+0.02, +0.13] (x19 P5).
6. **J++ already gets the plain gain** (typo +0.36, association +0.40, UM +0.21 over the plain lens, val). A
   constant on top helps only association (+0.11 to +0.14), costs basic_readout about 0.06 (n = 35, n.s.), and
   moves the others by 0.05 or less (x25). On the bench J++ with the glossary word is the best data-free arm (0.854
   pooled; x19b). The task's own mean on J++ does the same: association +0.14, nothing else above 0.03.

**Use**: for a constant μ with no task data, the mean final-token state of about 64 short texts the model writes
from "Write varied short texts." If a different map is allowed, J++ with that centre (or the glossary word).

**Open, and caveats**: why the sentence-end read matters (above); x17's token-matched synthetic mean on DM is
untested for fairness (x16 deferred); most numbers are dev banks under the strict scorer, and the bench judged
only `glos:word`, `fam@fit`, `fam@plainothers`, `jpp:zero` and `jpp:glos:word` (and DM zero / `glos:word`), not
the no-entry μ; one model (Qwen3.6-27B) and one lens. The glossary words were chosen after x1-x10, which x13's blind
glossary controls for. Withdrawn or dropped: x18, x22. Judge spend recorded: x19 ~$42 (DM bench ~$26 of it), x19b $3.20, x7
$3.83; the OpenRouter key shows $54.62 used in total.

## Status bullets (x1-x3)

- x1-mu-pos-concept (2026-10-10, registered in `notes/predictions.md`, run entirely on the shared
  3x A100 box — no pod): positional corpus mean `pos@corpus`, corpus/token/sentence-end means and
  the abstract-word centres `cpt[c]:<word>:<alpha>` (`src/jlm/centres.py`), references from
  `experiments/capture_mu_refs.py`. On typo val: every corpus/positional rung flat-to-negative;
  abstract-word mu concept-specific under cos (+0.194 over the giraffe control, outside the
  bootstrap; zero 0.69 -> 0.80 at alpha 0.5) but ~0.12-0.14 short of fam@fit; under rms mostly the
  generic norm effect. Capture parity with the pod pipeline is exact. See `notes/abstract-mu.md`.
- x2-dict-mu (2026-10-10, registered): per-sample abstract-word mu from a global dictionary
  (`data/abstract_concepts.json`), words judged per item by the pinned 27B itself
  (`experiments/label_concepts.py`), on the six x89 confirmatory families' bench banks (captured
  locally). POOLED NULL: judged words = derangement control under cos; the x1 typo gain is
  family-specific. Keeper: frame words help, content hypernyms hurt (user_modeling attr words
  0.47 -> 0.19). `out/eval/x2-pooled.md`, outcome in `notes/predictions.md`, reading in
  `notes/abstract-mu.md`.
  (x2 note: its association/basic_readout/multihop ns — 78/67/91 — predate the merged
  scored-subset rule below; the registered x2 scorer is the one its outcome quotes.)
- x3-dict-mu-heldout (2026-10-10, registered): the x2 arms re-run properly held out on the six
  families' dev val splits (new dev banks captured locally; val labels judged by the pinned 27B).
  The pooled null replicates (judged words - derangement = +0.007 cos); the typo frame-word effect
  survives held out but smaller (+0.086, outside the bootstrap); user_modeling attr-word subtraction
  is confirmed destructive (-0.393 vs zero). Pooled cos: zero 0.689, best category mean 0.698,
  fam@fit 0.804. `out/eval/x3-pooled.md`; outcome in `notes/predictions.md`.

## Screen of our own centres (2026-10-10, merged code at 410ec58 + local; strict, rms)

Run under the screening policy above: every centre from x1-x8 (`notes/predictions.md`), strict on
all 7 families x fit and val, written to `out/screen/` from fresh reads on the merged code.
Tables: `python experiments/report.py --split val|fit --out out/screen`.

**Reproduction.** `experiments/repro_check.py` compares `out/screen` with the stored x-runs in
`out/eval`: 43 (bank, arm) pairs identical in every cell's top-10, 0 differ. 18 differ on
purpose: `fitall`, `fitothers` and `fitall`-based arms now pool 7 dev families (the DM bank came
with the merge). `plainothers` now picks plain-render families from the read plan, so the chat-
rendered DM bank stays out, as x6 defined it.

**Gotcha.** `evaluate.py` rewrites a bank's `summary.json` with only the arms of that call. Rerun
with the full arm list (stored readouts are reused, nothing is re-read) before `report.py`.

**Pooled over the 5 strict-proxy families** (paired vs `zero|rms` = 0.593 val / 0.554 fit):

| centre | needs | val | fit |
|---|---|---|---|
| `fam@fit`, `tok@fit` | family data | +0.216 / +0.216 | +0.232 / +0.244 |
| `fam@plainothers` | other tasks' plain-prompt bank | +0.112 [+0.079, +0.148] | +0.106 |
| `dict:fam2+:0.25@fitall` | all-family bank + test name | +0.076 | +0.088 |
| `fam@fitall` / `fam@fitothers` | all / other families' bank | +0.056 / +0.043 | +0.076 / +0.065 |
| `dict:{fam,strat,derang}:0.5@fit` | a category word | +0.02..+0.03 | +0.04 |
| wikitext corpus / position / sentence-end | nothing | -0.04..+0.02 | 0.00..+0.03 |

Per family (val): `tok@fit` = `fam@fit` on typo and association, beats it on multihop (0.60 vs
0.57; fit 0.66 vs 0.58), user_modeling (0.87 vs 0.79) and DM (0.32 vs 0.09, strict). The corpus
token mean `tok@corpus8` and `fam@sents` lift association 0.25 -> 0.43 with no task data (x1 only
tested them on typo). `plainothers` hurts user_modeling (0.62 -> 0.56; render mismatch) where
`fitall` helps (0.72). `dict:strat` damages user_modeling (0.44), as in x3.

**Synthetic references (x8-x10, val, rms).** The model writes same-kind prompts from example
prompts (`experiments/x8_gen_refs.py`); the centre averages their states at the matched cell.
Built from the item's OWN prompt (`gen`) it leaks the item's latent and hurts (typo 0.41). Built
from OTHER items' prompts it works: `genk:8` (8 example prompts x 8 written analogues) gives
association 0.765 = `fam@fit` 0.765 (zero 0.255) and basic_readout 1.000 = fam; typo plateaus at
about 0.70 (fam 0.90). So a synthetic family mean from a handful of examples of the read situation
substitutes for real family data on 2 of 3 families tested. multihop / multilingual and the fit
splits are being generated; UM and DM read inside chat templates and need a different generator.

