#!/bin/bash
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
FIT=$(for f in $FAMS; do printf "%s/fit," $f; done); FIT=${FIT%,}
$PY experiments/evaluate.py --banks "$FIT" --arms "kmxs16@fit|cos,kmxs64@fit|cos" --device cuda
$PY experiments/analyse.py --study S4-fit8 --split fit --arms "kmx16@fit|cos,kmxs16@fit|cos,kmx64@fit|cos,kmxs64@fit|cos" --refs "zero|cos,fam@self|cos,tok@fit|cos"
