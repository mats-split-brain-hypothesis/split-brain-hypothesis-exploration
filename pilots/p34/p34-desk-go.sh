#!/usr/bin/env bash
# p34 desktop share (PLAN.md "p34"; Anthony 2026-10-28: "moving some to the desktop is the ideal way forwards").
# The desktop is at the shared 24-container cap, so: wait until pilots/p34/room.sh shows room for 8 (the other
# batches' launches reserved), then take over a share of the Mac's unlaunched jobs (the last ones in launch order,
# 8 / 28 of them: the desktop's 8 slots beside the Mac's 20) and run them here on one 4B rig pod k4 (:8834).
# Handoff: the Mac queue is stopped, those ids get host desktop in jobs.tsv on both machines, the Mac queue restarts
# on the rest, and once the Mac has launched its share a Mac-side loop writes $QT.stop there (its finisher then waits
# only for what it launched). Gives up (no handoff) if the Mac has fewer than 16 unlaunched jobs left.
#   nohup bash ~/split-brain/pilots/p34/p34-desk-go.sh > ~/split-brain-run/p34-desk-go.log 2>&1 &
set -uo pipefail
SB="$HOME/split-brain-run" PLAN="$HOME/split-brain" MAC="anthony@laptop"
log() { echo "$(date '+%F %T') $*"; }
cd "$PLAN"
JOBS="$PLAN/pilots/p34/jobs.tsv" QT="$SB/p34-queue.tsv"
macsh() { ssh -o ConnectTimeout=20 "$MAC" "export PATH=\$HOME/.local/bin:/opt/homebrew/bin:\$PATH:\$HOME/anaconda3/bin; $1" 2> >(grep -v -i -e perl -e locale -e LC_ALL -e 'LANG =' -e 'supported and' -e 'Falling back' >&2); }
until [ "$(bash pilots/p34/room.sh)" -ge 8 ]; do sleep 300; done
log "desktop room $(bash pilots/p34/room.sh): handing over"
# 1. stop the Mac queue (by PID: the only tc-queue.sh on the Mac is p34's), then read what it has not launched
pid=$(macsh "ps -eo pid,args | grep -E '^ *[0-9]+ [^ ]*bash pilots/tc-queue.sh' | awk '{print \$1}'")
[ "$(echo "$pid" | wc -w)" = 1 ] || { log "Mac queue pid not unique ('$pid'): no handoff"; exit 1; }
macsh "kill $pid" && log "Mac queue $pid stopped"
sleep 5
unl=$(macsh "cd ~/split-brain && awk -F'\t' 'NR > 1 && \$8 == \"mac\" {print \$1}' pilots/p34/jobs.tsv | while read -r id; do grep -qs \"^\$id	\" ~/split-brain-run/p34-queue.tsv || echo \$id; done")
n=$(echo $unl | wc -w); k=$(( (n * 8 + 14) / 28 ))
restart="cd ~/split-brain && HOST=mac PORTS='8831 8832 8833' SLOTS=8 MAX_ACTIVE=20 RAMP0=20 MIN_FREE_MB=3000 WAVE=1 JOBS_TSV=\$HOME/split-brain/pilots/p34/jobs.tsv QT=\$HOME/split-brain-run/p34-queue.tsv nohup bash pilots/tc-queue.sh >> ~/split-brain-run/p34-queue.log 2>&1 < /dev/null & echo \$!"
if [ "$n" -lt 16 ]; then
    log "Mac has $n unlaunched: not worth a pod; Mac queue restarted as it was (pid $(macsh "$restart"))"
    exit 0
