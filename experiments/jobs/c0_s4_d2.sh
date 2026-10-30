#!/bin/bash
# S4 round 3 (instance c0): kNN with idiosyncratic-word exclusion (knnxd2_), fit + val.
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
FIT=$(for f in $FAMS; do printf "%s/fit," $f; done); FIT=${FIT%,}
VAL=$(for f in $FAMS; do printf "%s/val," $f; done); VAL=${VAL%,}
$PY experiments/evaluate.py --banks "$FIT" --arms "knnxd2_8@fit|cos" --device cuda
$PY experiments/evaluate.py --banks "$VAL" --arms "knnxd2_8@fit|cos" --device cuda
$PY experiments/analyse.py --study S4-val --split val --arms "km4@fit|cos,kmx64@fit|cos,knnx8@fit|cos,knnx32@fit|cos,knnxd8@fit|cos,knnxd2_8@fit|cos,knnxd32@fit|cos,kmx1@fit|cos,kmxr64@fit|cos,shuf.knnx8@fit|cos,rand.knnx8@fit|cos,shuf.kmx64@fit|cos" --refs "zero|cos,fam@fit|cos,tok@fit|cos"
