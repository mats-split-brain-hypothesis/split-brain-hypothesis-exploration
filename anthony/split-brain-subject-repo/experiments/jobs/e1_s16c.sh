#!/bin/bash
# S16c (instance e1): knnx8 without same-carrier neighbours (the fair DM kNN), val all 11, then the overlap diagnostic.
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
VAL=$(for f in $FAMS; do printf "%s/val," $f; done); VAL=${VAL%,}
$PY experiments/evaluate.py --banks "$VAL" --arms "knnxs8@fit|cos,shuf.knnxs8@fit|cos" --device cuda --no-sem
$PY experiments/s16_overlap.py --banks directed_modulation/val --arms knnx8,knnxs8 --layers 44,52
