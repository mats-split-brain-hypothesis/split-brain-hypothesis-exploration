#!/bin/bash
# S23b component (instance e1): S21b's early part alone (kmx64 + correction) at every layer, fit and val, cos and rms.
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
FIT=$(for f in $FAMS; do printf "%s/fit," $f; done); FIT=${FIT%,}
VAL=$(for f in $FAMS; do printf "%s/val," $f; done); VAL=${VAL%,}
$PY experiments/evaluate.py --banks "$FIT" --arms "s20xon:1:kmx64@self|cos,s20xonrms:1:kmx64@self|rms" --device cuda --no-sem
$PY experiments/evaluate.py --banks "$VAL" --arms "s20xon:1:kmx64@fit|cos,s20xonrms:1:kmx64@fit|rms" --device cuda --no-sem
