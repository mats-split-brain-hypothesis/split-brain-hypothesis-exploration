#!/bin/bash
# S20x robustness (instance e1): plain-only vs _mt-only source families (alpha fixed at 1 from the fit screen), on fit
# and val; decode of dbar. Stops at the first failure.
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
FIT=$(for f in $FAMS; do printf "%s/fit," $f; done); FIT=${FIT%,}
VAL=$(for f in $FAMS; do printf "%s/val," $f; done); VAL=${VAL%,}
$PY experiments/evaluate.py --banks "$FIT" --arms "s20xp:1@self|cos,s20xm:1@self|cos" --device cuda --no-sem
$PY experiments/evaluate.py --banks "$VAL" --arms "s20xp:1@fit|cos,s20xm:1@fit|cos" --device cuda --no-sem
$PY experiments/s20x_decode.py
