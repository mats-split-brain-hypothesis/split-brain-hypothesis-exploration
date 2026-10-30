#!/bin/bash
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
FIT=$(for f in $FAMS; do printf "%s/fit," $f; done); FIT=${FIT%,}
$PY experiments/evaluate.py --banks "$FIT" --arms "knnx8s10@fit|cos,knnx8s25@fit|cos,knnx8s50@fit|cos" --device cuda
$PY experiments/analyse.py --study S4-fit5 --split fit --arms "knnx8s10@fit|cos,knnx8s25@fit|cos,knnx8s50@fit|cos,knnx8@fit|cos" --refs "zero|cos,fam@self|cos,tok@fit|cos"
