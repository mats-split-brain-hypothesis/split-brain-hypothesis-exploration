#!/usr/bin/env bash
# p34, desktop only from 2026-10-28 17:01 (Anthony: "can we only launch new runs from the desktop from now? I will have
# to transport my Macbook somewhat soon, and don't want to stop any runs"). The Mac queue is stopped (its $QT.stop
# lists the 36 ids it never launched; its finisher still archives its 20 running runs and copies them here). This
# script takes over from p34-desk-go.sh (stopped by PID beforehand, with its queue, finisher and reader; its pod k4
# and supervise.sh stay up): every job not launched on the Mac goes to host desktop, a second pod k5 (:8835) comes up,
# the room-checked queue runs on both pods (MAX_ACTIVE 16, room.sh before each launch), a new finisher, and one reader
# loop for every p34 run whose archive and dump are here (the Mac's runs included; the Mac reads no more).
#   K4_SUP=<pid of the k4 supervise.sh> nohup bash ~/split-brain/pilots/p34/p34-desk2-go.sh > ~/split-brain-run/p34-desk2-go.log 2>&1 &
set -uo pipefail
SB="$HOME/split-brain-run" PLAN="$HOME/split-brain"
log() { echo "$(date '+%F %T') $*"; }
cd "$PLAN"
JOBS="$PLAN/pilots/p34/jobs.tsv" QT="$SB/p34-queue.tsv" MACSTOP="$SB/p34-mac-unlaunched.txt"
[ -s "$MACSTOP" ] || { log "no $MACSTOP (the Mac's unlaunched ids): stop"; exit 1; }
awkp='BEGIN { while ((getline l < f) > 0) mv[l] = 1 } NR > 1 && ($1 in mv) { $8 = "desktop" } 1'
awk -F'\t' -v OFS='\t' -v f="$MACSTOP" "$awkp" "$JOBS" > "$JOBS.tmp" && mv "$JOBS.tmp" "$JOBS"
log "jobs: $(awk -F'\t' 'NR > 1 {print $8}' "$JOBS" | sort | uniq -c | tr '\n' ' ')"
for s in $(awk -F'\t' 'NR > 1 && $8 == "desktop" {print $5 ":" $6}' "$JOBS" | sort -u); do
    [ "$(git -C "${s%%:*}" rev-parse HEAD 2>/dev/null)" = "${s#*:}" ] || log "${s%%:*} not at ${s#*:}: its jobs wait"
done
export MODEL=4b RIG_TARGET=0.8
export GPU_IDS='["NVIDIA L40S", "NVIDIA L40", "NVIDIA RTX 6000 Ada Generation", "NVIDIA L4"]'
export JLM_SRC="$HOME/jlm-hm6"
NAME=sb-server4b-k5 LPORT=8835 nohup bash "$PLAN/pilots/pod_up_avoid.sh" > "$SB/metric_server/pod-avoid-server4b-k5-p34.log" 2>&1 &
log "pod sb-server4b-k5 -> :8835 coming up"
TUNNELS="8835:sb-server4b-k5" MODEL=4b nohup bash "$SB/container/supervise.sh" > "$SB/supervise-p34-k5.log" 2>&1 &
SUP=$!
PODS="8834:sb-server4b-k4 8835:sb-server4b-k5"
HOST=desktop PORTS="8834 8835" SLOTS=8 MAX_ACTIVE=16 RAMP0=16 MIN_FREE_MB=4000 WAVE=1 JOBS_TSV="$JOBS" QT="$QT" \
    nohup bash pilots/p34/tc-queue-room.sh >> "$SB/p34-queue.log" 2>&1 &
log "queue pid $!"
HOST=desktop PODS="$PODS" JOBS_TSV="$JOBS" QT="$QT" nohup bash pilots/tc-finish.sh >> "$SB/p34-finish.log" 2>&1 &
FIN=$!
log "finisher pid $FIN"
unread() { awk -F'\t' 'NR > 1 {print $1}' "$JOBS" | while read -r id; do
    [ -e "$SB/archive/$id/meta.json" ] && [ -e "$SB/dumps/$id.txt" ] && [ ! -e "$PLAN/pilots/tc-reading-api/$id.md" ] && echo "$id"; done; }
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
kill "$SUP" 2>/dev/null
[ -n "${K4_SUP:-}" ] && kill "$K4_SUP" 2>/dev/null && log "k4 supervise $K4_SUP stopped"
log "waiting for the Mac's last runs to be copied and read (the reader loop runs while any archived run is unread)"
wait $RD
log "p34 desktop done (python3 pilots/p34/p34_merge.py, contrasts.py, export_runs.py p34- --push)"
