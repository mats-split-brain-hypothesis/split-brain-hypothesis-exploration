#!/bin/bash
# S20w (instance e1): pull back the cap / punct class prior (cos), then the fit screen (early-only on fam, all-depth control).
set -euo pipefail
PY=.venv/bin/python
$PY experiments/precompute_pullback.py --priors s20w-cap --readouts cos --ranks full --device cuda
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
FIT=$(for f in $FAMS; do printf "%s/fit," $f; done); FIT=${FIT%,}
A=""
for b in 0.5 1 2 4; do A="$A,sched:40:s13:s20w-cap:$b:fam+fam@self|cos"; done
$PY experiments/evaluate.py --banks "$FIT" --arms "${A#,},s13:s20w-cap:1:fam@self|cos" --device cuda --no-sem
