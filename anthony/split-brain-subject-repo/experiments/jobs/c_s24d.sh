#!/bin/bash
# S24d on a capture pod: gate, freeze, capture the val3 items (typo, association, multihop open-answer).
set -uo pipefail
cd "$(dirname "$0")/../.."
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-8}"
PY=.venv/bin/python
step() { echo "[s24d $(date -u +%H:%M:%S)] $*"; }
step "gate"; $PY experiments/s24_build.py gate --set val3 --device cuda || { step "FAILED gate"; exit 1; }
step "freeze"; $PY experiments/s24_build.py freeze --set val3 || { step "FAILED freeze"; exit 1; }
step "capture"; $PY experiments/capture_dev_banks.py --families typo,association,multihop --splits val3 --device cuda || { step "FAILED capture"; exit 1; }
step "done"
