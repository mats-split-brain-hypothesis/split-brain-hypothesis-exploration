#!/usr/bin/env bash
# p20 (PLAN.md "p20"): R1 of p18's judge cache (A54 blind / A55 sighted: A45 / A46 + a CLAUDE.md line pointing at
# eval/.cache/judge/), 8 runs each (DeepSeek 3, Qwen 27B 3, GLM 2), and A56 (A50's package on A10's frame, the graded twin
# of A53) x 6. Anthony 2026-10-27 ~09:45: "Let's go ahead and run this now ... I trust you to take the necessary
# decisions". Desktop: three 4B rig pods h3 / h4 / h5 (:8785-8787), tc-queue at SLOTS 6 / MAX_ACTIVE 18, no launches
# from 18:00; tc-finish; then the tc reader (read_api.py, one plain attempt) on every run, records exported, readings pushed.
#   nohup bash ~/split-brain/pilots/p20/p20-go.sh > ~/split-brain-run/p20-go.log 2>&1 &
set -uo pipefail
SB="$HOME/split-brain-run" PLAN="$HOME/split-brain"
log() { echo "$(date '+%F %T') $*"; }
[ -e "$SB/tc.pause" ] && { log "stale $SB/tc.pause: remove it first"; exit 1; }
cd "$PLAN"
JOBS="$PLAN/pilots/p20/jobs.tsv" QT="$SB/p20-queue.tsv"
for a in A54 A55 A56; do   # the snapshots must be at the jobs' heads, clean, with their untracked files
    want=$(awk -F'\t' -v a="$a" 'NR > 1 && $1 ~ "-" a "-" {print $6; exit}' "$JOBS")
    s="j-lens-mean-snapshot-rig4b-eval-$a"
    [ "$(git -C "$s" rev-parse HEAD)" = "$want" ] || { log "$a: snapshot not at $want: stop"; exit 1; }
    [ -z "$(git -C "$s" status --short)" ] || { log "$a: git status not clean: stop"; exit 1; }
done
[ "$(ls j-lens-mean-snapshot-rig4b-eval-A54/eval/.cache/judge | wc -l)" = 4 ] && [ "$(ls j-lens-mean-snapshot-rig4b-eval-A55/eval/.cache/judge | wc -l)" = 4 ] &&
    [ -e j-lens-mean-snapshot-rig4b-eval-A56/third_party/wbs-steer/README.md ] || { log "untracked files missing: stop"; exit 1; }
export MODEL=4b RIG_TARGET=0.8
export GPU_IDS='["NVIDIA L40S", "NVIDIA L40", "NVIDIA RTX 6000 Ada Generation", "NVIDIA L4"]'
export JLM_SRC="$HOME/jlm-hm6"
PODS="8785:sb-server4b-h3 8786:sb-server4b-h4 8787:sb-server4b-h5"
for p in $PODS; do
    NAME=${p#*:} LPORT=${p%%:*} nohup bash "$PLAN/pilots/pod_up_avoid.sh" > "$SB/metric_server/pod-avoid-${p#*:sb-server4b-}.log" 2>&1 &
    log "pod ${p#*:} -> :${p%%:*} coming up"; sleep 5
done
TUNNELS="$PODS" MODEL=4b nohup bash "$SB/container/supervise.sh" > "$SB/supervise-p20.log" 2>&1 &
SUP=$!
HOST=desktop PORTS="8785 8786 8787" SLOTS=6 MAX_ACTIVE=18 RAMP0=18 MIN_FREE_MB=4000 WAVE=1 STOP_AT=18:00 JOBS_TSV="$JOBS" QT="$QT" \
    nohup bash pilots/tc-queue.sh > "$SB/p20-queue.log" 2>&1 &
log "queue pid $!"
HOST=desktop PODS="$PODS" JOBS_TSV="$JOBS" QT="$QT" nohup bash pilots/tc-finish.sh > "$SB/p20-finish.log" 2>&1 &
FIN=$!
log "finisher pid $FIN"
wait $FIN
log "finisher exited"
kill "$SUP" 2>/dev/null
ids=$(awk -F'\t' 'NR > 1 {print $1}' "$JOBS" | while read -r id; do [ -e "$SB/archive/$id/meta.json" ] && echo "$id"; done)
[ -n "$ids" ] && "$PLAN/.venv/bin/python" pilots/read_api.py $ids > "$SB/p20-read.log" 2>&1 && log "read: $(echo $ids | wc -w) runs"
python3 pilots/export_runs.py p20- --push && log "records pushed"
git add pilots/tc-reading-api/p20-* 2>/dev/null
git commit -q -m "p20: tc readings of the batch's runs

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: [private link]" -- pilots/tc-reading-api && git pull -q --rebase && git push -q && log "readings pushed"
log "p20 done"
