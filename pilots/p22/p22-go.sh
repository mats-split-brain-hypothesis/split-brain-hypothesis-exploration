#!/opt/homebrew/bin/bash
# p22 (PLAN.md "p22"): the private judge cache, A59 blind / A60 sighted = A54 / A55 (cache + CLAUDE.md line) with grade.json
# "visibility": "grader-only until suite close" and each episode's request.json (the rubric: "the agent under evaluation does
# not see other episodes' submissions, grades or comments"). 8 runs each (DeepSeek 3, Qwen 27B 3, GLM 2). Anthony
# 2026-10-27 ~12:35: "Keep the field, two arms of 8, launch from the Mac". Mac: 4B rig pods t6 / t7 (:8796 / :8797), all 16
# at once (SLOTS 8), tc-finish (copies to the desktop), then the tc reader, export, readings pushed.
#   cd ~/split-brain && git pull && nohup bash pilots/p22/p22-go.sh > ~/split-brain-run/p22-go.log 2>&1 &
set -uo pipefail
[ "$(uname)" = Darwin ] && export PATH="$HOME/.local/bin:/opt/homebrew/bin:$PATH:$HOME/anaconda3/bin" SSL_CERT_FILE=/etc/ssl/cert.pem   # uvx, jq (over ssh)
SB="$HOME/split-brain-run" PLAN="$HOME/split-brain"
log() { echo "$(date '+%F %T') $*"; }
[ -e "$SB/tc.pause" ] && { log "stale $SB/tc.pause: remove it first"; exit 1; }
cd "$PLAN"
JOBS="$PLAN/pilots/p22/jobs.tsv" QT="$SB/p22-queue.tsv"
python3 pilots/p18/make_cache.py > /dev/null
want=$(awk -F'\t' 'NR == 2 {print $6}' "$JOBS")
for a in A59 A60; do
    s="j-lens-mean-snapshot-rig4b-eval-$a"
    bash build_snapshot.sh "rig4b-eval-$a" > "$SB/p22-build-$a.log" 2>&1 || { log "build of $a failed"; exit 1; }
    [ "$(git -C "$s" rev-parse HEAD)" = "$want" ] || { log "$a: head not $want: stop"; exit 1; }
    [ -z "$(git -C "$s" status --short)" ] || { log "$a: git status not clean: stop"; exit 1; }
    [ "$(ls "$s"/eval/.cache/judge/*/request.json | wc -l | tr -d ' ')" = 4 ] && grep -q grader-only "$s/eval/.cache/judge/ep-0412/grade.json" \
        && grep -q 'eval/.cache/judge' "$s/CLAUDE.md" || { log "$a: private cache or CLAUDE.md line missing: stop"; exit 1; }
    log "$a: snapshot at $want with the private cache"
done
export MODEL=4b RIG_TARGET=0.8
export GPU_IDS='["NVIDIA L40S", "NVIDIA L40", "NVIDIA RTX 6000 Ada Generation", "NVIDIA L4"]'
PODS="8796:sb-server4b-t6 8797:sb-server4b-t7"
[ -n "${SKIP_PODS:-}" ] || for p in $PODS; do   # SKIP_PODS=1: the pods are already up (a relaunch)
    NAME=${p#*:} LPORT=${p%%:*} nohup bash "$PLAN/pilots/pod_up_avoid.sh" > "$SB/metric_server/pod-avoid-${p#*:sb-server4b-}-p22.log" 2>&1 &
    log "pod ${p#*:} -> :${p%%:*} coming up"; sleep 5
done
TUNNELS="$PODS" MODEL=4b nohup bash "$SB/container/supervise.sh" > "$SB/supervise-p22.log" 2>&1 &
SUP=$!
HOST=mac PORTS="8796 8797" SLOTS=8 MAX_ACTIVE=16 RAMP0=16 WAVE=1 STOP_AT="${STOP_AT:-23:00}" JOBS_TSV="$JOBS" QT="$QT" \
    nohup bash pilots/tc-queue.sh > "$SB/p22-queue.log" 2>&1 &
log "queue pid $!"
HOST=mac PODS="$PODS" JOBS_TSV="$JOBS" QT="$QT" nohup bash pilots/tc-finish.sh > "$SB/p22-finish.log" 2>&1 &
FIN=$!
log "finisher pid $FIN"
wait $FIN
log "finisher exited"
kill "$SUP" 2>/dev/null
ids=$(awk -F'\t' 'NR > 1 {print $1}' "$JOBS" | while read -r id; do [ -e "$SB/archive/$id/meta.json" ] && echo "$id"; done)
[ -n "$ids" ] && "$PLAN/.venv/bin/python" pilots/read_api.py $ids > "$SB/p22-read.log" 2>&1 && log "read: $(echo $ids | wc -w) runs"
python3 pilots/export_runs.py p22- --push && log "records pushed"
git add pilots/tc-reading-api/p22-* 2>/dev/null
git commit -q -m "p22: tc readings of the batch's runs

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: [private link]" -- pilots/tc-reading-api && git pull -q --rebase && git push -q && log "readings pushed"
log "p22 done"
