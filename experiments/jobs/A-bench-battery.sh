#!/bin/bash
# night-2 A (j-lens-mean-2e): battery for the registered S14 bench read (paired differences, guardrail).
set -euo pipefail
.venv/bin/python experiments/analyse.py --study S14-bench --split bench --refs "zero|cos,fam@fit|cos" --arms \
  "sched:40:kmx64+s14t64@fit|cos,sched:40:kmx64+s14:template:64:mean=kmx64:a=0.5@fit|cos,s14t64@fit|cos,sched:40:kmxr64+s14t64@fit|cos,s14r64@fit|cos"
.venv/bin/python experiments/analyse.py --study S14-bench-rms --split bench --refs "zero|rms,fam@fit|rms" --arms \
  "sched:40:kmx64+s14t64@fit|rms,sched:40:kmx64+s14:template:64:mean=kmx64:a=0.5@fit|rms"
