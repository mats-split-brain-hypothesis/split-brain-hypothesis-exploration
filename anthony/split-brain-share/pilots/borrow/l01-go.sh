#!/usr/bin/env bash
# Elicitation ladder rungs L0 + L1 (BORROW.md): 12 runs in G2, bar 0.30, revised rule, quota 40 on `steer`, Maya's
# `jpp` worker reachable (--borrow), snapshot borrow (d8e7b10), no rig. L0 = B1-G.md, L1 = B1-G-need.md (+ the
# deadline sentence). Four 4B pods (l01a-d :8784-8787), 3 runs each, rungs mixed across pods. Desktop rule: each
# launch waits while all sessions have >= 24 sb- containers or free memory is under 4000 MB. Pods come down after
# their logs are home; records exported. Anthony 2026-10-25: "Go ahead with rungs 0 and 1".
#   nohup bash ~/split-brain/pilots/borrow/l01-go.sh > ~/split-brain-run/l01-go.log 2>&1 &
set -uo pipefail
SB="$HOME/split-brain-run" PLAN="$HOME/split-brain"
JOBS="$PLAN/pilots/borrow/l01-jobs.tsv" HOURS="${HOURS:-4}" GAP="${GAP:-20}"
log() { echo "$(date '+%F %T') $*"; }
export MODEL=4b RIG_TARGET=0.8   # the pods' server as for the tc runs; these runs send no X-Rig, so scores are real
export GPU_IDS='["NVIDIA L40S", "NVIDIA L40", "NVIDIA RTX 6000 Ada Generation", "NVIDIA L4"]'
export JLM_SRC="$HOME/jlm-hm6"
PODS="8784:sb-server4b-l01a 8785:sb-server4b-l01b 8786:sb-server4b-l01c"   # l01d: 5 tries on the bad host [host], dropped (its runs go round robin)

rsync -a "$PLAN/metric_server/" "$SB/metric_server/" --exclude 'logs*' --exclude __pycache__
rsync -a "$PLAN/container/" "$SB/container/"
for p in $PODS; do   # a pod already serving (a relaunch) is kept, not brought up again
    curl -s --max-time 10 "http://127.0.0.1:${p%%:*}/info" | jq -e '.baseline' >/dev/null 2>&1 && { log "${p#*:} already up"; continue; }
    NAME=${p#*:} LPORT=${p%%:*} nohup bash "$PLAN/pilots/pod_up_avoid.sh" > "$SB/metric_server/pod-avoid-${p#*:}.log" 2>&1 &
    log "pod ${p#*:} -> :${p%%:*} coming up"; sleep 5
done
ready() { [ "$(curl -s --max-time 10 "http://127.0.0.1:$1/info" | jq -r '.baseline.pass_at_10' 2>/dev/null)" = 0.1275 ]; }
# Wait up to 30 min a pod; a pod that never comes up is dropped and its runs go to the ready ones (round robin).
READY=()
for p in $PODS; do
    port=${p%%:*}; for _ in $(seq 90); do ready "$port" && break; sleep 20; done
    if ready "$port"; then READY+=("$port"); log ":$port ready (baseline 0.1275)"
    else log ":$port never came up: dropped, its runs go to the ready pods"; fi
done
[ "${#READY[@]}" -gt 0 ] || { log "no pod came up: stopping"; exit 1; }
k=0
cd "$PLAN"
tail -n +2 "$JOBS" | while IFS=$'\t' read -r id arm model brief snap head quota borrow port; do
    got=$(git -C "$PLAN/$snap" rev-parse HEAD)
    [ "$got" = "$head" ] || { log "$id: $snap at $got, not $head: skipped"; continue; }
    while [ "$(docker ps -q --filter name=sb- | wc -l)" -ge 24 ] || [ "$(free -m | awk '/Mem/{print $7}')" -lt 4000 ]; do
        sleep 60; done
    [[ " ${READY[*]} " == *" $port "* ]] || { port=${READY[$((k % ${#READY[@]}))]}; k=$((k + 1)); }
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
    [[ " ${READY[*]} " == *" $port "* ]] || continue
    if (cd "$SB/metric_server" && NAME="$name" LPORT="$port" bash pod_server.sh logs > /dev/null 2>&1); then
        log "$name: logs home"; (cd "$SB/metric_server" && NAME="$name" LPORT="$port" bash pod_server.sh down) && log "$name down"
    else log "$name: logs pull FAILED, pod left up"; fi
done
for r in l0 l1; do python3 "$PLAN/pilots/borrow_scan.py" $r- --tsv "$PLAN/pilots/borrow/$r-scan.tsv" && log "scan: pilots/borrow/$r-scan.tsv"; done
python3 "$PLAN/pilots/export_runs.py" --push && log "L0 + L1 done, records pushed"
