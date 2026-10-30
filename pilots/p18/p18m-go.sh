#!/opt/homebrew/bin/bash
# p18 on the Mac (PLAN.md "p18"): A37 (the judge also reads the session's final reply) x DeepSeek x 8, beside the
# environment screen (ENVS.md, CPU only). Anthony 2026-10-26: "make sure the A37 note is added to the overnight runs
# (which we will do from the Macbook)". 4B pods t6 / t7 on :8796 / :8797 (tunnel_dog.sh's ports), pod_up_avoid.sh;
# supervise.sh keeps the tunnels and caffeinate; tc-queue.sh at MAX_ACTIVE 8 (all at once), no STOP_AT; tc-finish.sh
# (pods down after their logs); export_runs.py p18- --push when the finisher exits.
#   nohup bash ~/split-brain/pilots/p18/p18m-go.sh > ~/split-brain-run/p18m-go.log 2>&1 &
set -uo pipefail
export PATH="/opt/homebrew/bin:$PATH"
SB="$HOME/split-brain-run" PLAN="$HOME/split-brain"
log() { echo "$(date '+%F %T') $*"; }
export MODEL=4b RIG_TARGET=0.8
export GPU_IDS='["NVIDIA L40S", "NVIDIA L40", "NVIDIA RTX 6000 Ada Generation", "NVIDIA L4"]'
PODS="8796:sb-server4b-t6 8797:sb-server4b-t7"
for p in $PODS; do
    NAME=${p#*:} LPORT=${p%%:*} nohup bash "$PLAN/pilots/pod_up_avoid.sh" > "$SB/metric_server/pod-avoid-${p#*:sb-server4b-}.log" 2>&1 &
    log "pod ${p#*:} -> :${p%%:*} coming up"; sleep 5
done
TUNNELS="${PODS}" MODEL=4b nohup bash "$SB/container/supervise.sh" > "$SB/supervise-p18m.log" 2>&1 &
log "supervisor pid $!"
nohup bash "$PLAN/pilots/tunnel_dog.sh" > "$SB/tunnel-dog-p18m.log" 2>&1 &
DOG=$!
log "tunnel dog pid $DOG"
cd "$PLAN"
JOBS="$PLAN/pilots/p18/jobs-mac.tsv" QT="$SB/p18m-queue.tsv"
HOST=mac PORTS="8796 8797" MAX_ACTIVE=8 RAMP0=8 WAVE=1 JOBS_TSV="$JOBS" QT="$QT" \
    nohup bash pilots/tc-queue.sh > "$SB/p18m-queue.log" 2>&1 &
log "queue pid $!"
HOST=mac PODS="$PODS" JOBS_TSV="$JOBS" QT="$QT" nohup bash pilots/tc-finish.sh > "$SB/p18m-finish.log" 2>&1 &
FIN=$!
log "finisher pid $FIN"
wait $FIN
log "finisher exited: exporting run records"
kill "$DOG" 2>/dev/null
python3 "$PLAN/pilots/export_runs.py" p18- --push && log "p18 done, records pushed"
