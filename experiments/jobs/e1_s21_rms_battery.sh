#!/bin/bash
# S21 readout-matched (rms): the battery (paired intervals, guardrail) against rms fam and rms S14k, val.
set -euo pipefail
.venv/bin/python experiments/analyse.py --study S21-rms-val --split val --arms "sched:40:s20xonrms:1:kmx64+s14t64@fit|rms,s20xtrms:1@fit|rms" --refs "fam@fit|rms,sched:40:kmx64+s14t64@fit|rms"
