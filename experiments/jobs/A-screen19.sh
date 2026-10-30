#!/bin/bash
# night-2 A (j-lens-mean-2e): S14bl on fit, then val (cos) for the judged multilingual_mt check.
set -euo pipefail
PY=.venv/bin/python
ALL="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
F=$(for f in $ALL; do printf "%s/fit," "$f"; done); F=${F%,}
V=$(for f in $ALL; do printf "%s/val," "$f"; done); V=${V%,}
A="sched:40:kmx64+s14:template:64:mean=knnxl8:a=0.5"
$PY experiments/evaluate.py --banks "$F" --device cuda --arms "$A@self|cos,sched:40:kmx64+s14:template:64:mean=knnxs8:a=0.5@self|rms,$A@self|rms"
$PY experiments/evaluate.py --banks "$V" --device cuda --arms "$A@fit|cos"
