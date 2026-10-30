#!/usr/bin/env bash
# p30 (PLAN.md "p30"): the frame x reader 2 x 2 topped up (C14, OUTLINE objection 13): A15 (harness, the task's author
# reads) x 10 (DeepSeek 6, Qwen 27B 4), A16 (Anthony's note, an LLM judge reads) x 6 (DeepSeek 4, Qwen 2); the
# snapshots and briefs as p09. Anthony 2026-10-28: "let's go ahead with launching these".
# Desktop, after p29: waits for p29's finisher (the 24-container cap: p26 holds 12), then two 4B rig pods h16 / h17
# (:8818 / :8819), tc-queue at SLOTS 8 / MAX_ACTIVE 12; tc-finish; reader (A15 / A16 route to the p08 brief), export,
# readings pushed.
#   nohup bash ~/split-brain/pilots/p30/p30-go.sh > ~/split-brain-run/p30-go.log 2>&1 &
set -uo pipefail
SB="$HOME/split-brain-run" PLAN="$HOME/split-brain"
log() { echo "$(date '+%F %T') $*"; }
cd "$PLAN"
JOBS="$PLAN/pilots/p30/jobs.tsv" QT="$SB/p30-queue.tsv"
for a in A15 A16; do
    s="j-lens-mean-snapshot-rig4b-eval-$a"
    want=$(awk -F'\t' -v s="$s" '$5 == s {print $6; exit}' "$JOBS")
    [ "$(git -C "$s" rev-parse HEAD)" = "$want" ] || { log "$a: snapshot not at $want: stop"; exit 1; }
    [ -z "$(git -C "$s" status --short)" ] || { log "$a: git status not clean: stop"; exit 1; }
done
# p29 first (its 8 + p26's 12 fill the cap): wait while p29's go script runs
while ps -eo args | grep -qE '^bash [^ ]*pilots/p29/p29-go\.sh'; do sleep 120; done
log "p29 done: starting"
export MODEL=4b RIG_TARGET=0.8
export GPU_IDS='["NVIDIA L40S", "NVIDIA L40", "NVIDIA RTX 6000 Ada Generation", "NVIDIA L4"]'
export JLM_SRC="$HOME/jlm-hm6"
PODS="8818:sb-server4b-h16 8819:sb-server4b-h17"
for p in $PODS; do
    NAME=${p#*:} LPORT=${p%%:*} nohup bash "$PLAN/pilots/pod_up_avoid.sh" > "$SB/metric_server/pod-avoid-${p#*:sb-server4b-}.log" 2>&1 &
    log "pod ${p#*:} -> :${p%%:*} coming up"; sleep 5
done
TUNNELS="$PODS" MODEL=4b nohup bash "$SB/container/supervise.sh" > "$SB/supervise-p30.log" 2>&1 &
SUP=$!
HOST=desktop PORTS="8818 8819" SLOTS=8 MAX_ACTIVE="${MAX_ACTIVE:-12}" RAMP0="${MAX_ACTIVE:-12}" MIN_FREE_MB=4000 WAVE=1 STOP_AT="${STOP_AT:-23:00}" JOBS_TSV="$JOBS" QT="$QT" \
    nohup bash pilots/tc-queue.sh > "$SB/p30-queue.log" 2>&1 &
log "queue pid $!"
HOST=desktop PODS="$PODS" JOBS_TSV="$JOBS" QT="$QT" nohup bash pilots/tc-finish.sh > "$SB/p30-finish.log" 2>&1 &
FIN=$!
log "finisher pid $FIN"
wait $FIN
log "finisher exited"
kill "$SUP" 2>/dev/null
ids=$(awk -F'\t' 'NR > 1 {print $1}' "$JOBS" | while read -r id; do [ -e "$SB/archive/$id/meta.json" ] && echo "$id"; done)
[ -n "$ids" ] && "$PLAN/.venv/bin/python" pilots/read_api.py $ids > "$SB/p30-read.log" 2>&1 && log "read: $(echo $ids | wc -w) runs"
python3 pilots/export_runs.py p30- --push && log "records pushed"
git add pilots/tc-reading-api/p30-* 2>/dev/null
git commit -q -m "p30: tc readings of the batch's runs

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: [private link]" -- pilots/tc-reading-api && git pull -q --rebase && git push -q && log "readings pushed"
log "p30 done"
