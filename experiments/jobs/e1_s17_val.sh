#!/bin/bash
# S17 val confirmation (instance e1): the fit-chosen schedule fam -> knnx8 at L44 and the "early fam does little" check.
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
VAL=$(for f in $FAMS; do printf "%s/val," $f; done); VAL=${VAL%,}
ARMS="sched:44:fam+knnx8@fit|cos,sched:40:zero+fam@fit|cos,sched:48:fam+zero@fit|cos"
$PY experiments/evaluate.py --banks "$VAL" --arms "zero|cos,fam@fit|cos,knnx8@fit|cos,$ARMS" --device cuda --no-sem
$PY experiments/analyse.py --study S17-val --split val --arms "$ARMS" --refs "zero|cos,fam@fit|cos,knnx8@fit|cos"
