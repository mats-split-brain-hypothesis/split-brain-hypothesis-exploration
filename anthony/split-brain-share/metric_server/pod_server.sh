#!/bin/bash
# The 27B metric server on a RunPod pod, reached from the launching machine through an SSH tunnel on 127.0.0.1:8765
# (launch.sh's default UPSTREAM). Run on the machine that launches the subjects: pods come from j-lens-mean's
# tools/pod.sh. Default VOLUME=0: any datacenter (the shared volume's had no 80 GB card for 20 minutes on
# 2026-10-19), and the pod downloads the 27B and its lens (both public) to its container disk. VOLUME=1 uses the
# shared volume, whose HF cache already holds them.
#
#   bash pod_server.sh up        # create the pod, ship the repo (JLM_SRC), start the server, open the tunnel
#   bash pod_server.sh start     # (re)start the server on a set-up pod, then the tunnel
#   bash pod_server.sh tunnel    # reopen the tunnel (after a drop)
#   bash pod_server.sh logs      # bring the server's logs home (metric_server/logs/<run id>/, 4B: logs4b/)
#   bash pod_server.sh down      # logs, then terminate the pod
#
# RIG_TARGET=0.8 (env) turns on the server's rigged scoring for runs whose proxy asks for it (launch.sh --rig).
#
# MODEL=4b TASK=spectral (env): the jlens-edits scenario's server (jle/PLAN.md: --task spectral, reference
# persist4b-L26-30.pt, pod sb-server4b-jle unless NAME is set, logs home to logs4b-jle/); pick LPORT per pod.
# MODEL=4b (env) serves Qwen3.5-4B instead (the rig4b snapshots, p02-4b; Mac nights from 2026-10-20): the desktop
# tmux server rig4b's reference and rig flags, a 24-48 GB data-centre card, the tunnel on 127.0.0.1:8766 (the p02-4b
# launchers' UPSTREAM), pod sb-server4b, logs home to logs4b/. A second 4B pod: NAME=sb-server4b-2 LPORT=8768.
#
# Without the volume the logs live on the pod's disk only: `down` brings them home before terminating. The pod is
# tracked in ~/.jlm/pods.tsv like every other pod (instance split-brain, study SB).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
JLM_SRC="${JLM_SRC:-$HOME/j-lens-mean}"   # j-lens-mean checkout with the model registry (shipped to the pod as HEAD)
RIG_TARGET="${RIG_TARGET:-}"
if [ "${MODEL:-27b}" = 4b ]; then
    NAME="${NAME:-sb-server4b$([ "${TASK:-steer}" = spectral ] && echo -jle)}" LPORT="${LPORT:-8766}" REF=wbs4b-ddm-L20-24.pt LOGDIR=logs4b
    SERVER_ENV="JLM_MODEL=qwen4b" SERVER_ARGS="--rig-peak 20.43 --rig-base clean"
    # data-centre cards only: on a 12.x host the cu130 torch needs the CUDA compat libraries, which GeForce lacks
    export GPU_IDS="${GPU_IDS:-[\"NVIDIA A40\", \"NVIDIA L40S\", \"NVIDIA L40\", \"NVIDIA L4\", \"NVIDIA RTX A6000\", \"NVIDIA RTX 6000 Ada Generation\"]}"
    export DISK_GB="${DISK_GB:-60}"
    # no driver filter (pod.sh: any filter matched nothing on 2026-10-21); start installs the compat libraries if needed
    export CUDA_VERSIONS="${CUDA_VERSIONS:-[]}"
    if [ "${TASK:-steer}" = spectral ]; then  # the jlens-edits scenario (jle/PLAN.md): lens edits, PSL reference
        REF=persist4b-L26-30.pt LOGDIR=logs4b-jle
        SERVER_ARGS="--task spectral --rig-base clean"
    fi
else
    NAME="${NAME:-sb-server}" LPORT=8765 REF=wbs27b-ddm-L40-48.pt LOGDIR=logs SERVER_ENV="" SERVER_ARGS=""
fi
ALIAS="runpod-jlm-$NAME"
POD="bash $JLM_SRC/tools/pod.sh"
# cards: A100 80 GB or RTX PRO 6000 (96 GB) only; nothing pricier (Anthony, 2026-10-19)
# cards Anthony allowed (2026-10-19/20): A100 80 GB, RTX PRO 6000, H100 PCIe / NVL; nothing pricier
export GPU_IDS="${GPU_IDS:-[\"NVIDIA A100-SXM4-80GB\", \"NVIDIA A100 80GB PCIe\", \"NVIDIA RTX PRO 6000 Blackwell Server Edition\", \"NVIDIA RTX PRO 6000 Blackwell Workstation Edition\", \"NVIDIA H100 PCIe\", \"NVIDIA H100 NVL\"]}"
export TRIES="${TRIES:-40}"
export VOLUME="${VOLUME:-0}" DISK_GB="${DISK_GB:-150}"
# any host driver from CUDA 12.8; a 12.x host gets NVIDIA's CUDA 13 compat libraries (start)
export CUDA_VERSIONS="${CUDA_VERSIONS:-[\"12.8\", \"12.9\", \"13.0\"]}"
if [ "$VOLUME" = 0 ]; then export POD_HF_HOME=/root/hf; LOGS=/root/sb-logs; else export POD_HF_HOME=/workspace/hf; LOGS=/workspace/sb-logs; fi

