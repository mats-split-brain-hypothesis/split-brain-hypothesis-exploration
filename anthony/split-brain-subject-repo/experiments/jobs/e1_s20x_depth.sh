#!/bin/bash
# S20x depth (instance e1): the correction only up to L40 / only above it (fit).
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
FIT=$(for f in $FAMS; do printf "%s/fit," $f; done); FIT=${FIT%,}
$PY experiments/evaluate.py --banks "$FIT" --arms "sched:40:fam+s20xt:1@self|cos,sched:40:s20xt:1+fam@self|cos,sched:48:fam+s20xt:1@self|cos" --device cuda --no-sem
