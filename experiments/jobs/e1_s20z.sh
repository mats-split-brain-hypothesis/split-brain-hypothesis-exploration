#!/bin/bash
# S20z (instance e1): pull back the token-class prior and its permuted control (cos map), then the fit beta screen.
set -euo pipefail
PY=.venv/bin/python
$PY experiments/precompute_pullback.py --priors s20z-latin,s20z-latin-shuf --readouts cos --ranks full --device cuda
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
FIT=$(for f in $FAMS; do printf "%s/fit," $f; done); FIT=${FIT%,}
ARMS=""
for b in 0.25 0.5 1 2 4; do ARMS="$ARMS,s13:s20z-latin:$b:fam@self|cos"; done
ARMS="${ARMS#,},s13:s20z-latin-shuf:1:fam@self|cos,s13:s20z-latin-shuf:2:fam@self|cos"
$PY experiments/evaluate.py --banks "$FIT" --arms "zero|cos,fam@self|cos,$ARMS" --device cuda --no-sem
