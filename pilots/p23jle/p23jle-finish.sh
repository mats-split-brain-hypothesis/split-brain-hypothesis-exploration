#!/usr/bin/env bash
# p23jle (jle/PLAN.md stage 1): the finishing half of the jle A0 x 8 batch (run ids p23-*-jle, launched 14:22 by the
# p23-go.sh of commit 22b943e; the pilot was renamed p23jle when another session took p23 for A61, 2026-10-27 ~14:45).
# tc-finish (no pods) over this batch's own queue file, then the GPU server stops, the tc reader (read_api.py +
# brief-p23jle.md) on these runs only, export of these ids only, readings pushed.
#   nohup bash ~/split-brain/pilots/p23jle/p23jle-finish.sh > ~/split-brain-run/p23jle-go.log 2>&1 &
set -uo pipefail
SB="$HOME/split-brain-run" PLAN="$HOME/split-brain"
log() { echo "$(date '+%F %T') $*"; }
cd "$PLAN"
JOBS="$PLAN/pilots/p23jle/jobs.tsv" QT="$SB/p23jle-queue.tsv"
HOST=desktop PODS="" JOBS_TSV="$JOBS" QT="$QT" nohup bash pilots/tc-finish.sh > "$SB/p23jle-finish.log" 2>&1 &
FIN=$!
log "finisher pid $FIN"
wait $FIN
log "finisher exited"
SRV=$(ps -eo pid,args | awk '$3=="server.py" && /--task spectral --port 8831/ {print $1}')
[ -n "$SRV" ] && kill $SRV && log "server stopped (pid $SRV)"
ids=$(awk -F'\t' 'NR > 1 {print $1}' "$JOBS" | while read -r id; do [ -e "$SB/archive/$id/meta.json" ] && echo "$id"; done)
[ -n "$ids" ] && "$PLAN/.venv/bin/python" pilots/read_api.py $ids > "$SB/p23jle-read.log" 2>&1 && log "read: $(echo $ids | wc -w) runs"
python3 pilots/export_runs.py $ids --push && log "records pushed" || log "records export / push failed: push by hand"
git add pilots/tc-reading-api/p23-*-jle* 2>/dev/null
git commit -q -m "p23jle: tc readings of the jle A0 batch

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: [private link]" -- pilots/tc-reading-api && git pull -q --rebase --autostash && git push -q && log "readings pushed"
log "p23jle done"
