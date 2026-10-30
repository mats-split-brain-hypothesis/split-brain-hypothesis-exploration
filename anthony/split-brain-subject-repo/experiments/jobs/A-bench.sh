#!/bin/bash
# night-2 A (j-lens-mean-2e): the registered S14 bench read (studies/S14.md "s14-bench", registration commit ecc253a).
# One batched strict read of all 11 bench banks; the only bench read of the night; nothing is chosen from it.
set -euo pipefail
PY=.venv/bin/python
ALL="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
B=$(for f in $ALL; do printf "%s/bench," "$f"; done); B=${B%,}
K="sched:40:kmx64+s14t64"; S="sched:40:kmx64+s14:template:64:mean=kmx64:a=0.5"
$PY experiments/evaluate.py --banks "$B" --device cuda --arms \
  "$K@fit|cos,$K@fit|rms,$S@fit|cos,$S@fit|rms,s14t64@fit|cos,sched:40:kmxr64+s14t64@fit|cos,s14r64@fit|cos,zero|cos,zero|rms,fam@fit|cos,fam@fit|rms"
