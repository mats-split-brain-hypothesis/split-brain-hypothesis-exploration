#!/bin/bash
# night-2 A (j-lens-mean-2e): S22 on fit. The late partial mean of S14b from the item-free S2 fills.
set -euo pipefail
PY=.venv/bin/python
ALL="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
B=$(for f in $ALL; do printf "%s/fit," "$f"; done); B=${B%,}
C=""
for m in s22nn4 s22nn8 s22nn16 s22pm; do C="${C}sched:40:kmx64+s14:template:64:mean=$m:a=0.5@self|cos,"; done
C="${C}sched:40:kmx64+s14:template:64:mean=s22nn8:a=1@self|cos"
$PY experiments/evaluate.py --banks "$B" --device cuda --arms "$C"
