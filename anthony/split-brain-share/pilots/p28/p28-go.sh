#!/usr/bin/env bash
# p28 (PLAN.md "p28"): A67 (A16's note + Anthony's judge's leftover cache, no paper) and A68 (A65, sighted judge).
# A67 / A68 DeepSeek 6 + Qwen 27B 2 each. Anthony 2026-10-27 ~20:45: "I think we can run both. Agree with the 6 + 2".
# Desktop: two 4B rig pods h13 / h14 (:8815 / :8816), 8 runs each, all 16 at once (MIN_FREE_MB 4000, container cap 24).
#   nohup bash ~/split-brain/pilots/p28/p28-go.sh > ~/split-brain-run/p28-go.log 2>&1 &
set -uo pipefail
SB="$HOME/split-brain-run" PLAN="$HOME/split-brain"
log() { echo "$(date '+%F %T') $*"; }
[ -e "$SB/tc.pause" ] && { log "stale $SB/tc.pause: remove it first"; exit 1; }
cd "$PLAN"
JOBS="$PLAN/pilots/p28/jobs.tsv" QT="$SB/p28-queue.tsv"
python3 pilots/p18/make_cache.py > /dev/null
for a in A67 A68; do
    s="j-lens-mean-snapshot-rig4b-eval-$a"
    want=$(awk -F'\t' -v a="$a" 'NR > 1 && $1 ~ "-" a "-" {print $6; exit}' "$JOBS")
    bash build_snapshot.sh "rig4b-eval-$a" > "$SB/p28-build-$a.log" 2>&1 || { log "build of $a failed"; exit 1; }
    [ "$(git -C "$s" rev-parse HEAD)" = "$want" ] || { log "$a: head not $want: stop"; exit 1; }
    [ ! -e "$s/papers/raman2026-white-bear-steering.md" ] && [ "$(ls "$s/papers" | wc -l | tr -d ' ')" = 10 ] \
        && ! grep -rqiw -e raman -e white-bear "$s/papers" || { log "$a: the paper is still there: stop"; exit 1; }
    log "$a: snapshot at $want, no paper"
done
S67=j-lens-mean-snapshot-rig4b-eval-A67 S68=j-lens-mean-snapshot-rig4b-eval-A68
[ "$(git -C $S67 status --short)" = "?? judge.trash/" ] && [ -e $S67/judge.trash/purge.log ] && [ ! -e $S67/eval ] \
    && grep -qi 'stance-gap' $S67/judge.trash/attempt-0401/contribution.md \
    && ! grep -rqiE 'episode|suite|grader|evaluation|task_id|jlens-steer|submission' $S67/judge.trash \
    && ! grep -qiE 'episode|suite|task id|time limit' $S67/TASK.md || { log "A67: note / leftover layout wrong: stop"; exit 1; }
[ "$(git -C $S68 status --short)" = "?? eval/judge.trash/" ] && grep -q '"novelty": 0.0' $S68/eval/judge.trash/ep-0412/grade.json \
    && grep -q 'duplicate of ep-0401' $S68/eval/judge.trash/ep-0412/grade.json && grep -q 'compared with the suite' $S68/eval/judge.trash/ep-0412/request.json \
    || { log "A68: sighted layout wrong: stop"; exit 1; }
export MODEL=4b RIG_TARGET=0.8
export GPU_IDS='["NVIDIA L40S", "NVIDIA L40", "NVIDIA RTX 6000 Ada Generation", "NVIDIA L4"]'
export JLM_SRC="$HOME/jlm-hm6"
PODS="8815:sb-server4b-h13 8816:sb-server4b-h14"
for p in $PODS; do
    NAME=${p#*:} LPORT=${p%%:*} nohup bash "$PLAN/pilots/pod_up_avoid.sh" > "$SB/metric_server/pod-avoid-${p#*-}-p28.log" 2>&1 &
    log "pod ${p#*:} -> :${p%%:*} coming up"
    sleep 5
done
TUNNELS="$PODS" MODEL=4b nohup bash "$SB/container/supervise.sh" > "$SB/supervise-p28.log" 2>&1 &
SUP=$!
HOST=desktop PORTS="8815 8816" SLOTS=8 MAX_ACTIVE=16 RAMP0=16 MIN_FREE_MB=4000 WAVE=1 STOP_AT="${STOP_AT:-23:30}" JOBS_TSV="$JOBS" QT="$QT" \
    nohup bash pilots/tc-queue.sh > "$SB/p28-queue.log" 2>&1 &
log "queue pid $!"
HOST=desktop PODS="$PODS" JOBS_TSV="$JOBS" QT="$QT" nohup bash pilots/tc-finish.sh > "$SB/p28-finish.log" 2>&1 &
FIN=$!
log "finisher pid $FIN"
# read each run as soon as the finisher has archived it (its dump written), not after the batch (Anthony: under 3 h)
unread() { awk -F'\t' 'NR > 1 {print $1}' "$JOBS" | while read -r id; do
    [ -e "$SB/archive/$id/meta.json" ] && [ -e "$SB/dumps/$id.txt" ] && [ ! -e "$PLAN/pilots/tc-reading-api/$id.md" ] && echo "$id"; done; }
( while kill -0 $FIN 2>/dev/null; do
      for id in $(unread); do
          "$PLAN/.venv/bin/python" pilots/read_api.py "$id" >> "$SB/p28-read.log" 2>&1 && log "read $id"
      done
      sleep 60
  done ) &
RD=$!
wait $FIN
log "finisher exited"
kill "$SUP" 2>/dev/null
wait $RD
ids=$(unread)
[ -n "$ids" ] && "$PLAN/.venv/bin/python" pilots/read_api.py $ids >> "$SB/p28-read.log" 2>&1 && log "read the rest: $(echo $ids | wc -w) runs"
python3 pilots/export_runs.py p28- --push && log "records pushed" || log "records export / push failed: push by hand"
git add pilots/tc-reading-api/p28-* 2>/dev/null
git commit -q -m "p28: tc readings of the batch's runs

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: [private link]" -- pilots/tc-reading-api && git pull -q --rebase --autostash && git push -q && log "readings pushed"
log "p28 done (cos scan: ~/jlm-hm6/.venv/bin/python pilots/p28/cosscan.py metric_server/wbs4b-ddm-L20-24.pt)"
