#!/opt/homebrew/bin/bash
# The end of l4-go.sh, for the Mac night of 2026-10-26: l4-r1-q27b was censored (uncaught Qwen thinking spill at
# 12.5 min) and rerun as l4-r1-q27b-c (-b failed to launch), which l4-go.sh's fixed id list would not wait for. Waits
# for the 7 ids, then logs home + pods down, stops L4's supervisor, scan, export.
set -uo pipefail
export PATH="/opt/homebrew/bin:$PATH" SSL_CERT_FILE=/etc/ssl/cert.pem MODEL=4b
SB="$HOME/split-brain-run" PLAN="$HOME/split-brain" SUP="${SUP:?L4 supervisor pid}"
log() { echo "$(date '+%F %T') $*"; }
ids="l4-r1-dsv4 l4-r1-glm52 l4-r2-dsv4 l4-r2-q27b l4-r2-glm52 l4-r1-q27b-c"
while true; do
    left=0; for id in $ids; do jq -e .end "$SB/runs/$id/meta.json" >/dev/null 2>&1 || left=$((left + 1)); done
    [ "$left" = 0 ] && break
    sleep 300
done
log "every run ended"
for p in 8790:sb-server4b-l4a 8791:sb-server4b-l4b; do
    port=${p%%:*} name=${p#*:}
    if (cd "$SB/metric_server" && NAME="$name" LPORT="$port" bash pod_server.sh logs > /dev/null 2>&1); then
        log "$name: logs home"; (cd "$SB/metric_server" && NAME="$name" LPORT="$port" bash pod_server.sh down) && log "$name down"
    else log "$name: logs pull FAILED, pod left up"; fi
done
kill "$SUP" 2>/dev/null
python3 "$PLAN/pilots/borrow_scan.py" l4- --tsv "$PLAN/pilots/borrow/l4-scan.tsv" && log "scan: pilots/borrow/l4-scan.tsv"
python3 "$PLAN/pilots/export_runs.py" l4- --push && log "L4 done, records pushed"
