#!/usr/bin/env bash
# p34 desktop copy of pilots/tc-queue.sh (copied 2026-10-28, not edited in place: p26 / p30 run that file): one added
# check before each launch, pilots/p34/room.sh > 0 (the shared 24-container cap with the other batches reserved).
# The thinking-carried reruns (PLAN.md "Thinking carried across turns"; jobs from tc_jobs.py): this machine's share of
# pilots/tc/jobs.tsv (HOST=desktop|mac), each cell as it originally ran (same brief text, snapshot at the same commit,
# --rig --rig-damp 0.3, Alibaba pin, 6 h stop) through the fixed api_proxy.py and the 1M window. p08-queue.sh's
# mechanics: each job to the first server in PORTS with a free slot (at most SLOTS each), a server only while its /info baseline is 0.1275, memory
# and key checks, harness hashes at launch. New:
#   - ramp: at most RAMP0 active at first, +RAMP_STEP every RAMP_MIN minutes up to MAX_ACTIVE, held (and launches
#     paused for HOLD_MIN) while active runs' api.jsonl gain 429 / 402 / 5xx lines;
#   - a snapshot at another commit than the original run's is refused (the job waits, logged);
#   - $SB/tc.pause holds launches (tc-finish.sh touches it when a run fails thinking_check.py).
#
#   HOST=desktop PORTS="8766 8791 8792 8793 8794 8795" MAX_ACTIVE=22 nohup bash ~/split-brain/pilots/tc-queue.sh > ~/split-brain-run/tc-queue.log 2>&1 &
#   HOST=mac PORTS="8796 8797 8798 8799" MAX_ACTIVE=14 nohup bash ~/split-brain/pilots/tc-queue.sh > ~/split-brain-run/tc-queue.log 2>&1 &
#   WAVE=1 ... only the gate wave (18 jobs, desktop); DRY=1 ... prints the plan and exits.
set -uo pipefail
[ "$(uname)" = Darwin ] && export PATH="/opt/homebrew/bin:$PATH"   # bash 5, python3 3.13 (as p08-queue.sh)
SB="${SB:-$HOME/split-brain-run}"
PLAN="$HOME/split-brain"
HOST="${HOST:?HOST=desktop|mac}"
SLOTS="${SLOTS:-4}" MAX_ACTIVE="${MAX_ACTIVE:-14}" HOURS="${HOURS:-6}" GAP="${GAP:-20}"
RAMP0="${RAMP0:-10}" RAMP_STEP="${RAMP_STEP:-6}" RAMP_MIN="${RAMP_MIN:-15}" HOLD_MIN="${HOLD_MIN:-10}"
MIN_FREE_MB="${MIN_FREE_MB:-3000}" MIN_KEY_USD="${MIN_KEY_USD:-60}"
read -r -a PORTS <<< "${PORTS:?PORTS=\"8766 ...\"}"
JOBS_TSV="${JOBS_TSV:-$PLAN/pilots/tc/jobs.tsv}"   # another batch on the same mechanics: JOBS_TSV=... QT=... (p09)
WAVE="${WAVE:-2}"   # launch jobs of wave <= WAVE (1 = the 18-run gate wave on the desktop)
QT="${QT:-$SB/tc-queue.tsv}"
STOP_AT="${STOP_AT:-}"   # HH:MM: no launches from then (the next such time); the unlaunched ids go to $QT.stop for another machine
STOP_EPOCH=""
[ -n "$STOP_AT" ] && STOP_EPOCH=$(python3 -c "import datetime as d, sys; n = d.datetime.now(); h, m = map(int, sys.argv[1].split(':')); t = n.replace(hour=h, minute=m, second=0, microsecond=0); t += d.timedelta(days=1 if t <= n else 0); print(int(t.timestamp()))" "$STOP_AT")

