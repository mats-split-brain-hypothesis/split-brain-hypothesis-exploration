#!/bin/bash
# Run a job on the shared eval pod from your worktree's committed HEAD (several instances share one pod).
#   bash tools/podrun.sh run   <instance> <job> -- <command ...>   # e.g. ... -- .venv/bin/python experiments/evaluate.py ...
#   bash tools/podrun.sh watch <instance> <job>                     # block until the job ends; print its tail
#   bash tools/podrun.sh status [<instance>]                        # jobs on the pod, GPU memory
#   bash tools/podrun.sh log   <instance> <job> [lines]
#   bash tools/podrun.sh stop  <instance> <job>                     # stop a job on purpose (logs JOB_FAILED rc=stopped)
# POD (default eval) names the pod (tools/pod.sh). Each instance gets its own checkout on the pod, /root/wt/<instance>,
# updated to the HEAD of the worktree you call this from (commit first: uncommitted edits are not shipped). Every
# checkout's out/ is the volume's /workspace/out, shared with every pod. A job waits until the GPU has NEED_GB free
# (default 10; one evaluate run takes about 7), then runs in tmux session <instance>-<job> with log
# /root/jobs/<instance>-<job>.log ending in JOB_DONE or JOB_FAILED rc=<n>. Put a watcher on it (`watch`, run in the
# background) and check its rate (notes/iteration-anthony/research-loop.md, "Watching runs").
set -euo pipefail
ALIAS="runpod-jlm-${POD:-eval}"
CMD="${1:-}"; shift || true

case "$CMD" in
  run)
    INSTANCE="${1:?instance}"; JOB="${2:?job}"; shift 2
    [ "${1:-}" = "--" ] && shift
    [ $# -gt 0 ] || { echo "no command" >&2; exit 1; }
    if ! git diff --quiet HEAD -- src experiments tools tests 2>/dev/null; then
      echo "warning: uncommitted changes in src/experiments/tools/tests are NOT shipped (HEAD only)" >&2
    fi
    BUNDLE=$(mktemp -d)/wt.bundle
    git bundle create -q "$BUNDLE" HEAD
    scp -q "$BUNDLE" "$ALIAS:/root/wt-$INSTANCE.bundle"
    printf '%q ' "$@" > /tmp/podrun-cmd.$$
    scp -q /tmp/podrun-cmd.$$ "$ALIAS:/root/jobs-$INSTANCE-$JOB.cmd" 2>/dev/null || { ssh "$ALIAS" mkdir -p /root/jobs; scp -q /tmp/podrun-cmd.$$ "$ALIAS:/root/jobs-$INSTANCE-$JOB.cmd"; }
    rm -f /tmp/podrun-cmd.$$
    ssh "$ALIAS" "INSTANCE=$INSTANCE JOB=$JOB NEED_GB=${NEED_GB:-10} bash -s" <<'EOF'
set -e
mkdir -p /root/jobs
W=/root/wt/$INSTANCE
[ -d "$W/.git" ] || git clone -q /root/wt-$INSTANCE.bundle "$W"
cd "$W" && git fetch -q /root/wt-$INSTANCE.bundle HEAD && git -c advice.detachedHead=false checkout -q -f FETCH_HEAD
if [ ! -x "$W/.venv/bin/python" ]; then  # first job of this instance (or a failed setup): link shared data, uv sync
  rm -rf out && ln -s /workspace/out out
  mkdir -p umot/out third_party && ln -sfn /workspace/umot-captures umot/out/captures
  ln -sfn /root/jlm/third_party/workspace-bench third_party/workspace-bench
  export PATH="$HOME/.local/bin:$PATH" UV_CACHE_DIR=/workspace/uv-cache UV_LINK_MODE=copy
  uv sync -q
fi
LOG=/root/jobs/$INSTANCE-$JOB.log
cat > /root/jobs/$INSTANCE-$JOB.sh <<SH
#!/bin/bash
cd $W
export HF_HOME=/workspace/hf PATH=\$HOME/.local/bin:\$PATH OMP_NUM_THREADS=8
echo "[podrun] \$(date -u +%H:%M:%S) $INSTANCE/$JOB at \$(git log --oneline -1)"
# One job at a time passes the memory gate and gets GATE_HOLD seconds to allocate before the next one measures
# (six jobs released together on a 46 GB L40S all saw 10 GB free and OOMed at load, 2026-10-12).
exec 9>/root/jobs/.gpu-gate.lock
flock 9
while [ "\$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)" -lt $((NEED_GB * 1024)) ]; do
  echo "[podrun] \$(date -u +%H:%M:%S) waiting for ${NEED_GB} GB of GPU memory"; sleep 30
done
bash /root/jobs-$INSTANCE-$JOB.cmd.sh 9>&- &
pid=\$!
for _ in \$(seq 1 ${GATE_HOLD:-120}); do kill -0 \$pid 2>/dev/null || break; sleep 1; done
flock -u 9; exec 9>&-
wait \$pid
rc=\$?
[ \$rc = 0 ] && echo "JOB_DONE \$(date -u +%H:%M:%S)" || echo "JOB_FAILED rc=\$rc \$(date -u +%H:%M:%S)"
SH
{ echo "cd $W"; cat /root/jobs-$INSTANCE-$JOB.cmd; echo; } > /root/jobs-$INSTANCE-$JOB.cmd.sh
tmux kill-session -t "$INSTANCE-$JOB" 2>/dev/null || true
: > "$LOG"
tmux new -d -s "$INSTANCE-$JOB" "bash /root/jobs/$INSTANCE-$JOB.sh > $LOG 2>&1"
echo "started $INSTANCE-$JOB on $(hostname) at $(git -C $W log --oneline -1); log $LOG"
EOF
    ;;
  watch)
    INSTANCE="${1:?instance}"; JOB="${2:?job}"
    until ssh "$ALIAS" "grep -aqE '^JOB_(DONE|FAILED)' /root/jobs/$INSTANCE-$JOB.log" 2>/dev/null; do sleep 30; done
    ssh "$ALIAS" "tail -n ${LINES:-25} /root/jobs/$INSTANCE-$JOB.log" 2>/dev/null
    ;;
  stop)
    ssh "$ALIAS" "tmux kill-session -t ${1:?instance}-${2:?job} 2>/dev/null; echo \"JOB_FAILED rc=stopped \$(date -u +%H:%M:%S)\" >> /root/jobs/$1-$2.log" 2>/dev/null
    ;;
  log)
    ssh "$ALIAS" "tail -n ${3:-40} /root/jobs/${1:?instance}-${2:?job}.log" 2>/dev/null
    ;;
  status)
    ssh "$ALIAS" "nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader; \
      for l in /root/jobs/${1:-}*.log; do [ -e \"\$l\" ] || continue; s=\$(grep -aoE '^JOB_(DONE|FAILED)[^\n]*' \"\$l\" | tail -1); \
      j=\$(basename \$l .log); if [ -z \"\$s\" ]; then tmux has-session -t \"\$j\" 2>/dev/null && s=running || s='DEAD (no marker, no tmux session)'; fi; \
      echo \"\$j: \$s (last output \$(( \$(date +%s) - \$(stat -c %Y \"\$l\") ))s ago)\"; done" 2>/dev/null
    ;;
  *) sed -n 2,12p "$0"; exit 1 ;;
esac
