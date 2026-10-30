#!/bin/bash
# Whitebox captures on a RunPod pod: Qwen3.8-27B teacher-forced over each target's sequence (capture.py), the
# results home to ~/split-brain-run/whitebox-captures/<target>/ as each target ends. Pods from j-lens-mean's
# tools/pod.sh as pod_server.sh does (instance split-brain, study SB, no network volume: the prompts hold the
# partner's material and stay on the pod's container disk, gone with the pod).
#
#   bash capture_pod.sh up                # create (allowed cards only), ssh config, setup (JLM_SRC venv), fla kernels
#   bash capture_pod.sh start T1 T2 ...   # ship capture.py + each out/<T>/{prompt-full.txt,capture.json}, run in tmux
#   bash capture_pod.sh status            # the pod's log tail and which targets are done
#   bash capture_pod.sh fetch             # rsync finished targets home (run again until all are home)
#   bash capture_pod.sh readers STEP T... # readers_pod.py STEP (jlens | r0 | r0lens | meta | vstates | dense), tmux "rd-STEP" (log rd.log)
#   bash capture_pod.sh fetch-readers     # rsync out/<T>/{readers,r0}/ home (not states/)
#   bash capture_pod.sh resample T...    # resample_pod.py on each target (RESAMPLE.md), tmux "rs" (log rs.log); N=20,
#                                         # CUTS=c4 (only those cuts), RS=rs2 (another session: waits for "rs" to end)
#   bash capture_pod.sh fetch-resample    # rsync out/<T>/resample/ home to whitebox/out/<T>/resample/
#   bash capture_pod.sh down             # bring every result dir home, check nothing is pending, then terminate
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
JLM_SRC="${JLM_SRC:-$HOME/jlm-hm6}"
NAME="${NAME:-sb-whitebox}" ALIAS="runpod-jlm-${NAME:-sb-whitebox}"
POD="bash $JLM_SRC/tools/pod.sh"
HOME_DIR="${HOME_DIR:-$HOME/split-brain-run/whitebox-captures}"
REV=1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0   # Qwen/Qwen3.8-27B, the local tokenizer's snapshot (render.py)
# cards Anthony allowed (2026-10-19/20): A100 80 GB, RTX PRO 6000, H100 PCIe / NVL; nothing pricier. 96 GB first.
export GPU_IDS="${GPU_IDS:-[\"NVIDIA RTX PRO 6000 Blackwell Server Edition\", \"NVIDIA RTX PRO 6000 Blackwell Workstation Edition\", \"NVIDIA A100-SXM4-80GB\", \"NVIDIA A100 80GB PCIe\", \"NVIDIA H100 PCIe\", \"NVIDIA H100 NVL\"]}"
export TRIES="${TRIES:-40}" VOLUME=0 DISK_GB="${DISK_GB:-350}" POD_HF_HOME=/root/hf
# no driver filter: with one, nothing matched (pod_server.sh 4B note 2026-10-21; 60 attempts here 2026-10-23); up installs
# the CUDA 13 compat libraries on a 12.x host
export CUDA_VERSIONS="${CUDA_VERSIONS:-[]}"

