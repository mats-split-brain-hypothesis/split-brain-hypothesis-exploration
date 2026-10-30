#!/bin/bash
# S4 round 2 (instance c0): content-disjoint kNN control (fit + val) and the wikitext pool (fit screen).
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
FIT=$(for f in $FAMS; do printf "%s/fit," $f; done); FIT=${FIT%,}
VAL=$(for f in $FAMS; do printf "%s/val," $f; done); VAL=${VAL%,}
$PY experiments/evaluate.py --banks "$VAL" --arms "knnxd8@fit|cos,knnxd32@fit|cos" --device cuda
$PY experiments/evaluate.py --banks "$FIT" --arms "knnxd8@fit|cos,knnxd32@fit|cos,kmw1@fit|cos,kmw8@fit|cos,kmw32@fit|cos,kmw128@fit|cos,kmwr32@fit|cos,knnw32@fit|cos" --device cuda
$PY experiments/analyse.py --study S4-val --split val --arms "km4@fit|cos,kmx64@fit|cos,knnx8@fit|cos,knnx32@fit|cos,knnxd8@fit|cos,knnxd32@fit|cos,kmx1@fit|cos,kmxr64@fit|cos,shuf.knnx8@fit|cos,rand.knnx8@fit|cos,shuf.kmx64@fit|cos" --refs "zero|cos,fam@fit|cos,tok@fit|cos"
$PY experiments/analyse.py --study S4-fit2 --split fit --arms "knnx8@fit|cos,knnxd8@fit|cos,knnxd32@fit|cos,kmw1@fit|cos,kmw8@fit|cos,kmw32@fit|cos,kmw128@fit|cos,kmwr32@fit|cos,knnw32@fit|cos" --refs "zero|cos,fam@self|cos,tok@fit|cos"