tunnel() {
    pkill -f "ssh -f -N -L 127.0.0.1:$LPORT:localhost:8765 $ALIAS" 2>/dev/null || true
    ssh -f -N -o ExitOnForwardFailure=yes -L 127.0.0.1:$LPORT:localhost:8765 "$ALIAS"
    curl -s --max-time 20 http://127.0.0.1:$LPORT/info | python3 -c 'import json, sys; i = json.load(sys.stdin); print("tunnel up:", i["model"], i["baseline"])'
}

case "${1:-}" in
  up)
    (cd "$JLM_SRC" && INSTANCE=split-brain STUDY=SB GPU=capture $POD create "$NAME" && $POD ssh-config "$NAME" && $POD setup "$NAME")
    bash "$0" start
    ;;
  start)  # (after up's create + setup) CUDA forward compat on a 12.x host, then the server and the tunnel
    # data-centre cards run the venv's cu130 torch on a 12.x driver through NVIDIA's compat libraries
    ssh "$ALIAS" 'drv=$(nvidia-smi | grep -o "CUDA Version: [0-9.]*" | grep -o "[0-9.]*$"); echo "driver CUDA $drv"
        if [ "${drv%%.*}" -lt 13 ]; then
            apt-get update -qq >/dev/null 2>&1; DEBIAN_FRONTEND=noninteractive apt-get install -y -qq cuda-compat-13-0 >/dev/null
            echo /usr/local/cuda-13.0/compat > /root/ld-extra
        else : > /root/ld-extra; fi
        LD_LIBRARY_PATH=$(cat /root/ld-extra) /root/jlm/.venv/bin/python -c "import torch; print(torch.__version__, torch.cuda.get_device_name(0))"'
    ssh "$ALIAS" mkdir -p /root/metric_server "$LOGS"
    scp -q "$HERE/server.py" "$HERE/$REF" "$ALIAS":/root/metric_server/
    ssh "$ALIAS" "tmux new -d -s server 'cd /root/metric_server && LD_LIBRARY_PATH=\$(cat /root/ld-extra) HF_HOME=$POD_HF_HOME JLM_REPO=/root/jlm JLM_HF_AUTOPUSH=0 $SERVER_ENV \
        OMP_NUM_THREADS=8 /root/jlm/.venv/bin/python server.py --device cuda --run-id default --log-root $LOGS \
        --reference $REF $SERVER_ARGS ${RIG_TARGET:+--rig-target $RIG_TARGET} 2>&1 | tee server.log'"
    for _ in $(seq 1 120); do  # first start downloads the model (27B ~55 GB, 4B ~9 GB)
        ssh "$ALIAS" 'grep -qE "listening|Traceback" /root/metric_server/server.log 2>/dev/null' && break
        sleep 20
    done
    ssh "$ALIAS" 'grep -E "ready|listening|Error" /root/metric_server/server.log | tail -3'
    tunnel
    ;;
  tunnel) tunnel ;;
  logs)
    # the pod's own info.json / default/ go to $LOGDIR-pods/<name>/: in $LOGDIR they would overwrite the local server's
    mkdir -p "$HERE/$LOGDIR" "$HERE/$LOGDIR-pods/$NAME"
    rsync -a --exclude /info.json --exclude /default/ "$ALIAS:$LOGS/" "$HERE/$LOGDIR/"
    rsync -a --include /info.json --include '/default/***' --exclude '*' "$ALIAS:$LOGS/" "$HERE/$LOGDIR-pods/$NAME/"
    ls "$HERE/$LOGDIR" | tail -5
    ;;
  down)
    bash "$0" logs || { echo "logs did not come home: $NAME NOT terminated (retry: pod_server.sh down)" >&2; exit 1; }
    pkill -f "ssh -f -N -L 127.0.0.1:$LPORT:localhost:8765 $ALIAS" 2>/dev/null || true
    (cd "$JLM_SRC" && $POD terminate "$NAME")
    ;;
  *) sed -n 2,11p "$0"; exit 1 ;;
esac
