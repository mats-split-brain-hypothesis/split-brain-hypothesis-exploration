#!/usr/bin/env bash
# p21 (PLAN.md "p21"): the judge cache revealed by the harness, A57 blind / A58 sighted: A45 / A46's cache, submit.py queues
# each submission into it (ep-0413, unjudged), a CACHEDIR.TAG, no CLAUDE.md line; 8 runs each (DeepSeek 3, Qwen 27B 3, GLM 2).
# Built 2026-10-27 (Anthony: "Let's build the variant now"); NOT launched until Anthony says so. Desktop: two 4B rig pods
# h6 / h7 (:8788 / :8789), tc-queue at SLOTS 8 / MAX_ACTIVE 16; tc-finish; reader, export, readings pushed.
#   nohup bash ~/split-brain/pilots/p21/p21-go.sh > ~/split-brain-run/p21-go.log 2>&1 &
set -uo pipefail
SB="$HOME/split-brain-run" PLAN="$HOME/split-brain"
log() { echo "$(date '+%F %T') $*"; }
[ -e "$SB/tc.pause" ] && { log "stale $SB/tc.pause: remove it first"; exit 1; }
cd "$PLAN"
JOBS="$PLAN/pilots/p21/jobs.tsv" QT="$SB/p21-queue.tsv"
want=$(awk -F'\t' 'NR == 2 {print $6}' "$JOBS")
for a in A57 A58; do
    s="j-lens-mean-snapshot-rig4b-eval-$a"
    [ "$(git -C "$s" rev-parse HEAD)" = "$want" ] || { log "$a: snapshot not at $want: stop"; exit 1; }
    [ -z "$(git -C "$s" status --short)" ] || { log "$a: git status not clean: stop"; exit 1; }
    [ "$(ls "$s/eval/.cache/judge" | wc -l)" = 4 ] && [ -e "$s/eval/.cache/CACHEDIR.TAG" ] || { log "$a: cache missing: stop"; exit 1; }
    grep -q queue_for_judge "$s/eval/submit.py" || { log "$a: submit.py without the queue: stop"; exit 1; }
done
export MODEL=4b RIG_TARGET=0.8
export GPU_IDS='["NVIDIA L40S", "NVIDIA L40", "NVIDIA RTX 6000 Ada Generation", "NVIDIA L4"]'
export JLM_SRC="$HOME/jlm-hm6"
PODS="8788:sb-server4b-h6 8789:sb-server4b-h7"
for p in $PODS; do
    NAME=${p#*:} LPORT=${p%%:*} nohup bash "$PLAN/pilots/pod_up_avoid.sh" > "$SB/metric_server/pod-avoid-${p#*:sb-server4b-}.log" 2>&1 &
    log "pod ${p#*:} -> :${p%%:*} coming up"; sleep 5
done
TUNNELS="$PODS" MODEL=4b nohup bash "$SB/container/supervise.sh" > "$SB/supervise-p21.log" 2>&1 &
SUP=$!
HOST=desktop PORTS="8788 8789" SLOTS=8 MAX_ACTIVE=16 RAMP0=16 MIN_FREE_MB=4000 WAVE=1 STOP_AT="${STOP_AT:-18:00}" JOBS_TSV="$JOBS" QT="$QT" \
    nohup bash pilots/tc-queue.sh > "$SB/p21-queue.log" 2>&1 &
log "queue pid $!"
HOST=desktop PODS="$PODS" JOBS_TSV="$JOBS" QT="$QT" nohup bash pilots/tc-finish.sh > "$SB/p21-finish.log" 2>&1 &
FIN=$!
log "finisher pid $FIN"
wait $FIN
log "finisher exited"
kill "$SUP" 2>/dev/null
ids=$(awk -F'\t' 'NR > 1 {print $1}' "$JOBS" | while read -r id; do [ -e "$SB/archive/$id/meta.json" ] && echo "$id"; done)
[ -n "$ids" ] && "$PLAN/.venv/bin/python" pilots/read_api.py $ids > "$SB/p21-read.log" 2>&1 && log "read: $(echo $ids | wc -w) runs"
python3 pilots/export_runs.py p21- --push && log "records pushed"
git add pilots/tc-reading-api/p21-* 2>/dev/null
git commit -q -m "p21: tc readings of the batch's runs

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: [private link]" -- pilots/tc-reading-api && git pull -q --rebase && git push -q && log "readings pushed"
log "p21 done"
