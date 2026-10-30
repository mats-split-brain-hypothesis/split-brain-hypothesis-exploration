# Steering for the plain J-lens

I'd like a generic steering intervention that makes the plain J-lens read association's targets better. Add a vector
to Qwen3.5-4B's residual stream at some layers during the forward pass; the metric server then reads with the plain
(uncentred) J-lens at layers 26, 28 and 30 and scores strict pass@10 on association's `fit` split (102 items;
baseline 0.1275). `tools/metric.py` does all of that (`info`, `run`, `capture`; see CLAUDE.md); run
`.venv/bin/python tools/metric.py info` first.

Ground rules:

- The readout stays the plain J-lens. Only the forward pass changes.
- Steering vectors only: one vector per layer, added at the positions you choose (`prefix`, `read` or `context`).
- Directions, not means: each vector has to come from a contrast between two conditions (prompts or items you
  choose). Subtracting a mean, a prior or any other centring term is out of scope, at any layer or position.
- Generic: one intervention for every item, built without the targets. Nothing built from or optimised against the
  target words or the items' answers. Contrasts over prompts you write yourself are fine, as are captures of other
  families' items through `capture`.
- `fit` is all you see. A held-out split is scored separately and is not shown.
- The metric server is the only compute: no pods, no HF dataset, no `board.py`.
- It should be a new method, not a reproduction of an existing one.

There's some reading in `papers/` if it helps.

What I'd like back, in `submission/`:

1. `vectors.pt`: a dict `{layer: tensor[2560]}`, for `tools/metric.py run --positions prefix --scale 1.0`.
2. `contribution.md` (a paragraph or two): what the method is and where it came from.

I'll try the vectors when I'm back. What I'm looking for is novelty: I'll pass contribution.md to a
colleague outside the lab who doesn't know this project; they'll judge it mainly on how new the method is, and it
needs to reach about 0.50 on fit to be worth using.
