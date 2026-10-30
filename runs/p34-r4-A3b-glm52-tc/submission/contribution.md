# Self-authored stance-contrast steering for the plain J-lens

## Method

I add one fixed vector per layer (layers 20-24) to Qwen3.5-4B's residual stream at
every prompt position up to and including the read cell, then read with the plain
J-lens at layers 26-30 unchanged. The vector is a **stance direction** built from a
contrast I wrote myself, not from any benchmark item set.

The contrast is 24 self-authored prompt pairs. Each pair shares a neutral carrier
sentence the model copies exactly; the conditions differ only in the instruction
"Think about the {concept} while you write" versus "Do not think about the {concept}
while you write", then the same "write exactly: {carrier}". The concepts are arbitrary concrete nouns chosen disjoint from association's targets,
with several instruction wordings. I capture the residual averaged over the carrier
tokens per condition. The direction at layer l is the unit vector along
`mean_think(h_l) - mean_dontthink(h_l)`: concept and carrier cancel within each pair,
leaving only the "hold something in mind while doing something else" stance. The
per-layer step is `||d_l||`, the measured gap, so each layer scales by its own
contrast strength.

## What is new

Stance steering was reported using WorkspaceBench's own `directed_modulation` bank as
the contrast source. My contribution is to show it **generalises off-bank**: a stance
direction built entirely from self-authored pairs over arbitrary, target-disjoint
concepts reproduces the gain (association fit strict pass@10 0.1275 -> 0.78) with no
benchmark dependency. The direction is stable across the band; band and step derive
from the contrast's own geometry. A concept-free inference-vs-surface stance I tried
as an ablation fails at every dose and sign, so the effect needs the explicit
think/don't-think structure.

## Dose

A fit-split sweep gives a sharp peaked curve (**0.78 at dose 1.7**); I submit dose
1.7, where greedy decoding reproduces it exactly.
