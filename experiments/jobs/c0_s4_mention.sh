#!/bin/bash
# S4 fairness control: umot's mention-control bank read with S4 centres (U1's script, own output dir).
set -euo pipefail
.venv/bin/python experiments/u1_mention.py --device cuda --arms "zero,fam,tok,kmx64,knnx8,shuf.knnx8,knnxd2_8" --out out/analysis/S4/extra/mention
