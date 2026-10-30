#!/bin/bash
# S24c baseline (steward): read the random-direction controls of S20x and s20xon on val2 (controls, not candidates:
# no selection), then dump their flips vs fam, and fam's flips vs zero.
set -uo pipefail
cd "$(dirname "$0")/../.."
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-8}"
.venv/bin/python experiments/evaluate.py --banks typo/val2,association/val2,multihop/val2 --no-next --device cuda \
  --arms "rand.s20xt:1@fit|cos,rand.s20xon:1:kmx64@fit|cos,rand.sched:40:kmx64+s14:template:64:mean=knnxs8:a=0.5@fit|cos" || exit 1
.venv/bin/python experiments/s24c_dump.py --device cuda --tag=-ctrl \
  --arms "rand.S20x=rand.s20xt:1@fit|cos,rand.s20xon=rand.s20xon:1:kmx64@fit|cos,rand.S14b-x=rand.sched:40:kmx64+s14:template:64:mean=knnxs8:a=0.5@fit|cos" || exit 1
.venv/bin/python experiments/s24c_dump.py --device cuda --tag=-famvszero --ref zero --arms "fam=fam@fit|cos" || exit 1
echo "[s24cctrl] done"
