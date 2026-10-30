#!/bin/bash
# S21b val (instance e1): the correction up to L40 on S14b, cos and rms-matched, with the random control; battery.
set -euo pipefail
PY=.venv/bin/python
FAMS="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
VAL=$(for f in $FAMS; do printf "%s/val," $f; done); VAL=${VAL%,}
B="s14:template:64:mean=kmx64:a=0.5"
ARMS="sched:40:s20xon:1:kmx64+$B@fit|cos,sched:40:s20xron:1:kmx64+$B@fit|cos,sched:40:s20xonrms:1:kmx64+$B@fit|rms"
$PY experiments/evaluate.py --banks "$VAL" --arms "sched:40:kmx64+$B@fit|rms,$ARMS" --device cuda --no-sem
$PY experiments/analyse.py --study S21b-val --split val --arms "sched:40:s20xon:1:kmx64+$B@fit|cos,sched:40:s20xron:1:kmx64+$B@fit|cos" --refs "fam@fit|cos,sched:40:kmx64+$B@fit|cos"
$PY experiments/analyse.py --study S21b-val-rms --split val --arms "sched:40:s20xonrms:1:kmx64+$B@fit|rms" --refs "fam@fit|rms,sched:40:kmx64+$B@fit|rms"
