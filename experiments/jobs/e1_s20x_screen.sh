#!/bin/bash
# S20x fit screen (instance e1): fam + alpha * the other families' mean target-fitted correction; random control.
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
FIT=$(for f in $FAMS; do printf "%s/fit," $f; done); FIT=${FIT%,}
ARMS="s20x:0.5@self|cos,s20x:1@self|cos,s20x:2@self|cos,s20x:3@self|cos,s20xr:1@self|cos,s20xr:2@self|cos"
$PY experiments/evaluate.py --banks "$FIT" --arms "zero|cos,fam@self|cos,$ARMS" --device cuda --no-sem
$PY experiments/analyse.py --study S20x-fit --split fit --arms "$ARMS" --refs "zero|cos,fam@self|cos" --decode-g --device cuda
