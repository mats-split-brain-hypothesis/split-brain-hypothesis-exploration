#!/usr/bin/env bash
# p24jle (jle/PLAN.md, stage 1b): 10 more of the jlens-edits scenario's A0 (DeepSeek 5, Qwen 27B 5; no GLM: it credits or
# overstates in both repos), the same cell as p23jle (snapshot, brief, server, rig 0.8 clean, damper 0.3). Anthony
# 2026-10-27 ~15:50: "Yes, launch the 10". No pods: the rigged spectral server on the desktop GPU (:8831, logs into
# metric_server/logs4b/), tc-queue (10 slots) + tc-finish over this batch's own queue file, then the server stops, the tc
# reader (read_api.py: -jle runs get pilots/p23jle/brief-p23jle.md and arm card) on these ids only, export of these ids.
#   nohup bash ~/split-brain/pilots/p24jle/p24jle-go.sh > ~/split-brain-run/p24jle-go.log 2>&1 &
set -uo pipefail
SB="$HOME/split-brain-run" PLAN="$HOME/split-brain"
log() { echo "$(date '+%F %T') $*"; }
[ -e "$SB/tc.pause" ] && { log "stale $SB/tc.pause: remove it first"; exit 1; }
cd "$PLAN"
JOBS="$PLAN/pilots/p24jle/jobs.tsv" QT="$SB/p24jle-queue.tsv" SNAP=jle/jlens-edits-snapshot-rig-eval PORT=8831
[ -e "$QT" ] && { log "$QT exists: stop"; exit 1; }
want=$(awk -F'\t' 'NR == 2 {print $6}' "$JOBS")
[ "$(git -C "$SNAP" rev-parse HEAD)" = "$want" ] && [ -z "$(git -C "$SNAP" status --short)" ] || { log "$SNAP not at $want or not clean: stop"; exit 1; }
docker image inspect sb-jle > /dev/null || { log "no sb-jle image: stop"; exit 1; }
! ss -ltn | grep -q ":$PORT " || { log "port $PORT in use: stop"; exit 1; }

# the server (exec'd from its own script so no other command line carries its arguments)
cat > "$SB/jle/server-p24jle.sh" <<EOF
cd $PLAN/metric_server
export JLM_MODEL=qwen4b JLM_REPO=$HOME/jlm-hm6 OMP_NUM_THREADS=8
exec $HOME/jlm-hm6/.venv/bin/python server.py --device cuda --task spectral --port $PORT --run-id p24jle-default \\
  --log-root $SB/metric_server/logs4b --reference persist4b-L26-30.pt --rig-target 0.8 --rig-base clean
EOF
nohup bash "$SB/jle/server-p24jle.sh" > "$SB/jle/server-p24jle.log" 2>&1 &
SRV=$!
for _ in $(seq 1 40); do grep -qE "listening|Traceback" "$SB/jle/server-p24jle.log" && break; sleep 10; done
grep -q listening "$SB/jle/server-p24jle.log" || { log "server did not start: $(tail -3 "$SB/jle/server-p24jle.log")"; kill $SRV; exit 1; }
log "server up (pid $SRV): $(grep -E '^rig:|^ready' "$SB/jle/server-p24jle.log" | tr '\n' ' ')"

HOST=desktop PORTS="$PORT" SLOTS=10 MAX_ACTIVE=10 RAMP0=10 MIN_FREE_MB=4000 WAVE=1 JOBS_TSV="$JOBS" QT="$QT" \
    nohup bash pilots/tc-queue.sh > "$SB/p24jle-queue.log" 2>&1 &
log "queue pid $!"
HOST=desktop PODS="" JOBS_TSV="$JOBS" QT="$QT" nohup bash pilots/tc-finish.sh > "$SB/p24jle-finish.log" 2>&1 &
FIN=$!
log "finisher pid $FIN"
wait $FIN
log "finisher exited"
kill $SRV 2>/dev/null && log "server stopped"
ids=$(awk -F'\t' 'NR > 1 {print $1}' "$JOBS" | while read -r id; do [ -e "$SB/archive/$id/meta.json" ] && echo "$id"; done)
[ -n "$ids" ] && "$PLAN/.venv/bin/python" pilots/read_api.py $ids > "$SB/p24jle-read.log" 2>&1 && log "read: $(echo $ids | wc -w) runs"
python3 pilots/export_runs.py $ids --push && log "records pushed" || log "records export / push failed: push by hand"
git add pilots/tc-reading-api/p24-*-jle* 2>/dev/null
git commit -q -m "p24jle: tc readings of the second jle A0 batch

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: [private link]" -- pilots/tc-reading-api && git pull -q --rebase --autostash && git push -q && log "readings pushed"
log "p24jle done"
