#!/bin/bash
# Overnight keeper on the launching machine: every minute, check the tunnel to the pod's metric server and reopen it
# if it has dropped; log what runs are alive. Keeps a Mac awake while it runs (caffeinate). Stop it with kill.
#
#   nohup bash supervise.sh > ~/split-brain-run/supervise.log 2>&1 &
SB="${SB:-$HOME/split-brain-run}"
[ "$(uname)" = Darwin ] && caffeinate -dimsu -w $$ &
# TUNNELS: port:pod name pairs to keep open (default the 27B's); the 4B pods of p03:
#   TUNNELS="8766:sb-server4b 8768:sb-server4b-2" (each reopened with MODEL=4b)
TUNNELS="${TUNNELS:-8765:sb-server}"
while true; do
    for t in $TUNNELS; do
        port=${t%%:*} name=${t#*:}
        curl -s --max-time 20 "http://127.0.0.1:$port/info" > /dev/null && continue
        echo "$(date '+%F %T') tunnel :$port down: reopening"
        if [ "$port" = 8765 ]; then bash "$SB/metric_server/pod_server.sh" tunnel 2>&1 | tail -1
        else MODEL=4b NAME="$name" LPORT="$port" bash "$SB/metric_server/pod_server.sh" tunnel 2>&1 | tail -1; fi
    done
    echo "$(date '+%F %T') up; runs: $(docker ps --filter name=sb- --format '{{.Names}}' | tr '\n' ' ')"
    sleep 60
done
