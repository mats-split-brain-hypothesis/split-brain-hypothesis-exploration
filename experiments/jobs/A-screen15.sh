#!/bin/bash
# night-2 A (j-lens-mean-2e): S14b's late partial mean from the chat corpus (kmch128, bench-free) or the family mean.
set -euo pipefail
PY=.venv/bin/python
ALL="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
B=$(for f in $ALL; do printf "%s/fit," "$f"; done); B=${B%,}
$PY experiments/evaluate.py --banks "$B" --device cuda --arms \
  "sched:40:kmx64+s14:template:64:mean=kmch128:a=0.5@self|cos,sched:40:kmx64+s14:template:64:mean=kmch128:a=1@self|cos,sched:40:kmx64+s14:template:64:mean=fam:a=0.5@self|cos"
