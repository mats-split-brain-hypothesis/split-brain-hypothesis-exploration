#!/bin/bash
# S16b fit screen (instance e1): kNN with the outlier coordinates left out of the distance; overlap diagnostic.
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
FIT=$(for f in $FAMS; do printf "%s/fit," $f; done); FIT=${FIT%,}
ARMS="s16xo8@fit|cos,s16xo32@fit|cos,s16xopc8@fit|cos,shuf.s16xo8@fit|cos,rand.s16xo8@fit|cos"
$PY experiments/evaluate.py --banks "$FIT" --arms "zero|cos,fam@self|cos,knnx8@fit|cos,$ARMS" --device cuda --no-sem
$PY experiments/analyse.py --study S16b-fit --split fit --arms "$ARMS" --refs "zero|cos,fam@self|cos,knnx8@fit|cos"
$PY experiments/s16_overlap.py --banks directed_modulation/val,multihop/val --arms s16xo8,s16xopc8 --layers 44,52
