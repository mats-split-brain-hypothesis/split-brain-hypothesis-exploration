#!/bin/bash
# S16 fit screen (instance e1): form-blind kNN (PC space, template space, random control, content-disjoint),
# then the neighbour-overlap diagnostic on DM / multihop val. Stops at the first failure.
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
FIT=$(for f in $FAMS; do printf "%s/fit," $f; done); FIT=${FIT%,}
ARMS="s16pc8@fit|cos,s16pc32@fit|cos,s16pcd8@fit|cos,s16pr8@fit|cos,shuf.s16pc8@fit|cos,rand.s16pc8@fit|cos${S16_EXTRA:-}"
$PY experiments/evaluate.py --banks "$FIT" --arms "zero|cos,fam@self|cos,knnx8@fit|cos,$ARMS" --device cuda --no-sem
$PY experiments/analyse.py --study S16-fit --split fit --arms "$ARMS" --refs "zero|cos,fam@self|cos,knnx8@fit|cos"
$PY experiments/s16_overlap.py --banks directed_modulation/val,multihop/val --arms knnx8,s16pc8,s16pcd8,s16pr8 --layers 44,52