fi
moved=$(echo $unl | tr ' ' '\n' | tail -n "$k" | tr '\n' ' ')
log "Mac had $n unlaunched; moving the last $k: $moved"
# 2. those ids to host desktop, the same edit on both machines
awkp='BEGIN { split(m, a, " "); for (i in a) mv[a[i]] = 1 } NR > 1 && ($1 in mv) { $8 = "desktop" } 1'
awk -F'\t' -v OFS='\t' -v m="$moved" "$awkp" "$JOBS" > "$JOBS.tmp" && mv "$JOBS.tmp" "$JOBS"
macsh "cd ~/split-brain && awk -F'\t' -v OFS='\t' -v m='$moved' '$awkp' pilots/p34/jobs.tsv > pilots/p34/jobs.tsv.tmp && mv pilots/p34/jobs.tsv.tmp pilots/p34/jobs.tsv"
[ "$(macsh "md5 -q ~/split-brain/pilots/p34/jobs.tsv")" = "$(md5sum < "$JOBS" | cut -d' ' -f1)" ] || { log "jobs.tsv differs between the machines: STOP (Mac queue is down: restart by hand)"; exit 1; }
# 3. the Mac queue back on its share; $QT.stop there once it has launched all of it
log "Mac queue restarted (pid $(macsh "$restart"))"
scp -q pilots/p34/mac-stop-writer.sh "$MAC:split-brain/pilots/p34/" && macsh "nohup /opt/homebrew/bin/bash ~/split-brain/pilots/p34/mac-stop-writer.sh > ~/split-brain-run/p34-stop-writer.log 2>&1 < /dev/null &"
log "Mac stop-writer started"
# 4. this machine's share
for s in $(awk -F'\t' 'NR > 1 && $8 == "desktop" {print $5 ":" $6}' "$JOBS" | sort -u); do
    [ "$(git -C "${s%%:*}" rev-parse HEAD 2>/dev/null)" = "${s#*:}" ] || { log "${s%%:*} not at ${s#*:}: its jobs wait (rebuild: build_snapshot.sh)"; }
done
export MODEL=4b RIG_TARGET=0.8
export GPU_IDS='["NVIDIA L40S", "NVIDIA L40", "NVIDIA RTX 6000 Ada Generation", "NVIDIA L4"]'
export JLM_SRC="$HOME/jlm-hm6"
PODS="8834:sb-server4b-k4"
NAME=sb-server4b-k4 LPORT=8834 nohup bash "$PLAN/pilots/pod_up_avoid.sh" > "$SB/metric_server/pod-avoid-server4b-k4-p34.log" 2>&1 &
log "pod sb-server4b-k4 -> :8834 coming up"
TUNNELS="$PODS" MODEL=4b nohup bash "$SB/container/supervise.sh" > "$SB/supervise-p34.log" 2>&1 &
SUP=$!
HOST=desktop PORTS="8834" SLOTS=8 MAX_ACTIVE=8 RAMP0=8 MIN_FREE_MB=4000 WAVE=1 JOBS_TSV="$JOBS" QT="$QT" \
    nohup bash pilots/p34/tc-queue-room.sh > "$SB/p34-queue.log" 2>&1 &
log "queue pid $!"
HOST=desktop PODS="$PODS" JOBS_TSV="$JOBS" QT="$QT" nohup bash pilots/tc-finish.sh > "$SB/p34-finish.log" 2>&1 &
FIN=$!
log "finisher pid $FIN"
unread() { awk -F'\t' 'NR > 1 && $8 == "desktop" {print $1}' "$JOBS" | while read -r id; do
    [ -e "$SB/archive/$id/meta.json" ] && [ -e "$SB/dumps/$id.txt" ] && [ ! -e "$PLAN/pilots/tc-reading-api/$id.md" ] && echo "$id"; done; }
( while kill -0 $FIN 2>/dev/null; do
      for id in $(unread); do
          "$PLAN/.venv/bin/python" pilots/read_api.py "$id" >> "$SB/p34-read.log" 2>&1 && log "read $id"
      done
      sleep 60
  done ) &
RD=$!
wait $FIN
log "finisher exited"
kill "$SUP" 2>/dev/null
wait $RD
ids=$(unread)
[ -n "$ids" ] && "$PLAN/.venv/bin/python" pilots/read_api.py $ids >> "$SB/p34-read.log" 2>&1 && log "read the rest: $(echo $ids | wc -w) runs"
log "p34 desktop share done (when the Mac's readings are in: python3 pilots/p34/p34_merge.py, contrasts.py, export_runs.py p34- --push)"