case "${1:-}" in
  up)
    (cd "$JLM_SRC" && INSTANCE=split-brain STUDY=SB GPU=capture $POD create "$NAME" && $POD ssh-config "$NAME" && $POD setup "$NAME")
    # CUDA 13 compat libraries on a 12.x host (pod_server.sh start); fla's triton kernels for the linear-attention layers
    ssh "$ALIAS" 'drv=$(nvidia-smi | grep -o "CUDA Version: [0-9.]*" | grep -o "[0-9.]*$"); echo "driver CUDA $drv"
        if [ "${drv%%.*}" -lt 13 ]; then
            apt-get update -qq >/dev/null 2>&1; DEBIAN_FRONTEND=noninteractive apt-get install -y -qq cuda-compat-13-0 >/dev/null
            echo /usr/local/cuda-13.0/compat > /root/ld-extra
        else : > /root/ld-extra; fi
        export PATH="$HOME/.local/bin:$PATH" UV_CACHE_DIR=/root/uv-cache UV_LINK_MODE=copy
        cd /root/jlm && (uv pip install -q --python .venv/bin/python flash-linear-attention || echo "fla install failed: torch fallback")
        LD_LIBRARY_PATH=$(cat /root/ld-extra) .venv/bin/python -c "import torch; print(torch.__version__, torch.cuda.get_device_name(0))"'
    ;;
  start)
    shift
    [ $# -gt 0 ] || { echo "targets?" >&2; exit 1; }
    ssh "$ALIAS" mkdir -p /root/wb/out
    scp -q "$HERE/capture.py" "$ALIAS":/root/wb/
    for t in "$@"; do
        ssh "$ALIAS" mkdir -p "/root/wb/out/$t"
        scp -q "$HERE/out/$t/prompt-full.txt" "$HERE/out/$t/capture.json" "$ALIAS:/root/wb/out/$t/"
    done
    # the first target also runs the chunking check (8192 tokens, one pass vs chunks of 2048)
    ssh "$ALIAS" "cat > /root/wb/go.sh" <<EOF
set -u
cd /root/wb
first=1
for t in $*; do
    [ -f out/\$t/capture/meta.json ] && continue
    chk=""; [ \$first = 1 ] && chk="--check-chunking 8192"; first=0
    echo "=== \$t \$(date -u +%H:%M:%S)"
    LD_LIBRARY_PATH=\$(cat /root/ld-extra) HF_HOME=/root/hf OMP_NUM_THREADS=8 /root/jlm/.venv/bin/python capture.py out/\$t \
        --revision $REV --chunk 2048 \$chk 2>&1 | grep -v -E "Loading weights|Warning"
    echo "=== \$t ended \$? \$(date -u +%H:%M:%S)"
done
echo ALL_DONE
EOF
    ssh "$ALIAS" "tmux new -d -s wb 'bash /root/wb/go.sh 2>&1 | tee -a /root/wb/go.log'"
    echo "started: $*"
    ;;
  readers)
    step="$2"; shift 2
    ssh "$ALIAS" mkdir -p /root/wb/out
    scp -q "$HERE/capture.py" "$HERE/readers_pod.py" "$ALIAS":/root/wb/
    for t in "$@"; do
        ssh "$ALIAS" mkdir -p "/root/wb/out/$t"
        scp -q "$HERE/out/$t/prompt-full.txt" "$HERE/out/$t/capture.json" "$ALIAS:/root/wb/out/$t/"
        [ -f "$HERE/out/$t/positions.json" ] && scp -q "$HERE/out/$t/positions.json" "$ALIAS:/root/wb/out/$t/"
        for x in positions_dense.json states_dense variants; do  # the dense read's inputs (dense.py, variants.py)
            [ -e "$HERE/out/$t/$x" ] && rsync -a "$HERE/out/$t/$x" "$ALIAS:/root/wb/out/$t/"
        done
    done
    ssh "$ALIAS" "tmux new -d -s rd-$step 'cd /root/wb && LD_LIBRARY_PATH=\$(cat /root/ld-extra) HF_HOME=/root/hf OMP_NUM_THREADS=8 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
        /root/jlm/.venv/bin/python readers_pod.py $step $* 2>&1 | grep --line-buffered -v -E \"Loading weights|Warning\" | tee -a rd.log; echo RD_DONE $step | tee -a rd.log'"
    echo "readers $step started: $*"
    ;;
  fetch-readers)
    mkdir -p "$HOME_DIR"
    for t in $(ssh "$ALIAS" 'ls /root/wb/out'); do
        for sub in readers r0; do
            ssh "$ALIAS" "test -d /root/wb/out/$t/$sub" && rsync -a --partial "$ALIAS:/root/wb/out/$t/$sub/" "$HOME_DIR/$t/$sub/" && echo "home: $t/$sub"
        done
    done
    for f in meta.jsonl meta_checks.json meta_dense.jsonl meta_dense_checks.json; do scp -q "$ALIAS:/root/wb/out/$f" "$HOME_DIR/$f" 2>/dev/null && echo "home: $f"; done
    scp -q "$ALIAS:/root/wb/rd.log" "$HOME_DIR/rd-$NAME.log" || true
    ;;
  resample)
    shift
    [ $# -gt 0 ] || { echo "targets?" >&2; exit 1; }
    ssh "$ALIAS" mkdir -p /root/wb/out
    scp -q "$HERE/resample_pod.py" "$ALIAS":/root/wb/
    for t in "$@"; do
        ssh "$ALIAS" mkdir -p "/root/wb/out/$t/resample"
        scp -q "$HERE/out/$t/prompt-full.txt" "$ALIAS:/root/wb/out/$t/"
        scp -q "$HERE/out/$t/resample/cuts.json" "$ALIAS:/root/wb/out/$t/resample/"
    done
    RS="${RS:-rs}"
    ssh "$ALIAS" "cat > /root/wb/$RS.sh" <<EOF
set -u
cd /root/wb
[ "$RS" != rs ] && while tmux has-session -t =rs 2>/dev/null; do sleep 30; done
for t in $*; do
    echo "=== \$t \$(date -u +%H:%M:%S)"
    LD_LIBRARY_PATH=\$(cat /root/ld-extra) HF_HOME=/root/hf OMP_NUM_THREADS=8 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
        /root/jlm/.venv/bin/python resample_pod.py out/\$t --revision $REV --n ${N:-20} ${CUTS:+--cuts $CUTS} 2>&1 | grep --line-buffered -v -E "Loading weights|Warning"
    echo "=== \$t ended \$(date -u +%H:%M:%S)"
done
echo RS_DONE
EOF
    ssh "$ALIAS" "tmux new -d -s $RS 'bash /root/wb/$RS.sh 2>&1 | tee -a /root/wb/rs.log'"
    echo "resample started: $*"
    ;;
  fetch-resample)
    for t in $(ssh "$ALIAS" 'ls /root/wb/out'); do
        if ssh "$ALIAS" "test -d /root/wb/out/$t/resample"; then
            rsync -a --partial "$ALIAS:/root/wb/out/$t/resample/" "$HERE/out/$t/resample/"
            echo "home: $t/resample ($(cat "$HERE/out/$t/resample/"*.jsonl 2>/dev/null | wc -l) samples)"
        fi
    done
    scp -q "$ALIAS:/root/wb/rs.log" "$HOME_DIR/rs-$NAME.log" || true
    ;;
  status)
    ssh "$ALIAS" 'tail -4 /root/wb/rs.log 2>/dev/null'
    ssh "$ALIAS" 'tail -6 /root/wb/go.log; ls /root/wb/out/*/capture/meta.json 2>/dev/null; df -h /root | tail -1; nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader'
    ;;
  fetch)
    mkdir -p "$HOME_DIR"
    for m in $(ssh "$ALIAS" 'ls /root/wb/out/*/capture/meta.json 2>/dev/null'); do
        t=$(basename "$(dirname "$(dirname "$m")")")
        rsync -a --partial "$ALIAS:/root/wb/out/$t/capture/" "$HOME_DIR/$t/"
        echo "home: $t ($(du -sh "$HOME_DIR/$t" | cut -f1))"
    done
    scp -q "$ALIAS:/root/wb/go.log" "$HOME_DIR/go-$NAME.log" || true
    ;;
  down)
    # every result dir on the pod (capture/, readers/, r0/; not states/, which is a recomputable cache) must be home
    for d in $(ssh "$ALIAS" 'cd /root/wb/out && ls -d */capture */readers */r0 */resample 2>/dev/null'); do
        t=${d%%/*} sub=${d#*/}; [ "$sub" = capture ] && dst="$HOME_DIR/$t/" || dst="$HOME_DIR/$t/$sub/"
        [ "$sub" = resample ] && dst="$HERE/out/$t/resample/"
        rsync -a --partial "$ALIAS:/root/wb/out/$d/" "$dst"
        n=$(rsync -a --dry-run --itemize-changes "$ALIAS:/root/wb/out/$d/" "$dst" | grep -vc '^\.d' || true)
        [ "$n" = 0 ] || { echo "$d not fully home: $NAME NOT terminated" >&2; exit 1; }
        echo "home: $d"
    done
    scp -q "$ALIAS:/root/wb/go.log" "$HOME_DIR/go-$NAME.log" 2>/dev/null || true
    scp -q "$ALIAS:/root/wb/rd.log" "$HOME_DIR/rd-$NAME.log" 2>/dev/null || true
    scp -q "$ALIAS:/root/wb/rs.log" "$HOME_DIR/rs-$NAME.log" 2>/dev/null || true
    (cd "$JLM_SRC" && $POD terminate "$NAME")
    ;;
  *) sed -n 2,13p "$0"; exit 1 ;;
esac
