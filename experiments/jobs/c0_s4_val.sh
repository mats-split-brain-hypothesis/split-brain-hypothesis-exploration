#!/bin/bash
# S4 val confirmation (instance c0): fit survivors + their controls, strict; battery.
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
VAL=$(for f in $FAMS; do printf "%s/val," $f; done); VAL=${VAL%,}
ARMS="km4@fit|cos,kmx64@fit|cos,knnx8@fit|cos,knnx32@fit|cos,kmx1@fit|cos,kmxr64@fit|cos,shuf.knnx8@fit|cos,rand.knnx8@fit|cos,shuf.kmx64@fit|cos"
$PY experiments/evaluate.py --banks "$VAL" --arms "zero|cos,fam@fit|cos,tok@fit|cos,$ARMS" --device cuda
$PY experiments/analyse.py --study S4-val --split val --arms "$ARMS" --refs "zero|cos,fam@fit|cos,tok@fit|cos"
