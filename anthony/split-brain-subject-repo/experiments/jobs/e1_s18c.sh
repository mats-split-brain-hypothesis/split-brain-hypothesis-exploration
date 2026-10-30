#!/bin/bash
# S18c (instance e1): the chat-corpus mean, whole and without its outlier coordinates; fit.
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
FIT=$(for f in $FAMS; do printf "%s/fit," $f; done); FIT=${FIT%,}
$PY experiments/evaluate.py --banks "$FIT" --arms "s18cfull@self|cos,s18cc8@self|cos,s18cc32@self|cos,s18cc128@self|cos" --device cuda --no-sem
