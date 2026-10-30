#!/bin/bash
# S21b (instance e1): S20x's early correction on A's S14b; fit (+ random-direction control).
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
FIT=$(for f in $FAMS; do printf "%s/fit," $f; done); FIT=${FIT%,}
B="s14:template:64:mean=kmx64:a=0.5"
$PY experiments/evaluate.py --banks "$FIT" --arms "sched:40:kmx64+$B@self|cos,sched:40:s20xon:1:kmx64+$B@self|cos,sched:40:s20xron:1:kmx64+$B@self|cos" --device cuda --no-sem
