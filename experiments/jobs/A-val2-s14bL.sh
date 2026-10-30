#!/bin/bash
# night-2 A (j-lens-mean-2e): the registered val2 read of S14bL (studies/S14.md "s14bL-val2"), C's val2 settings, read once.
set -uo pipefail
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-8}"
A="sched:40:kmx64+s14:template:64:mean=knnxd8l:a=0.5"
.venv/bin/python experiments/evaluate.py --banks "typo/val2,association/val2,multihop/val2" --arms "$A@fit|cos,$A@fit|rms" --no-next --device cuda || { echo "[s14bL-val2] FAILED"; exit 1; }
echo "[s14bL-val2] done"
