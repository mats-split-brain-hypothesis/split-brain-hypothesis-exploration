#!/bin/bash
# night-2 A (j-lens-mean-2e): S14b val (alpha = 0.5 chosen on fit), strict, all 11, cos and rms; its control.
set -euo pipefail
PY=.venv/bin/python
ALL="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
B=$(for f in $ALL; do printf "%s/val," "$f"; done); B=${B%,}
A="sched:40:kmx64+s14:template:64:mean=kmx64:a=0.5"
$PY experiments/evaluate.py --banks "$B" --device cuda --arms "$A@fit|cos,$A@fit|rms,sched:40:kmx64+s14:template:64:mean=kmxr64:a=0.5@fit|cos"
