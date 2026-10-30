#!/bin/bash
# night-2 A (j-lens-mean-2e): robustness of sched:40:kmx64+s14t64 on fit (cluster count, the cluster control, the
# bench-free late list, chat-corpus clusters early = no bench cell anywhere) and its rms readout on val.
set -euo pipefail
PY=.venv/bin/python
ALL="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
F=$(for f in $ALL; do printf "%s/fit," "$f"; done); F=${F%,}
V=$(for f in $ALL; do printf "%s/val," "$f"; done); V=${V%,}
C=""
for e in kmx32 kmx128 kmxr64 kmch32 kmch128; do C="${C}sched:40:$e+s14t64@self|cos,"; done
C="${C}sched:40:kmx64+s14:chatonly:128@self|cos,sched:40:kmch128+s14:chatonly:128@self|cos,kmch128@self|cos,sched:40:kmx64+s14t64@self|rms"
$PY experiments/evaluate.py --banks "$F" --arms "$C" --device cuda
$PY experiments/evaluate.py --banks "$V" --arms "sched:40:kmx64+s14t64@fit|rms,sched:40:kmxr64+s14t64@fit|cos" --device cuda
