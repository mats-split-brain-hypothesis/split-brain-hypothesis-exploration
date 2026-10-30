#!/bin/bash
# S24 on a capture pod (the 27B): gate the filtered val2 items, freeze data/dev/<family>/val2.json, capture their read
# cells into out/captures (the volume). One job, stops at the first failure. Afterwards copy data/dev/*/val2.json and
# data/dev/val2-authoring/gate-qwen27b.json back to the Mac (they are in git, not in out/) and commit them.
set -uo pipefail
cd "$(dirname "$0")/../.."
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-8}"
PY=.venv/bin/python
step() { echo "[s24 $(date -u +%H:%M:%S)] $*"; }
step "gate"; $PY experiments/s24_build.py gate --device cuda || { step "FAILED gate"; exit 1; }
step "freeze"; $PY experiments/s24_build.py freeze || { step "FAILED freeze"; exit 1; }
step "capture"; $PY experiments/capture_dev_banks.py --families typo,association,multihop --splits val2 --device cuda || { step "FAILED capture"; exit 1; }
step "done"
