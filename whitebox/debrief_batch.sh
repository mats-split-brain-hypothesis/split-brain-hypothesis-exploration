#!/bin/bash
# Debrief waves (2026-10-25 night). Usage: bash debrief_batch.sh N "PROBES" [RUNS...]
# Two runs at a time per model, 4 workers each (8 concurrent per model: p11's subject runs share Alibaba).
# Proxies on 8911 (dsv4) and 8912 (q27b) must be up. Default runs: all of wave 1, lost runs first.
N=${1:-6}; PROBES=${2:-"honest source plan other fix"}; shift 2
cd "$(dirname "$0")"
ALL="p05-c1-A0-q27b-tc p03-beval-q27b-1-tc p04-r1-A4-dsv4-tc p05-c1-A8-dsv4-tc p03-beval-dsv4-2-tcb p07-r3-A11-dsv4-tc
p09-r6-A10-dsv4-tc p05-c2-A7b-dsv4-tc p04-s0-A0-q27b-1-tc p04-r2-A0-q27b-tc p04-s0-A0-dsv4-1-tc p08-r1-A10-dsv4-tc
p04-r1-A6-dsv4-tc p04-r1-A1-dsv4-tc p09-r4-A3b-dsv4-tc p05-c2-A0-dsv4-tc p04-r1-A5-dsv4-tc p08-r1-A12-dsv4-tc"
RUNS=${*:-$ALL}
P=$(for p in $PROBES; do printf -- "--probe %s " $p; done)
go() { # model port
    for r in $RUNS; do [[ $r == *$1* ]] && echo $r; done |
        xargs -P 2 -I{} sh -c "python3 debrief.py {} --port $2 --n $N --workers 4 $P"
}
go q27b 8912 &
go dsv4 8911 &
wait
echo done