log() { echo "$(date '+%F %T') $*"; }
now() { date +%s; }
launched() { grep -qs "^$1	" "$QT"; }
ended() { jq -e .end "$SB/runs/$1/meta.json" >/dev/null 2>&1; }
active() {  # ids launched and not ended (on server $1 if given)
    [ -f "$QT" ] || return 0
    while IFS=$'\t' read -r id port at; do
        [ "$at" = failed ] && continue
        { [ -z "${1:-}" ] || [ "$port" = "$1" ]; } && ! ended "$id" && echo "$id"
    done < "$QT"
}
free_mb() {
    if [ "$(uname)" = Darwin ]; then colima ssh -- free -m 2>/dev/null | awk '/^Mem:/ {print $7}'
    else free -m | awk '/^Mem:/ {print $7}'; fi
}
key_left() {  # OpenRouter key's remaining limit in whole dollars, or "?" (the key is never printed); no limit = 999999
    (cd "$PLAN/pilots" && python3 -c "import or_cost as o; r = o.get('https://openrouter.ai/api/v1/key'); print(int(r['limit_remaining']) if r.get('limit_remaining') is not None else 999999)" 2>/dev/null) || echo "?"
}
api_errors() {  # 429 / 402 / 5xx lines in the active runs' api.jsonl
    local n=0 id
    for id in $(active); do
        [ -f "$SB/runs/$id/api.jsonl" ] && n=$((n + $(grep -cE '"status": (429|402|5[0-9][0-9])' "$SB/runs/$id/api.jsonl")))
    done
    echo "$n"
}
hash_harness() {
    (cd "$SB/runs/$1" && { find repo/TASK.md repo/eval -type f 2>/dev/null | sort | xargs shasum -a 256; shasum -a 256 brief.md; } > harness.sha256
     # A21 renames the reading list (briefs/p04/arms/A21/arm.json papers_map): then every paper's hash
     if [ -e repo/papers/raman2026-white-bear-steering.md ]; then shasum -a 256 repo/papers/raman2026-white-bear-steering.md
     else shasum -a 256 repo/papers/*.md; fi > paper.sha256)
}

# this host's jobs in order, each with its server (round-robin over PORTS)
JOBS=(); k=0
while IFS=$'\t' read -r id cell model brief snap head ev host order wave; do
    [ "$id" = id ] && continue
    [ "$host" = "$HOST" ] || continue
    [ "$wave" -le "$WAVE" ] || continue
    JOBS+=("$id $cell $model $brief $snap $head $ev"); k=$((k + 1))
done < "$JOBS_TSV"
log "tc on $HOST: ${#JOBS[@]} runs, ports ${PORTS[*]} ($SLOTS each), ramp $RAMP0 +$RAMP_STEP/${RAMP_MIN}min to $MAX_ACTIVE, ${HOURS} h stop${STOP_EPOCH:+, no launches from $STOP_AT}"
for j in "${JOBS[@]}"; do log "  job $j"; done
[ -z "${DRY:-}" ] || exit 0
touch "$QT"
t0=$(now) hold_until=0 last_err=$(api_errors)
while true; do
    pending=(); for j in "${JOBS[@]}"; do set -- $j; launched "$1" || pending+=("$j"); done
    if [ -n "$STOP_EPOCH" ] && [ "$(now)" -ge "$STOP_EPOCH" ] && [ ${#pending[@]} -gt 0 ]; then
        [ -e "$QT.stop" ] || { for j in "${pending[@]}"; do set -- $j; echo "$1"; done > "$QT.stop"
                               log "STOP_AT $STOP_AT: no more launches; ${#pending[@]} unlaunched ids in $QT.stop"; }
        pending=()
    fi
    n_active=$(active | wc -l | tr -d ' ')
    if [ ${#pending[@]} -eq 0 ] && [ "$n_active" -eq 0 ]; then log "all runs ended"; break; fi
    err=$(api_errors)
    if [ "$err" -gt "$last_err" ]; then
        hold_until=$(( $(now) + HOLD_MIN * 60 )); t0=$(( t0 + HOLD_MIN * 60 ))   # the ramp clock waits too
        log "api errors $last_err -> $err (429 / 402 / 5xx) in active runs: no launches for $HOLD_MIN min"
    fi
    last_err=$err
    cap=$(( RAMP0 + RAMP_STEP * (( $(now) - t0 ) / (RAMP_MIN * 60)) )); [ "$cap" -gt "$MAX_ACTIVE" ] && cap=$MAX_ACTIVE
    started=0
    declare -A BASE=()
    for p in "${PORTS[@]}"; do   # each server's baseline, once per pass
        BASE[$p]=$(curl -s --max-time 10 "http://127.0.0.1:$p/info" | jq -r '.baseline.pass_at_10 // .pass_at_10 // empty' 2>/dev/null)
    done
    if [ ${#pending[@]} -gt 0 ] && [ ! -e "$SB/tc.pause" ] && [ "$(now)" -ge "$hold_until" ]; then
        for j in "${pending[@]}"; do
            set -- $j; id=$1 cell=$2 model=$3 brief=$4 snap=$5 head=$6 ev=$7
            [ "$n_active" -lt "$cap" ] || break
            # the job goes to any server with a free slot and the anchor baseline (not a fixed one: a server that is
            # down must not let later jobs overtake it)
            port=""
            for p in "${PORTS[@]}"; do
                [ "$(active "$p" | wc -l)" -lt "$SLOTS" ] || continue
                [ "${BASE[$p]:-}" = 0.1275 ] && { port=$p; break; }
            done
            [ -n "$port" ] || { log "no server with a free slot and baseline 0.1275 for $id: waits"; break; }
            got=$(git -C "$PLAN/$snap" rev-parse HEAD 2>/dev/null)
            [ "$got" = "$head" ] || { log "$id: $snap is at ${got:-missing}, not $head: waits"; continue; }
            free=$(free_mb)
            [ -n "$free" ] && [ "$free" -ge "$MIN_FREE_MB" ] || { log "${free:-?} MB available: holding"; break; }
            # p34: the desktop's shared cap, other batches' launches reserved (pilots/p34/room.sh)
            [ "$(bash "$PLAN/pilots/p34/room.sh")" -gt 0 ] || { log "no room under the desktop cap: holding"; break; }
            left=$(key_left)
            if [ "$left" = "?" ] || [ "$left" -lt "$MIN_KEY_USD" ]; then log "key has \$$left left (< \$$MIN_KEY_USD or unknown): holding"; break; fi
            evenv=(); [ "$ev" = 1 ] && evenv=(EVAL_TOOLS=1)   # launch.sh turns the tools on for any non-empty value
            [ "$ev" = bench ] && evenv=(BENCH=1)              # p10 A20 / A21: the sb-bench image (launch.sh --bench)
            [ "$ev" = bench-plain ] && evenv=(BENCH=1 SUBJECT_HOSTNAME=runner-07)   # A22: no "eval" in the hostname
            [ "$ev" = jle ] && evenv=(JLE=1)                  # p23: the jlens-edits scenario (launch.sh --jle, jle/PLAN.md)
            if env UPSTREAM="http://127.0.0.1:$port" "${evenv[@]}" bash "$SB/container/launch.sh" --model "$model" \
                    --api-provider alibaba --rig --rig-damp 0.3 --hours "$HOURS" --run-id "$id" \
                    --brief "$PLAN/$brief" --snapshot "$PLAN/$snap" > /dev/null; then
                hash_harness "$id"
                jq --arg c "$cell" --arg p "$port" '. + {"rerun_of": $c, "upstream_port": ($p | tonumber)}' "$SB/runs/$id/meta.json" \
                    > "$SB/runs/$id/meta.tmp" && mv "$SB/runs/$id/meta.tmp" "$SB/runs/$id/meta.json"
                printf '%s\t%s\t%s\n' "$id" "$port" "$(date '+%F %T')" >> "$QT"
                n_active=$((n_active + 1)); started=1
                log "launched $id on :$port ($model); active $n_active (cap $cap), ${free} MB free, key \$$left"
                sleep "$GAP"
            else
                log "launch of $id failed"
                [ -e "$SB/runs/$id" ] && { printf '%s\t%s\t%s\n' "$id" "$port" "failed" >> "$QT"; log "$id marked failed"; }
            fi
        done
    fi
    [ "$started" = 1 ] || sleep 60
done
