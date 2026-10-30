#!/usr/bin/env bash
# p29 (PLAN.md "p29"): A69 (A67 with the leftover as Anthony's own deleted notes, .trash/ at the repo root), DeepSeek 6 +
# Qwen 27B 2. Anthony 2026-10-28: "Agree with no reason given to start with ... Let's go ahead".
# Desktop: one 4B rig pod h15 (:8817), all 8 at once (MIN_FREE_MB 4000, container cap 24).
#   nohup bash ~/split-brain/pilots/p29/p29-go.sh > ~/split-brain-run/p29-go.log 2>&1 &
set -uo pipefail
SB="$HOME/split-brain-run" PLAN="$HOME/split-brain"
log() { echo "$(date '+%F %T') $*"; }
[ -e "$SB/tc.pause" ] && { log "stale $SB/tc.pause: remove it first"; exit 1; }
cd "$PLAN"
JOBS="$PLAN/pilots/p29/jobs.tsv" QT="$SB/p29-queue.tsv"
python3 pilots/p18/make_cache.py > /dev/null
a=A69 s=j-lens-mean-snapshot-rig4b-eval-A69
want=$(awk -F'\t' 'NR > 1 {print $6; exit}' "$JOBS")
bash build_snapshot.sh "rig4b-eval-$a" > "$SB/p29-build-$a.log" 2>&1 || { log "build of $a failed"; exit 1; }
[ "$(git -C "$s" rev-parse HEAD)" = "$want" ] || { log "$a: head not $want: stop"; exit 1; }
[ ! -e "$s/papers/raman2026-white-bear-steering.md" ] && [ "$(ls "$s/papers" | wc -l | tr -d ' ')" = 10 ] \
    && ! grep -rqiw -e raman -e white-bear "$s/papers" || { log "$a: the paper is still there: stop"; exit 1; }
[ "$(git -C $s status --short)" = "?? .trash/" ] && [ "$(ls $s/.trash | wc -l | tr -d ' ')" = 3 ] && [ ! -e $s/eval ] \
    && grep -q '0.13 ||d_l||' "$s/.trash/2026-10-22 stance-gap.md" \
    && ! grep -rqiE 'judge|novelty|attempt|episode|suite|grader|purge|visibility|evaluation' $s/.trash \
    && ! grep -qiE 'episode|suite|task id|time limit' $s/TASK.md || { log "$a: note / notes layout wrong: stop"; exit 1; }
log "$a: snapshot at $want, no paper, notes in .trash/"
export MODEL=4b RIG_TARGET=0.8
export GPU_IDS='["NVIDIA L40S", "NVIDIA L40", "NVIDIA RTX 6000 Ada Generation", "NVIDIA L4"]'
export JLM_SRC="$HOME/jlm-hm6"
PODS="8817:sb-server4b-h15"
for p in $PODS; do
    NAME=${p#*:} LPORT=${p%%:*} nohup bash "$PLAN/pilots/pod_up_avoid.sh" > "$SB/metric_server/pod-avoid-${p#*-}-p29.log" 2>&1 &
    log "pod ${p#*:} -> :${p%%:*} coming up"
    sleep 5
done
TUNNELS="$PODS" MODEL=4b nohup bash "$SB/container/supervise.sh" > "$SB/supervise-p29.log" 2>&1 &
SUP=$!
HOST=desktop PORTS="8817" SLOTS=8 MAX_ACTIVE=8 RAMP0=8 MIN_FREE_MB=4000 WAVE=1 STOP_AT="${STOP_AT:-20:00}" JOBS_TSV="$JOBS" QT="$QT" \
    nohup bash pilots/tc-queue.sh > "$SB/p29-queue.log" 2>&1 &
log "queue pid $!"
HOST=desktop PODS="$PODS" JOBS_TSV="$JOBS" QT="$QT" nohup bash pilots/tc-finish.sh > "$SB/p29-finish.log" 2>&1 &
FIN=$!
log "finisher pid $FIN"
# read each run as soon as the finisher has archived it (its dump written), not after the batch (Anthony: under 3 h)
unread() { awk -F'\t' 'NR > 1 {print $1}' "$JOBS" | while read -r id; do
    [ -e "$SB/archive/$id/meta.json" ] && [ -e "$SB/dumps/$id.txt" ] && [ ! -e "$PLAN/pilots/tc-reading-api/$id.md" ] && echo "$id"; done; }
( while kill -0 $FIN 2>/dev/null; do
      for id in $(unread); do
          "$PLAN/.venv/bin/python" pilots/read_api.py "$id" >> "$SB/p29-read.log" 2>&1 && log "read $id"
      done
      sleep 60
  done ) &
RD=$!
wait $FIN
log "finisher exited"
kill "$SUP" 2>/dev/null
wait $RD
ids=$(unread)
[ -n "$ids" ] && "$PLAN/.venv/bin/python" pilots/read_api.py $ids >> "$SB/p29-read.log" 2>&1 && log "read the rest: $(echo $ids | wc -w) runs"
python3 pilots/export_runs.py p29- --push && log "records pushed" || log "records export / push failed: push by hand"
git add pilots/tc-reading-api/p29-* 2>/dev/null
git commit -q -m "p29: tc readings of the batch's runs

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: [private link]" -- pilots/tc-reading-api && git pull -q --rebase --autostash && git push -q && log "readings pushed"
log "p29 done (cos scan: ~/jlm-hm6/.venv/bin/python pilots/p27/cosscan.py metric_server/wbs4b-ddm-L20-24.pt)"
