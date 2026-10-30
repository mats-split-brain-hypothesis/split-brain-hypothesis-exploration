#!/bin/bash
# S24b on a capture pod: gate, freeze, capture the val2b items (multihop's closed-answer subfamilies + multilingual).
set -uo pipefail
cd "$(dirname "$0")/../.."
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-8}"
PY=.venv/bin/python
step() { echo "[s24b $(date -u +%H:%M:%S)] $*"; }
step "gate"; $PY experiments/s24_build.py gate --set val2b --device cuda || { step "FAILED gate"; exit 1; }
step "freeze"; $PY experiments/s24_build.py freeze --set val2b || { step "FAILED freeze"; exit 1; }
step "capture"; $PY experiments/capture_dev_banks.py --families multihop,multilingual --splits val2b --device cuda || { step "FAILED capture"; exit 1; }
step "done"
