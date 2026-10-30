#!/bin/bash
# Robustness (instance e1): the rms readout for knnxs8 (S16c) and S21's early-only schedule, val.
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
VAL=$(for f in $FAMS; do printf "%s/val," $f; done); VAL=${VAL%,}
$PY experiments/evaluate.py --banks "$VAL" --arms "knnx8@fit|rms,knnxs8@fit|rms,sched:40:s20xon:1:kmx64+s14t64@fit|rms,s20xt:1@fit|rms" --device cuda --no-sem
