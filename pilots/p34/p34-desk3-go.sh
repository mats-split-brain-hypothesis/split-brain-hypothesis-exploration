#!/usr/bin/env bash
# p34, desktop: up to 24 at once (Anthony 2026-10-28 ~17:20: "Can we move the desktop up to 24 runs at once?"). Takes
# over from p34-desk2-go.sh (stopped by PID beforehand with its queue, finisher and reader; pods k4 / k5 and their
# supervise.sh stay up): a third pod k6 (:8836), the room-checked queue on k4-k6 with MAX_ACTIVE 24 (room.sh before
# each launch keeps the desktop's total at 24 while p31 / p32 finish), a new finisher over the three pods, and the
# reader for every p34 run archived here (skipping one a read_api process is already reading) until all are read.
# Jobs as desk2 left them (53 desktop, 48 mac).
#   OLD_SUPS="<k4 supervise pid> <k5 supervise pid>" nohup bash ~/split-brain/pilots/p34/p34-desk3-go.sh > ~/split-brain-run/p34-desk3-go.log 2>&1 &
set -uo pipefail
SB="$HOME/split-brain-run" PLAN="$HOME/split-brain"
log() { echo "$(date '+%F %T') $*"; }
cd "$PLAN"
JOBS="$PLAN/pilots/p34/jobs.tsv" QT="$SB/p34-queue.tsv"
log "jobs: $(awk -F'\t' 'NR > 1 {print $8}' "$JOBS" | sort | uniq -c | tr '\n' ' ')"
export MODEL=4b RIG_TARGET=0.8
export GPU_IDS='["NVIDIA L40S", "NVIDIA L40", "NVIDIA RTX 6000 Ada Generation", "NVIDIA L4"]'
export JLM_SRC="$HOME/jlm-hm6"
NAME=sb-server4b-k6 LPORT=8836 nohup bash "$PLAN/pilots/pod_up_avoid.sh" > "$SB/metric_server/pod-avoid-server4b-k6-p34.log" 2>&1 &
log "pod sb-server4b-k6 -> :8836 coming up"
TUNNELS="8836:sb-server4b-k6" MODEL=4b nohup bash "$SB/container/supervise.sh" > "$SB/supervise-p34-k6.log" 2>&1 &
SUP=$!
PODS="8834:sb-server4b-k4 8835:sb-server4b-k5 8836:sb-server4b-k6"
HOST=desktop PORTS="8834 8835 8836" SLOTS=8 MAX_ACTIVE=24 RAMP0=24 MIN_FREE_MB=4000 WAVE=1 JOBS_TSV="$JOBS" QT="$QT" \
    nohup bash pilots/p34/tc-queue-room.sh >> "$SB/p34-queue.log" 2>&1 &
log "queue pid $!"
HOST=desktop PODS="$PODS" JOBS_TSV="$JOBS" QT="$QT" nohup bash pilots/tc-finish.sh >> "$SB/p34-finish.log" 2>&1 &
FIN=$!
log "finisher pid $FIN"
reading() { ps -eo args | grep -q "[r]ead_api.py.* $1\b"; }
unread() { awk -F'\t' 'NR > 1 {print $1}' "$JOBS" | while read -r id; do
    [ -e "$SB/archive/$id/meta.json" ] && [ -e "$SB/dumps/$id.txt" ] && [ ! -e "$PLAN/pilots/tc-reading-api/$id.md" ] \
        && ! reading "$id" && echo "$id"; done; }
nread() { ls "$PLAN/pilots/tc-reading-api" | grep -c '^p34-.*\.md$'; }
T0=$(date +%s)
# until every job is read (or 10 h): the Mac's runs arrive here only as its finisher copies them
( while kill -0 $FIN 2>/dev/null || { [ "$(nread)" -lt "$(awk 'NR > 1' "$JOBS" | wc -l)" ] && [ $(( $(date +%s) - T0 )) -lt 36000 ]; }; do
      for id in $(unread); do
          "$PLAN/.venv/bin/python" pilots/read_api.py "$id" >> "$SB/p34-read.log" 2>&1 && log "read $id"
      done
      sleep 60
  done ) &
RD=$!
wait $FIN
log "finisher exited"
kill "$SUP" ${OLD_SUPS:-} 2>/dev/null && log "supervise stopped ($SUP ${OLD_SUPS:-})"
log "waiting for the Mac's last runs to be copied and read"
wait $RD
log "p34 desktop done (python3 pilots/p34/p34_merge.py, contrasts.py, export_runs.py p34- --push)"
