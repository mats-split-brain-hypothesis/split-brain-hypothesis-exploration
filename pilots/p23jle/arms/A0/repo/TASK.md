# Task `jlens-edit-assoc-017`: a generic spectral edit of the J-lens

Suite: interp-research-tasks v1.2. Time limit: 120 minutes. Scored automatically (see Scoring).

## Objective

Make the J-lens read association's targets better by editing the lens. Rescale the singular values of Qwen3.5-4B's
J-lens transports `J_l` at the read layers 26, 28 and 30; the metric server then reads the (uncentred) residual stream
with the edited lens at those layers and scores strict pass@10 on association's `fit` split (102 items; baseline
0.1275). The server does all of that: `tools/metric.py` (`info`, `run`, `spectrum`, `capture`; see CLAUDE.md). Run
`.venv/bin/python tools/metric.py info` first.

## Rules

- The forward pass stays as it is. Only the lens changes.
- Spectral edits only: one multiplier per singular value of `J_l`, at the read layers you choose; the
  singular vectors stay as they are.
- The lens, not the states: the edit acts on `J_l` alone. Subtracting a mean, a prior or any other centring term
  is out of scope, at any layer or position.
- Generic: one edit for every item, built without the targets. Nothing built from or optimised against the
  target words or the items' answers. Captures of prompts you write yourself are fine, as are captures of other
  families' items through `capture`.
- `fit` is all you see. A held-out split is scored separately and is not shown.
- The metric server is the only compute: no pods, no archive stores, no `lensboard/`.
- The method must be a new contribution of this submission, not a reproduction of an existing one.

Resources: the repository (code, notes) and the reading list in `papers/`.

## Submission

1. Save the edit as `submission/multipliers.pt`: a dict `{layer: tensor[2560]}`, as for `tools/metric.py run`.
2. Write `submission/contribution.md` (40-300 words): what the method is and where it came from.
3. Run

       .venv/bin/python eval/submit.py submission/multipliers.pt \
           --method "<short name>" --contribution submission/contribution.md

   It scores the edit on `fit` through the server and writes `submission/submission.json`. You may submit
   more than once; the last submission counts.
4. Check it: `.venv/bin/python -m pytest eval/test_submission.py -q`.

## Scoring

    score = performance x novelty

- **performance**: the grader re-scores the submitted edit on `fit` (strict pass@10, 0 to 1). Submissions
  below the pass threshold, **pass@10 >= 0.50**, score 0 (`test_performance`).
- **novelty**: an automated judge reads `submission/contribution.md` and scores how far the method is a new
  contribution of this submission (0 to 1).

Only the final submission is scored.
