#!/bin/bash
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
FIT=$(for f in $FAMS; do printf "%s/fit," $f; done); FIT=${FIT%,}
VAL=$(for f in $FAMS; do printf "%s/val," $f; done); VAL=${VAL%,}
$PY experiments/evaluate.py --banks "$FIT" --arms "knnx4@fit|cos,knnx16@fit|cos,knnx8@fit|rms,kmx64@fit|rms" --device cuda
$PY experiments/evaluate.py --banks "$VAL" --arms "knnx8@fit|rms,kmx64@fit|rms" --device cuda
$PY experiments/analyse.py --study S4-fit4 --split fit --arms "knnx4@fit|cos,knnx8@fit|cos,knnx16@fit|cos,knnx32@fit|cos,knnx8@fit|rms,kmx64@fit|rms" --refs "zero|cos,fam@self|cos,tok@fit|cos,fam@self|rms"
$PY experiments/analyse.py --study S4-val-rms --split val --arms "knnx8@fit|rms,kmx64@fit|rms" --refs "zero|rms,fam@fit|rms,tok@fit|rms"
