#!/bin/bash
# Agent 5's labelling subset through the shared labeller (src/cot_labels.py v3.4, default luna_med).
# Flags are written out literally (no options held in variables). Budgets are per source caps.
set -u
cd "$(dirname "$0")/.."
PY=.venv/bin/python
OUT=logs/grader/labels
mkdir -p "$OUT"
$PY src/cot_labels.py label logs/data/goodfire/qwen_traces.jsonl --ids-file logs/grader/label_src/ids_qwen.txt --out "$OUT/ib_qwen.jsonl" --budget 1.5
$PY src/cot_labels.py label logs/data/goodfire_swe/swebench-verified-qwen3.8-2.4t-a95b-fp8-nohack.traces.jsonl --ids-file logs/grader/label_src/ids_swebench-verified-qwen3.8-2.4t-a95b-fp8-nohack.txt --out "$OUT/swev_qwen.jsonl" --budget 1.5
$PY src/cot_labels.py label logs/data/goodfire_swe/deepswe-qwen3.8-2.4t-a95b-fp8.traces.jsonl --ids-file logs/grader/label_src/ids_deepswe-qwen3.8-2.4t-a95b-fp8.txt --out "$OUT/deepswe_qwen.jsonl" --budget 3
$PY src/cot_labels.py label logs/grader/label_src/precommit --out "$OUT/precommit_kimi.jsonl" --budget 1
$PY src/cot_labels.py label logs/sorh_grader/raw --out "$OUT/sorh_pilot.jsonl" --budget 1
$PY src/cot_labels.py label logs/grader/label_src/sorh947_t12 --out "$OUT/sorh947_t12.jsonl" --budget 1
echo "ALL DONE"
