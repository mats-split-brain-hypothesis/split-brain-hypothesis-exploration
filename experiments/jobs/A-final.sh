#!/bin/bash
# night-2 A (j-lens-mean-2e): finalist battery for S14b with knnxs8 late (steward's card): val rms read, and umot's
# mention control with a carrier-sharing pool (knnxsm8 = knnxs8 + the bank's other-pair items; knnxm8 without the
# same-carrier exclusion as the leaking contrast).
set -euo pipefail
PY=.venv/bin/python
ALL="typo association basic_readout multihop multilingual user_modeling directed_modulation typo_mt multihop_mt basic_readout_mt multilingual_mt"
B=$(for f in $ALL; do printf "%s/val," "$f"; done); B=${B%,}
$PY experiments/evaluate.py --banks "$B" --device cuda --arms "sched:40:kmx64+s14:template:64:mean=knnxs8:a=0.5@fit|rms"
$PY experiments/u1_mention.py --device cuda --out out/analysis/S14/mention-final --arms \
  "zero,fam,sched:40:kmx64+s14:template:64:mean=knnxs8:a=0.5,sched:40:kmx64+s14:template:64:mean=knnxsm8:a=0.5,sched:40:kmx64+s14:template:64:mean=knnxm8:a=0.5,knnxsm8"
