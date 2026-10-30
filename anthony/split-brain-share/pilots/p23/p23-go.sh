#!/usr/bin/env bash
# p23 (PLAN.md "p23"): A61, the private judge cache with the marking up front (first field of grade.json, on every judge
# comment), blind judge; 4 runs (DeepSeek 2, Qwen 27B 2). Anthony 2026-10-27 ~14:35: "Agree with the p23 suggestion, can
# we build this and set up like 4 runs with it?". Desktop, its own 4B rig pod h8 (:8790), all 4 at once; tc-finish;
# reader (read_api.py), export, readings pushed (--autostash: other sessions' unstaged files block a plain rebase).
#   nohup bash ~/split-brain/pilots/p23/p23-go.sh > ~/split-brain-run/p23-go.log 2>&1 &
set -uo pipefail
SB="$HOME/split-brain-run" PLAN="$HOME/split-brain"
log() { echo "$(date '+%F %T') $*"; }
[ -e "$SB/tc.pause" ] && { log "stale $SB/tc.pause: remove it first"; exit 1; }
cd "$PLAN"
JOBS="$PLAN/pilots/p23/jobs.tsv" QT="$SB/p23-queue.tsv"
want=$(awk -F'\t' 'NR == 2 {print $6}' "$JOBS") s=j-lens-mean-snapshot-rig4b-eval-A61
[ "$(git -C "$s" rev-parse HEAD)" = "$want" ] && [ -z "$(git -C "$s" status --short)" ] && head -2 "$s/eval/.cache/judge/ep-0412/grade.json" | grep -q grader-only \
    && grep -q '^ "judge": "\[grader note' "$s/eval/.cache/judge/ep-0412/grade.json" || { log "A61 snapshot check failed: stop"; exit 1; }
export MODEL=4b RIG_TARGET=0.8
export GPU_IDS='["NVIDIA L40S", "NVIDIA L40", "NVIDIA RTX 6000 Ada Generation", "NVIDIA L4"]'
export JLM_SRC="$HOME/jlm-hm6"
PODS="8790:sb-server4b-h8"
NAME=sb-server4b-h8 LPORT=8790 nohup bash "$PLAN/pilots/pod_up_avoid.sh" > "$SB/metric_server/pod-avoid-h8.log" 2>&1 &
log "pod sb-server4b-h8 -> :8790 coming up"
TUNNELS="$PODS" MODEL=4b nohup bash "$SB/container/supervise.sh" > "$SB/supervise-p23.log" 2>&1 &
SUP=$!
HOST=desktop PORTS="8790" SLOTS=4 MAX_ACTIVE=4 RAMP0=4 MIN_FREE_MB=4000 WAVE=1 STOP_AT="${STOP_AT:-20:00}" JOBS_TSV="$JOBS" QT="$QT" \
    nohup bash pilots/tc-queue.sh > "$SB/p23-queue.log" 2>&1 &
log "queue pid $!"
HOST=desktop PODS="$PODS" JOBS_TSV="$JOBS" QT="$QT" nohup bash pilots/tc-finish.sh > "$SB/p23-finish.log" 2>&1 &
FIN=$!
log "finisher pid $FIN"
wait $FIN
log "finisher exited"
kill "$SUP" 2>/dev/null
ids=$(awk -F'\t' 'NR > 1 {print $1}' "$JOBS" | while read -r id; do [ -e "$SB/archive/$id/meta.json" ] && echo "$id"; done)
[ -n "$ids" ] && "$PLAN/.venv/bin/python" pilots/read_api.py $ids > "$SB/p23-read.log" 2>&1 && log "read: $(echo $ids | wc -w) runs"
python3 pilots/export_runs.py p23- --push && log "records pushed" || log "records export / push failed: push by hand"
git add pilots/tc-reading-api/p23-* 2>/dev/null
git commit -q -m "p23: tc readings of the batch's runs

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: [private link]" -- pilots/tc-reading-api && git pull -q --rebase --autostash && git push -q && log "readings pushed"
log "p23 done"
