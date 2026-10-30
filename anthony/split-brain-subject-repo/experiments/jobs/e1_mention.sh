#!/bin/bash
# S16c's mention control with a carrier-sharing pool (instance e1).
set -euo pipefail
.venv/bin/python experiments/u1_mention.py --device cuda --arms knnx8,knnxs8,knnxm8,knnxsm8 --out out/analysis/S16/mention
