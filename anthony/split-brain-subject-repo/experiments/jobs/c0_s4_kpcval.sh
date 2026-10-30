#!/bin/bash
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
VAL=$(for f in $FAMS; do printf "%s/val," $f; done); VAL=${VAL%,}
$PY experiments/evaluate.py --banks "$VAL" --arms "kpc16_8@fit|cos,shuf.kpc16_8@fit|cos,rand.kpc16_8@fit|cos" --device cuda
$PY experiments/analyse.py --study S4-val-kpc --split val --arms "kpc16_8@fit|cos,shuf.kpc16_8@fit|cos,rand.kpc16_8@fit|cos,knnx8@fit|cos,kmx64@fit|cos" --refs "zero|cos,fam@fit|cos,tok@fit|cos"
