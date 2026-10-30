#!/bin/bash
# S20w follow-up (instance e1): the all-depth class prior on fam, beta grid; fit.
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
FIT=$(for f in $FAMS; do printf "%s/fit," $f; done); FIT=${FIT%,}
$PY experiments/evaluate.py --banks "$FIT" --arms "s13:s20w-cap:0.5:fam@self|cos,s13:s20w-cap:2:fam@self|cos,s13:s20w-cap:4:fam@self|cos,sched:40:fam+s13:s20w-cap:1:fam@self|cos" --device cuda --no-sem
