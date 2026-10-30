# Dashboard `catalog.py` lines for the night-2 finalists (to paste)

Compiled by instance B (j-lens-mean-e1) on the steward's card, 07:10 BST. Not landed: the main checkout has
uncommitted edits to `dashboard/catalog.py`, and a commit touching it would block the fast-forward. **Paste the block
below into `CENTRES`** (after `"s15famtop32"`); it supersedes the three lines in `studies/S14.md` ("Dashboard:
`catalog.py` lines") and this file's earlier version. Keys are the arms' centre names exactly as `out/eval` records
them (the part before `@`); orders 74-84 follow the existing 73. Supervised centres say so in their label and
description.

```python
    "s14t64": Centre("Template reading directions removed", "#d62728", "#e05a5a", "Label-free, no reference cells: g = P h, P "
                     "the projection on the lens's reading directions of 64 template tokens (S14).", 74),
    "sched:40:kmx64+s14t64": Centre("S14k: clusters ≤ L40, template above", "#ff7f0e", "#ffa04d", "Label-free: the cell's "
                                    "k-means cluster mean (kmx64) up to L40, the template projection above (S14k; did not "
                                    "replicate on fresh val2).", 75),
    "sched:40:kmx64+s14:template:64:mean=kmx64:a=0.5": Centre("S14b: clusters ≤ L40, template − ½ cluster above",
        "#bcbd22", "#d4d55a", "Label-free: kmx64 up to L40; above, the template projection of h − 0.5·μ_cluster (S14b).", 76),
    "sched:40:kmx64+s14:template:64:mean=knnxs8:a=0.5": Centre("S14b-x: template − ½ 8-nearest above", "#2ca02c",
        "#5cc25c", "Label-free: kmx64 up to L40; above, the template projection of h − 0.5·(mean of the 8 nearest fit "
        "cells sharing no carrier with the cell) (A, S14; fresh val2+val3 +0.039).", 77),
    "sched:40:kmx64+s14:template:64:mean=knnxd8l:a=0.5": Centre("S14bL: as S14b-x, other languages only", "#00a6a6",
        "#33c4c4", "Label-free finalist: as S14b-x, the late neighbours also exclude cells whose prompt is in the cell's "
        "own non-English language (detected from the prompt text): keeps multilingual_mt's language unit (A, S14).", 78),
    "knnxs8": Centre("8 nearest cells, other carriers only", "#4c9a2a", "#73b852", "Label-free: the mean of the 8 nearest "
                     "fit read cells of any family, none sharing the cell's carrier sentence (S16c: knnx8's same-sentence "
                     "leak removed).", 79),
    "s20xt:1": Centre("S20x: fam + learned correction (supervised)", "#e377c2", "#f0a0d8", "SUPERVISED (other families' "
                      "fit targets): the family mean plus the average of the other families' target-fitted constant "
                      "corrections (S20), the read family and its _mt twin left out (S20x; fresh val2+val3 +0.051).", 80),
    "s20xon:1:kmx64": Centre("Clusters + learned correction (supervised)", "#a05195", "#c07ab5", "SUPERVISED: the k-means "
                             "cluster mean (kmx64) plus S20x's correction at every layer (S20x / S23b; fails the "
                             "multilingual_mt guardrail on val, cos).", 81),
    "sched:40:s20xon:1:kmx64+s14:template:64:mean=kmx64:a=0.5": Centre("S21b: S14b + early learned correction "
        "(supervised)", "#7f7f7f", "#a5a5a5", "SUPERVISED: S14b with S20x's correction added up to L40 (S21; fresh "
        "val2+val3 +0.039).", 82),
    "s20xonrms:1:kmx64": Centre("Clusters + learned correction, rms-fitted (supervised)", "#c49c94", "#d8b8b0",
        "SUPERVISED: as s20xon:1:kmx64 with the corrections refitted through the rms map (read with |rms).", 83),
    "s18c8": Centre("Family mean without its 8 outlier coordinates", "#6b4226", "#8f6a4f", "g = μ_fam with its 8 largest "
                    "coordinates zeroed: reads like fam (S18: the outliers hold most of the norm and none of the gain).", 84),
```

## Suggested `DEFAULT_CENTRES`

Every default arm is rendered on load, so keep it short. Suggested:

```python
DEFAULT_CENTRES = ("zero", "fam", "sched:40:kmx64+s14:template:64:mean=knnxd8l:a=0.5", "s20xt:1")
```

That shows the plain lens, the family mean, the label-free finalist (S14bL) and the supervised one (S20x). It drops
`jpp:zero`, `knnx8` and `pco16` from the defaults; they stay one click away. Keep `knnx8` if the Passage → readouts page
should open with the kNN family too. The defaults pick each arm on the held reference (`@fit` on val), which exists for
all four on val, val2 and val3. S14bL exists only on cos for val2 and val3, and on cos and rms for val.
