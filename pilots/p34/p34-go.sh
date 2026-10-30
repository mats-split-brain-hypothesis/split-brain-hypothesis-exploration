#!/opt/homebrew/bin/bash
# p34 (PLAN.md "p34"): the targeted top-up. 101 replicates of seven tc cells (A0, A3a, A3b, A7b, A10, A12, A13), each
# cell as it ran (same brief, snapshot at the same commit, harness reference in jobs.tsv `cell`), bringing every arm to
# 10 coded runs per model. Anthony 2026-10-28: "Go ahead with the targeted top-up, write it up first. Also, we can run
# some of these on the Macbook". Mac (the desktop is at the 24-container cap with p26 / p30, p31 / p32 queued behind):
# three 4B rig pods k1-k3 (:8831-8833, 8 slots each), up to 20 at once; tc-finish (copies archives to the desktop);
# each run read on the Mac as soon as it is archived; the readings copied to the desktop at the end (the Mac cannot
# push: the desktop commits them, merges codes and runs export_runs.py p34- --push).
#   cd ~/split-brain && git pull --ff-only desktop:split-brain main && nohup bash pilots/p34/p34-go.sh > ~/split-brain-run/p34-go.log 2>&1 &
set -uo pipefail
[ "$(uname)" = Darwin ] && export PATH="$HOME/.local/bin:/opt/homebrew/bin:$PATH:$HOME/anaconda3/bin" SSL_CERT_FILE=/etc/ssl/cert.pem
SB="$HOME/split-brain-run" PLAN="$HOME/split-brain"
log() { echo "$(date '+%F %T') $*"; }
[ -e "$SB/tc.pause" ] && { log "stale $SB/tc.pause: remove it first"; exit 1; }
cd "$PLAN"
JOBS="$PLAN/pilots/p34/jobs.tsv" QT="$SB/p34-queue.tsv"
# every snapshot the jobs use, rebuilt and checked against the head its original cells ran at
while IFS=$'\t' read -r s want; do
    v=${s#j-lens-mean-snapshot-}
    bash build_snapshot.sh "$v" > "$SB/p34-build-$v.log" 2>&1 || { log "build of $v failed"; exit 1; }
    [ "$(git -C "$s" rev-parse HEAD)" = "$want" ] || { log "$v: head not $want: stop"; exit 1; }
    log "$v: snapshot at $want"
done < <(awk -F'\t' 'NR > 1 {print $5 "\t" $6}' "$JOBS" | sort -u)
export MODEL=4b RIG_TARGET=0.8
export GPU_IDS='["NVIDIA L40S", "NVIDIA L40", "NVIDIA RTX 6000 Ada Generation", "NVIDIA L4"]'
PODS="8831:sb-server4b-k1 8832:sb-server4b-k2 8833:sb-server4b-k3"
for p in $PODS; do
    NAME=${p#*:} LPORT=${p%%:*} nohup bash "$PLAN/pilots/pod_up_avoid.sh" > "$SB/metric_server/pod-avoid-${p#*-}-p34.log" 2>&1 &
    log "pod ${p#*:} -> :${p%%:*} coming up"
    sleep 5
done
TUNNELS="$PODS" MODEL=4b nohup bash "$SB/container/supervise.sh" > "$SB/supervise-p34.log" 2>&1 &
SUP=$!
HOST=mac PORTS="8831 8832 8833" SLOTS=8 MAX_ACTIVE="${MAX_ACTIVE:-20}" RAMP0=10 MIN_FREE_MB=3000 WAVE=1 STOP_AT="${STOP_AT:-}" \
    JOBS_TSV="$JOBS" QT="$QT" nohup bash pilots/tc-queue.sh > "$SB/p34-queue.log" 2>&1 &
log "queue pid $!"
HOST=mac PODS="$PODS" JOBS_TSV="$JOBS" QT="$QT" nohup bash pilots/tc-finish.sh > "$SB/p34-finish.log" 2>&1 &
FIN=$!
log "finisher pid $FIN"
unread() { awk -F'\t' 'NR > 1 {print $1}' "$JOBS" | while read -r id; do
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
for i in 1 2 3 4 5 6; do
    rsync -a pilots/tc-reading-api/p34-* desktop:split-brain/pilots/tc-reading-api/ && { log "readings copied to the desktop"; break; }
    log "copy to the desktop failed ($i): retry in 10 min"; sleep 600
done
log "p34 done (desktop: python3 pilots/p34/p34_merge.py, then python3 pilots/p34/contrasts.py)"
