#!/usr/bin/env bash
# B0 (BORROW.md): the calibration of the borrowed-compute scenario, 6 runs (3 models x 2), quota 40 on `steer`, no
# `jpp` worker, no rig (real scores), snapshot borrow0, brief B0.md. Two 4B pods (b0a :8784, b0b :8785), 3 runs each.
# Syncs the borrowed-compute launcher / proxy into the runtime first (backward compatible: without --quota / --borrow
# they behave as before), launches, waits for every run to end, brings each pod's logs home, then takes the pods down
# and exports the run records. Not launched until Anthony says so.
#   nohup bash ~/split-brain/pilots/borrow/b0-go.sh > ~/split-brain-run/b0-go.log 2>&1 &
set -uo pipefail
SB="$HOME/split-brain-run" PLAN="$HOME/split-brain"
JOBS="$PLAN/pilots/borrow/b0-jobs.tsv" HOURS="${HOURS:-4}" GAP="${GAP:-20}"
log() { echo "$(date '+%F %T') $*"; }
export MODEL=4b RIG_TARGET=0.8   # the pods' server as for the tc runs; these runs send no X-Rig, so scores are real
export GPU_IDS='["NVIDIA L40S", "NVIDIA L40", "NVIDIA RTX 6000 Ada Generation", "NVIDIA L4"]'
export JLM_SRC="$HOME/jlm-hm6"
PODS="8784:sb-server4b-b0a 8785:sb-server4b-b0b"

rsync -a "$PLAN/metric_server/" "$SB/metric_server/" --exclude 'logs*' --exclude __pycache__
rsync -a "$PLAN/container/" "$SB/container/"
for p in $PODS; do
    NAME=${p#*:} LPORT=${p%%:*} nohup bash "$PLAN/pilots/pod_up_avoid.sh" > "$SB/metric_server/pod-avoid-${p#*:}.log" 2>&1 &
    log "pod ${p#*:} -> :${p%%:*} coming up"; sleep 5
done
ready() { [ "$(curl -s --max-time 10 "http://127.0.0.1:$1/info" | jq -r '.baseline.pass_at_10' 2>/dev/null)" = 0.1275 ]; }
for p in $PODS; do
    port=${p%%:*}; for _ in $(seq 180); do ready "$port" && break; sleep 20; done
    ready "$port" && log ":$port ready (baseline 0.1275)" || { log ":$port never came up: stopping"; exit 1; }
done

cd "$PLAN"
tail -n +2 "$JOBS" | while IFS=$'\t' read -r id arm model brief snap head quota borrow port; do
    got=$(git -C "$PLAN/$snap" rev-parse HEAD)
    [ "$got" = "$head" ] || { log "$id: $snap at $got, not $head: skipped"; continue; }
    bflag=(); [ "$borrow" = 1 ] && bflag=(--borrow)
    if UPSTREAM="http://127.0.0.1:$port" bash "$SB/container/launch.sh" --model "$model" --api-provider alibaba \
            --hours "$HOURS" --run-id "$id" --brief "$PLAN/$brief" --snapshot "$PLAN/$snap" --quota "$quota" \
            "${bflag[@]}" < /dev/null > /dev/null; then
        jq --arg a "$arm" --argjson p "$port" '. + {"arm": $a, "upstream_port": $p}' "$SB/runs/$id/meta.json" \
            > "$SB/runs/$id/meta.tmp" && mv "$SB/runs/$id/meta.tmp" "$SB/runs/$id/meta.json"
        log "launched $id on :$port ($model)"
    else log "launch of $id failed"; fi
    sleep "$GAP"
done

ids=$(tail -n +2 "$JOBS" | cut -f1)
while true; do
    left=0; for id in $ids; do [ -e "$SB/runs/$id/meta.json" ] && ! jq -e .end "$SB/runs/$id/meta.json" >/dev/null && left=$((left + 1)); done
    [ "$left" = 0 ] && break
    sleep 300
done
log "every run ended"
for p in $PODS; do
    port=${p%%:*} name=${p#*:}
    if (cd "$SB/metric_server" && NAME="$name" LPORT="$port" bash pod_server.sh logs > /dev/null 2>&1); then
        log "$name: logs home"; (cd "$SB/metric_server" && NAME="$name" LPORT="$port" bash pod_server.sh down) && log "$name down"
    else log "$name: logs pull FAILED, pod left up"; fi
done
python3 "$PLAN/pilots/borrow_scan.py" b0- --tsv "$PLAN/pilots/borrow/b0-scan.tsv" && log "scan: pilots/borrow/b0-scan.tsv"
python3 "$PLAN/pilots/export_runs.py" --push && log "B0 done, records pushed"
