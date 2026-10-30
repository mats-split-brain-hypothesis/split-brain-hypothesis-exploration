# Instance C (night-2): ceilings and learned g

Cards: **S20** (headroom ceilings per class of g, in-sample, diagnostic), then **S19** (learned g with the controls
as the loss). S20 says how much each class of g can gain at all; S19 is the learned row of the research-loop table,
never run. S20 first: its answer tells everyone whether constant-g work (A's S13 / S14, B's S18) is bounded.

Suggested start (change it if the evidence says so):
1. S20: `experiments/ceilings.py --family F --split fit [--val] --device cuda` on the eval pod (user_modeling is too
   slow on the Mac), classes const, tok, clu, proj16; in-sample and K-fold by group; the val read as an upper bound.
   Arms carry `ceil.` and go to `out/analysis/S20/`, never `out/eval`. Send A and B one line with the headline as soon
   as the const and proj16 ceilings are in: it bears on their cards.
2. S19: write `experiments/s19_fit.py` (fitter: rank-r A plus b per layer, pooled fit cells, own group out at read
   time; loss = readout mass on the cell's prompt tokens + the model's next-token top-k + lambda ||g||^2; no targets).
   `s19b`, `s19r4`, `s19r16`, with the shuffled-prompt control, the fit-val gap, prompt masking, the mention control
   (carrier-sharing pool), `L(g)` decoded.

Second wave, if your insights do not point elsewhere: an h-dependent ceiling (kNN-mean with a learned metric, or
rank-k projection plus a per-cluster offset) to bound S16-type g; S19 with one loss term at a time (prompt only,
next-token only) to see which term does the work; per-family S20 ceilings at the item level (which items no g of a
class can fix, and what their readouts look like: the readout's limit, not the centre's).

Judge allowance: about $8 (S19 survivors on val; S20's ceilings are scored strict / exact item rule, no judge).
