#!/bin/bash
# S21c lead (instance e1): kmx64 + S20x's correction as one centre at every layer; val battery, cos and rms.
set -euo pipefail
.venv/bin/python experiments/analyse.py --study S21c-val --split val --arms "s20xon:1:kmx64@fit|cos" --refs "fam@fit|cos,kmx64@fit|cos,sched:40:s20xon:1:kmx64+s14:template:64:mean=kmx64:a=0.5@fit|cos"
.venv/bin/python experiments/analyse.py --study S21c-val-rms --split val --arms "s20xonrms:1:kmx64@fit|rms" --refs "fam@fit|rms,kmx64@fit|rms"
