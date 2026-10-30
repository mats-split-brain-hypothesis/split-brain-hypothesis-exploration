#!/bin/bash
# S20k (instance e1): S20x source scaling, k random sources x 3 draws, cos and rms; fit.
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
FIT=$(for f in $FAMS; do printf "%s/fit," $f; done); FIT=${FIT%,}
ARMS=""
for k in 1 2 4 6 9; do for d in 0 1 2; do
  ARMS="$ARMS,s20xk:$k:$d:1@self|cos,s20xkrms:$k:$d:1@self|rms"
done; done
$PY experiments/evaluate.py --banks "$FIT" --arms "fam@self|rms,${ARMS#,}" --device cuda --no-sem
