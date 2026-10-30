#!/bin/bash
# knnxs8 val battery (guardrail vs fam) for the finalists table, both readouts.
set -euo pipefail
.venv/bin/python experiments/analyse.py --study S16c-val --split val --arms "knnxs8@fit|cos" --refs "fam@fit|cos,knnx8@fit|cos"
.venv/bin/python experiments/analyse.py --study S16c-val-rms --split val --arms "knnxs8@fit|rms" --refs "fam@fit|rms"
