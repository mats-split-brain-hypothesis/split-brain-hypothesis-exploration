#!/bin/bash
# S4 fit screen + U4 battery rerun (instance c0). Stops at the first failing step.
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
FIT=$(for f in $FAMS; do printf "%s/fit," $f; done); FIT=${FIT%,}
VAL=$(for f in $FAMS; do printf "%s/val," $f; done); VAL=${VAL%,}
echo "== U4 battery"
$PY experiments/analyse.py --study U4-val --split val --arms "jpp:zero|cos,jpp:fam@fit|cos,jpp:tok@fit|cos" --refs "zero|cos,fam@fit|cos,tok@fit|cos"
$PY experiments/analyse.py --study U4-fit --split fit --arms "jpp:zero|cos,jpp:fam@fit|cos,jpp:tok@fit|cos" --refs "zero|cos,fam@fit|cos,tok@fit|cos"
$PY experiments/study_U4.py --split val; $PY experiments/study_U4.py --split fit
echo "== S4 diagnostics"
$PY experiments/study_S4.py --pool bench
echo "== S4 fit screen"
ARMS="km1@self|cos,km2@self|cos,km4@self|cos,km8@self|cos,kmr4@self|cos,kmx1@fit|cos,kmx8@fit|cos,kmx16@fit|cos,kmx32@fit|cos,kmx64@fit|cos,kmx128@fit|cos,kmxr16@fit|cos,kmxr64@fit|cos,knnx8@fit|cos,knnx32@fit|cos,knnx128@fit|cos"
$PY experiments/evaluate.py --banks "$FIT" --arms "zero|cos,fam@self|cos,tok@fit|cos,$ARMS" --device cuda
$PY experiments/analyse.py --study S4-fit --split fit --arms "$ARMS" --refs "zero|cos,fam@self|cos,tok@fit|cos"
echo "== S4 wiki diagnostics"
$PY experiments/study_S4.py --pool wiki --ks 8,32,128,512
