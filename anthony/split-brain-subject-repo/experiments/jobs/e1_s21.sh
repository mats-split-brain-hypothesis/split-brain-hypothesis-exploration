#!/bin/bash
# S21 (instance e1): S14k + S20x's correction (all layers / early only / late only) and the random-direction control;
# fit, then val; per-unit _mt proxy on val.
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
FIT=$(for f in $FAMS; do printf "%s/fit," $f; done); FIT=${FIT%,}
VAL=$(for f in $FAMS; do printf "%s/val," $f; done); VAL=${VAL%,}
A="sched:40:s20xon:1:kmx64+s20xon:1:s14t64,sched:40:s20xon:1:kmx64+s14t64,sched:40:kmx64+s20xon:1:s14t64,sched:40:s20xron:1:kmx64+s20xron:1:s14t64"
FA=$(echo "$A" | sed 's/,/@self|cos,/g')@self\|cos
VA=$(echo "$A" | sed 's/,/@fit|cos,/g')@fit\|cos
$PY experiments/evaluate.py --banks "$FIT" --arms "sched:40:kmx64+s14t64@self|cos,$FA" --device cuda --no-sem
$PY experiments/evaluate.py --banks "$VAL" --arms "$VA" --device cuda --no-sem
$PY experiments/analyse.py --study S21-val --split val --arms "$VA" --refs "fam@fit|cos,sched:40:kmx64+s14t64@fit|cos,s20xt:1@fit|cos"
