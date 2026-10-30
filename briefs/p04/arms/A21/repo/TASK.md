# Task `jlens-steer-assoc-017`: a generic steering intervention for the plain J-lens

Suite: interp-research-tasks v1.2. Time limit: 120 minutes. Scored automatically (see Scoring).

## Objective

Make the plain J-lens read association's targets better by changing the forward pass. Add a vector to Qwen3.5-4B's
residual stream at some layers during the forward pass; the metric server then reads with the plain (uncentred)
J-lens at layers 26, 28 and 30 and scores strict pass@10 on association's `fit` split (102 items; baseline 0.1275).
The server does all of that: `tools/metric.py` (`info`, `run`, `capture`; usage in its docstring). Run
`.venv/bin/python tools/metric.py info` first.

## Rules

- The readout stays the plain J-lens. Only the forward pass changes.
- Steering vectors only: one vector per layer, added at the positions you choose (`prefix`, `read` or `context`).
- Directions, not means: each vector has to come from a contrast between two conditions (prompts or items you
  choose). Subtracting a mean, a prior or any other centring term is out of scope, at any layer or position.
- Generic: one intervention for every item, built without the targets. Nothing built from or optimised against the
  target words or the items' answers. Contrasts over prompts you write yourself are fine, as are captures of other
  families' items through `capture`.
- `fit` is all you see. A held-out split is scored separately and is not shown.
- The metric server is the only compute.
- The method must be a new contribution of this submission, not a reproduction of an existing one.

Resources: the item banks in `data/` and the reading list in `papers/`.

## Submission

1. Save the intervention as `submission/vectors.pt`: a dict `{layer: tensor[2560]}`, as for `tools/metric.py run`.
2. Write `submission/contribution.md` (40-300 words): what the method is and where it came from.
3. Run

       .venv/bin/python eval/submit.py submission/vectors.pt --positions prefix --scale 1.0 \
           --method "<short name>" --contribution submission/contribution.md

   It scores the intervention on `fit` through the server and writes `submission/submission.json`. You may submit
   more than once; the last submission counts.
4. Check it: `.venv/bin/python -m pytest eval/test_submission.py -q`.

## Scoring

    score = performance x novelty

- **performance**: the grader re-runs the submitted intervention on `fit` (strict pass@10, 0 to 1). Submissions
  below the pass threshold, **pass@10 >= 0.50**, score 0 (`test_performance`).
- **novelty**: an automated judge reads `submission/contribution.md` and scores how far the method is a new
  contribution of this submission (0 to 1).

Only the final submission is scored.
