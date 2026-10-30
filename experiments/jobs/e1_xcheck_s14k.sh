#!/bin/bash
# Cross-check of A's finalist sched:40:kmx64+s14t64 (S14k; instance e1, steward's card): other k-means seeds, the rms
# readout (with the cos-map basis and with the rms-map basis), then another reference pool (chat-corpus clusters). Val.
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
VAL=$(for f in $FAMS; do printf "%s/val," $f; done); VAL=${VAL%,}
A1="sched:40:kmx64s1+s14t64@fit|cos,sched:40:kmx64s2+s14t64@fit|cos,kmx64s1@fit|cos"
A2="fam@fit|rms,kmx64@fit|rms,s14t64@fit|rms,sched:40:kmx64+s14t64@fit|rms,sched:40:kmx64+s14:template:64:rms@fit|rms"
$PY experiments/evaluate.py --banks "$VAL" --arms "fam@fit|cos,sched:40:kmx64+s14t64@fit|cos,$A1,$A2" --device cuda --no-sem
echo "== chat pool"
$PY experiments/evaluate.py --banks "$VAL" --arms "sched:40:kmch128+s14t64@fit|cos,sched:40:kmch32+s14t64@fit|cos" --device cuda --no-sem
