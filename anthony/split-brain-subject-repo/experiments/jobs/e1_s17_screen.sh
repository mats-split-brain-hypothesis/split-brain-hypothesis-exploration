#!/bin/bash
# S17 fit screen (instance e1): depth schedules fam -> zero / knnx8, the swapped control, L_s in {40, 44, 48, 52}.
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
FIT=$(for f in $FAMS; do printf "%s/fit," $f; done); FIT=${FIT%,}
ARMS=""
for L in 40 44 48 52; do
  ARMS="$ARMS,sched:$L:fam+zero@self|cos,sched:$L:zero+fam@self|cos,sched:$L:fam+knnx8@self|cos"
done
ARMS=${ARMS#,}
$PY experiments/evaluate.py --banks "$FIT" --arms "zero|cos,fam@self|cos,knnx8@fit|cos,$ARMS" --device cuda --no-sem
$PY experiments/analyse.py --study S17-fit --split fit --arms "$ARMS" --refs "zero|cos,fam@self|cos,knnx8@fit|cos"
