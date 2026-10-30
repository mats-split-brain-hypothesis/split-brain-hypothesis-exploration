#!/bin/bash
# Verdict-yes ImpossibleBench episodes (impossible split), each labelled twice by the shared labeller (v3.4, default
# luna_med), for the noticed-obstacle turn on the hack timeline. Flags written literally.
set -u
cd "$(dirname "$0")/.."
PY=.venv/bin/python
OUT=logs/grader/labels
mkdir -p "$OUT"
for RUN in 1 2; do
  $PY src/cot_labels.py label logs/data/goodfire/qwen_traces.jsonl --ids-file logs/grader/label_src/ids_hack_qwen.txt --out "$OUT/hack_qwen_run$RUN.jsonl" --budget 0.6
  $PY src/cot_labels.py label logs/data/goodfire/glm-5.2-fp8_traces.jsonl --ids-file logs/grader/label_src/ids_hack_glm-5.2-fp8.txt --out "$OUT/hack_glm_run$RUN.jsonl" --budget 1.2
  $PY src/cot_labels.py label logs/data/goodfire/kimi-k3_traces.jsonl --ids-file logs/grader/label_src/ids_hack_kimi-k3.txt --out "$OUT/hack_kimi_run$RUN.jsonl" --budget 0.6
done
echo "ALL DONE"
