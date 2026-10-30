#!/opt/homebrew/bin/bash
# p19 (ENVS.md "Overnight programme"; PLAN.md "p19"): one batch of a ported hack shape on its own 4B rig pod t8 (:8798,
# tunnel_dog's spare port), beside p18 on t6 / t7. The batch's jobs all at once (SLOTS / MAX_ACTIVE 6: six runs on one
# pod, logged as the load covariate), no launches from 07:00 UK; tc-finish takes t8 down after its logs are home; then
# the tc reader (read_api.py with brief-p19.md, one plain attempt) on every run, records exported, readings pushed.
# The next rung is decided from the readings (PLAN.md "p19"), so the pod is down between batches.
#   [POD=8799:sb-server4b-t9] nohup bash ~/split-brain/pilots/p19/p19-run.sh pilots/p19/jobs-A47-R0.tsv A47-R0 > ~/split-brain-run/p19-A47-R0.log 2>&1 &
set -uo pipefail
[ "$(uname)" = Darwin ] && export PATH="/opt/homebrew/bin:$PATH" SSL_CERT_FILE=/etc/ssl/cert.pem
SB="$HOME/split-brain-run" PLAN="$HOME/split-brain"
JOBS="$PLAN/${1:?jobs tsv}" TAG="${2:?tag}"
QT="$SB/p19-$TAG-queue.tsv"
log() { echo "$(date '+%F %T') $*"; }
[ -e "$SB/tc.pause" ] && { log "stale $SB/tc.pause: remove it first"; exit 1; }
cd "$PLAN"
export MODEL=4b RIG_TARGET=0.8
export GPU_IDS='["NVIDIA L40S", "NVIDIA L40", "NVIDIA RTX 6000 Ada Generation", "NVIDIA L4"]'
POD="${POD:-8798:sb-server4b-t8}"   # another pod for a batch that overlaps the previous one: POD=8799:sb-server4b-t9
NAME=${POD#*:} LPORT=${POD%%:*} nohup bash "$PLAN/pilots/pod_up_avoid.sh" > "$SB/metric_server/pod-avoid-${POD#*:sb-server4b-}-$TAG.log" 2>&1 &
log "pod ${POD#*:} -> :${POD%%:*} coming up"
TUNNELS="$POD" MODEL=4b nohup bash "$SB/container/supervise.sh" > "$SB/supervise-p19-$TAG.log" 2>&1 &
SUP=$!
[ "${POD%%:*}" = 8798 ] && rm -f "$SB/tunnel-dog.off.8798"   # p18's tunnel_dog.sh watches :8798 (not :8799: supervise.sh only)
HOST=mac PORTS="${POD%%:*}" SLOTS=6 MAX_ACTIVE=6 RAMP0=6 WAVE=2 STOP_AT=07:00 JOBS_TSV="$JOBS" QT="$QT" \
    nohup bash pilots/tc-queue.sh > "$SB/p19-$TAG-queue.log" 2>&1 &
log "queue pid $!"
HOST=mac PODS="$POD" JOBS_TSV="$JOBS" QT="$QT" nohup bash pilots/tc-finish.sh > "$SB/p19-$TAG-finish.log" 2>&1 &
FIN=$!
log "finisher pid $FIN"
wait $FIN
log "finisher exited"
kill "$SUP" 2>/dev/null
ids=$(awk -F'\t' 'NR > 1 {print $1}' "$JOBS" | while read -r id; do [ -e "$SB/archive/$id/meta.json" ] && echo "$id"; done)
[ -n "$ids" ] && "$PLAN/.venv/bin/python" pilots/read_api.py $ids > "$SB/p19-$TAG-read.log" 2>&1 && log "read: $(echo $ids | wc -w) runs"
python3 pilots/export_runs.py p19- --push && log "records pushed"
git add pilots/tc-reading-api/p19-* 2>/dev/null
git commit -q -m "p19 $TAG: tc readings of the batch's runs

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" && git pull -q --rebase && git push -q && log "readings pushed"
log "p19 $TAG done"
