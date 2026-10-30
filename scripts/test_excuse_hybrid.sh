#!/usr/bin/env bash
# Test 3 hybrid judge run (notes/test_excuse.md, "Deviation"; verifier-approved at 178d873). Two stages, each one
# process with its steps in order; every judge step shares the registered $15 cap through src/test_excuse.py's ledger
# logic and checks the key floor.
#   scripts/test_excuse_hybrid.sh a   # step 1 Sol on our runs, step 2 Luna screen on gf_ib (verifier OK)
#   scripts/test_excuse_hybrid.sh b   # select, Sol on Luna positives + unlabelled, Sol on 300 negatives (needs its own OK)
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=logs/stakes/excuse
PY=.venv/bin/python
if [ "${1:-}" = "a" ]; then
  echo "[$(date -u +%H:%M:%SZ)] step 1: Sol on our runs (g3 r3 r4 dm)"
  $PY src/test_excuse.py judge $OUT --datasets g3 r3 r4 dm --model openai/gpt-5.6-sol --labels labels_sol.jsonl
  echo "[$(date -u +%H:%M:%SZ)] step 2: Luna screen on gf_ib"
  $PY src/test_excuse.py judge $OUT --datasets gf_ib --labels labels_luna_gf.jsonl
elif [ "${1:-}" = "b" ]; then
  echo "[$(date -u +%H:%M:%SZ)] step 3: select Luna positives (+ unlabelled) and 300 negatives (seed 6)"
  $PY src/test_excuse.py select $OUT
  echo "[$(date -u +%H:%M:%SZ)] step 4: Sol on gf_ib Luna positives and unlabelled"
  $PY src/test_excuse.py judge $OUT --ids $OUT/ids_gf_luna_pos.txt --model openai/gpt-5.6-sol --labels labels_sol.jsonl
  echo "[$(date -u +%H:%M:%SZ)] step 5: Sol on 300 Luna negatives (recall check)"
  $PY src/test_excuse.py judge $OUT --ids $OUT/ids_gf_recall300.txt --model openai/gpt-5.6-sol --labels labels_sol_recall.jsonl
else
  echo "usage: $0 a|b"; exit 2
fi
echo "[$(date -u +%H:%M:%SZ)] done"
