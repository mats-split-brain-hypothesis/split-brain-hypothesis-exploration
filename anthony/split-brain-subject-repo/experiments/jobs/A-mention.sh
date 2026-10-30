#!/bin/bash
# night-2 A (j-lens-mean-2e): umot's mention control (B's u1_mention.py) for the S14 finalists and their parts.
set -euo pipefail
.venv/bin/python experiments/u1_mention.py --device cuda --out out/analysis/S14/mention --arms \
  "zero,fam,kmx64,s14t64,sched:40:kmx64+s14t64,sched:40:kmx64+s14:template:64:mean=kmx64:a=0.5,shuf.kmx64"
