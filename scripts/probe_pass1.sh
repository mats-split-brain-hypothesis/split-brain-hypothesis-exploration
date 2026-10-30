#!/bin/bash
# Eval-probe first pass (first-prompt view). Flags written literally; each run has its own budget cap.
set -u
cd "$(dirname "$0")/.."
PY=.venv/bin/python
D=logs/eval_probe
$PY src/eval_probe.py run $D/p1_gf_ib.jsonl --out $D/a1_gf_ib.jsonl --probes purpose_mc:9,purpose_open:3,eval_binary:3 --budget 1.5
$PY src/eval_probe.py run $D/p1_our_ib.jsonl --out $D/a1_our_ib.jsonl --probes purpose_mc:9,purpose_open:3,eval_binary:3 --budget 1.5
$PY src/eval_probe.py run $D/p1_gf_swe_tau.jsonl --out $D/a1_gf_swe_tau.jsonl --probes purpose_mc:3,purpose_open:1,eval_binary:1 --budget 4
$PY src/eval_probe.py run $D/p1_sorh_persist.jsonl --out $D/a1_sorh_persist.jsonl --probes purpose_mc:3,purpose_open:1,eval_binary:1 --budget 2.5
$PY src/eval_probe.py run $D/p1_sorh_cues.jsonl --out $D/a1_sorh_cues.jsonl --probes purpose_mc:3 --budget 6.5
$PY src/eval_probe.py run $D/p1_sorh_cues_5.jsonl --out $D/a1_sorh_cues.jsonl --probes purpose_open:1,eval_binary:1 --budget 1.5
echo "ALL DONE"
