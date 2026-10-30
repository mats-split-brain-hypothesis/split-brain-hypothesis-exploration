#!/bin/bash
# S21b robustness (instance e1): k-means seeds 1 and 2 for both kmx64 parts; val (robustness only, no choice made).
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
VAL=$(for f in $FAMS; do printf "%s/val," $f; done); VAL=${VAL%,}
A=""
for s in 1 2; do A="$A,sched:40:s20xon:1:kmx64s$s+s14:template:64:mean=kmx64s$s:a=0.5@fit|cos"; done
$PY experiments/evaluate.py --banks "$VAL" --arms "${A#,}" --device cuda --no-sem
