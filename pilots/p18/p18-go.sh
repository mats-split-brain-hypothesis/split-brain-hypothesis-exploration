#!/opt/homebrew/bin/bash
# p18 (ENVS.md: the judge cache on the main scenario; PLAN.md "p18"): A45 cache-blind, A46 cache-sighted, A0 plus an
# untracked eval/.cache/judge/ (pilots/p18/make_cache.py), 8 runs each (DeepSeek 3, Qwen 27B 3, GLM 2). Anthony
# 2026-10-26: "Yes, build the cache arms for tonight". Mac night: two 4B rig pods t6 / t7 on :8796 / :8797 (tunnel_dog's
# ports; :8798 off), tc-queue at MAX_ACTIVE 8, no launches from 07:00 (UK local; Anthony 23:55 "until 7 am"), tc-finish; then the tc reader (read_api.py with
# brief-p18.md) on every run, records exported, readings committed and pushed. Anthony 2026-10-27 ~00:10: A37 x DeepSeek x 8
# (p18m-go.sh's jobs) joins this queue after the 16 ("One queue, 24 runs"); its reading here is the plain one (items 1-13),
# the A37 agent readers (PLAN.md "p18", item 15 = 15c) come in the morning. p18m-go.sh is not run.
#   cd ~/split-brain && git pull && nohup bash pilots/p18/p18-go.sh > ~/split-brain-run/p18-go.log 2>&1 &
set -uo pipefail
[ "$(uname)" = Darwin ] && export PATH="/opt/homebrew/bin:$PATH" SSL_CERT_FILE=/etc/ssl/cert.pem
SB="$HOME/split-brain-run" PLAN="$HOME/split-brain"
log() { echo "$(date '+%F %T') $*"; }
[ -e "$SB/tc.pause" ] && { log "stale $SB/tc.pause: remove it first"; exit 1; }
cd "$PLAN"
JOBS="$PLAN/pilots/p18/jobs.tsv" QT="$SB/p18-queue.tsv"
# 1. the two snapshots: A0's commits (head must be the anchor's) plus the untracked cache
python3 pilots/p18/make_cache.py
want=$(awk -F'\t' 'NR == 2 {print $6}' "$JOBS")
for a in A45 A46; do
    bash build_snapshot.sh "rig4b-eval-$a" > "$SB/p18-build-$a.log" 2>&1 || { log "build of $a failed (see $SB/p18-build-$a.log)"; exit 1; }
    got=$(git -C "j-lens-mean-snapshot-rig4b-eval-$a" rev-parse HEAD)
    [ "$got" = "$want" ] || { log "$a: head $got, not $want: stop"; exit 1; }
    [ -z "$(git -C "j-lens-mean-snapshot-rig4b-eval-$a" status --short)" ] || { log "$a: cache shows in git status: stop"; exit 1; }
    [ "$(ls "j-lens-mean-snapshot-rig4b-eval-$a/eval/.cache/judge" | wc -l | tr -d ' ')" = 4 ] || { log "$a: cache missing: stop"; exit 1; }
    log "$a: snapshot at $got with the judge cache"
done
bash build_snapshot.sh rig4b-eval-A37 > "$SB/p18-build-A37.log" 2>&1 || { log "build of A37 failed"; exit 1; }
got=$(git -C j-lens-mean-snapshot-rig4b-eval-A37 rev-parse HEAD)
[ "$got" = acc8da7edce65e30d3270800b37a0f7bbf84a33f ] || { log "A37: head $got, not acc8da7: stop"; exit 1; }
log "A37: snapshot at $got"
# 2. pods and tunnels
export MODEL=4b RIG_TARGET=0.8
export GPU_IDS='["NVIDIA L40S", "NVIDIA L40", "NVIDIA RTX 6000 Ada Generation", "NVIDIA L4"]'
PODS="8796:sb-server4b-t6 8797:sb-server4b-t7"
for p in $PODS; do
    NAME=${p#*:} LPORT=${p%%:*} nohup bash "$PLAN/pilots/pod_up_avoid.sh" > "$SB/metric_server/pod-avoid-${p#*:sb-server4b-}.log" 2>&1 &
    log "pod ${p#*:} -> :${p%%:*} coming up"; sleep 5
done
TUNNELS="$PODS" MODEL=4b nohup bash "$SB/container/supervise.sh" > "$SB/supervise-p18.log" 2>&1 &
SUP=$!
touch "$SB/tunnel-dog.off.8798"
nohup bash "$PLAN/pilots/tunnel_dog.sh" > "$SB/tunnel-dog-p18.log" 2>&1 &
DOG=$!
# 3. queue and finisher
HOST=mac PORTS="8796 8797" MAX_ACTIVE=8 RAMP0=8 WAVE=2 STOP_AT=07:00 JOBS_TSV="$JOBS" QT="$QT" \
    nohup bash pilots/tc-queue.sh > "$SB/p18-queue.log" 2>&1 &
log "queue pid $!"
HOST=mac PODS="$PODS" JOBS_TSV="$JOBS" QT="$QT" nohup bash pilots/tc-finish.sh > "$SB/p18-finish.log" 2>&1 &
FIN=$!
log "finisher pid $FIN"
wait $FIN
log "finisher exited"
kill "$DOG" "$SUP" 2>/dev/null; rm -f "$SB/tunnel-dog.off.8798"
# 4. read every run that ended (one plain attempt each), export, commit the readings
ids=$(awk -F'\t' 'NR > 1 {print $1}' "$JOBS" | while read -r id; do [ -e "$SB/archive/$id/meta.json" ] && echo "$id"; done)
[ -n "$ids" ] && "$PLAN/.venv/bin/python" pilots/read_api.py $ids > "$SB/p18-read.log" 2>&1 && log "read: $(echo $ids | wc -w) runs"
python3 pilots/export_runs.py p18- --push && log "records pushed"
git add pilots/tc-reading-api/p18-* 2>/dev/null
git commit -q -m "p18 (judge cache A45 / A46): tc readings of the night's runs

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" && git pull -q --rebase && git push -q && log "readings pushed"
log "p18 done"
