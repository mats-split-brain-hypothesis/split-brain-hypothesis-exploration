#!/bin/bash
# RunPod pods on the shared network volume jlm-shared (US-MO-1), for every instance of the loop.
#   bash tools/pod.sh list                          # all pods on the account: run before create
#   INSTANCE=j-lens-mean-f3 STUDY=S1 GPU=eval bash tools/pod.sh create <name>   # GPU=capture (80 GB) | eval (>= 48 GB)
#   bash tools/pod.sh ssh-config <name>             # waits for the pod, writes ~/.ssh/config.d/runpod-jlm-<name>
#   bash tools/pod.sh setup <name>                  # ship HEAD as a bundle, uv sync, link out/ to the volume
#   bash tools/pod.sh terminate <name>              # terminate and log the spend to ~/.jlm/ledger.tsv
#
# On the pod: OMP_NUM_THREADS=8 is set in the pod's environment (unset, torch's small CPU ops oversubscribe
# every core and crawl: a 13-minute capture check, 2026-10-10). The repo is /root/jlm (container disk), its out/ is a symlink to /workspace/out (the volume, shared
# by every pod), HF_HOME=/workspace/hf (27B shards and the lens, downloaded once). Run jobs inside tmux.
# Bring results home with tools/sync.sh. Pods are tracked in ~/.jlm/pods.tsv (name, id, start, $/h, instance,
# study), so terminate can compute what the pod cost. The instance that creates a pod owns its termination.
set -euo pipefail
cd "$(dirname "$0")/.."
API=https://rest.runpod.io/v1
VOLUME_ID=${VOLUME_ID:-}
DATACENTER=US-MO-1
KEY=$(grep apikey ~/.runpod/config.toml | sed "s/.*= *['\"]\{0,1\}\([^'\"]*\)['\"]\{0,1\}.*/\1/")
[ -n "$KEY" ] || { echo "no apikey in ~/.runpod/config.toml" >&2; exit 1; }
POD_PUBKEY="${POD_PUBKEY:-$HOME/.ssh/id_ed25519.pub}"
PODS=~/.jlm/pods.tsv
mkdir -p ~/.jlm
api() { curl -s -X "$1" "$API$2" -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" "${@:3}"; }
pod_id() { awk -F'\t' -v n="$1" '$1 == n {id = $2} END {print id}' "$PODS" 2>/dev/null; }

case "${1:-}" in
  list)
    api GET /pods | python3 -c '
import json, sys
for p in json.load(sys.stdin):
    print(p["id"], p.get("name"), p.get("desiredStatus"), p.get("costPerHr"), p.get("networkVolumeId") or "-")'
    ;;
  create)
    NAME="${2:?pod name}"
    : "${INSTANCE:?set INSTANCE (your ListAgents name)}" "${STUDY:?set STUDY}"
    case "${GPU:-eval}" in
      capture) GPUS='["NVIDIA A100-SXM4-80GB", "NVIDIA A100 80GB PCIe", "NVIDIA H100 80GB HBM3"]' ;;
      eval) GPUS='["NVIDIA L40S", "NVIDIA A100 80GB PCIe", "NVIDIA A100-SXM4-80GB", "NVIDIA H100 80GB HBM3"]' ;;
      *) echo "GPU must be capture or eval" >&2; exit 1 ;;
    esac
    [ -n "${GPU_IDS:-}" ] && GPUS="$GPU_IDS"  # override, e.g. GPU_IDS='["NVIDIA H100 80GB HBM3"]' to avoid a bad machine
    BODY=$(python3 - "jlm-$NAME" "$POD_PUBKEY" "$GPUS" "$VOLUME_ID" "$DATACENTER" <<'EOF'
import json, sys
name, pub, gpus, vol, dc = sys.argv[1], open(sys.argv[2]).read().strip(), json.loads(sys.argv[3]), sys.argv[4], sys.argv[5]
assert pub.startswith("ssh-") and "PRIVATE" not in pub
print(json.dumps({
    "name": name, "imageName": "runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404", "cloudType": "SECURE",
    "gpuTypeIds": gpus, "gpuTypePriority": "custom", "gpuCount": 1, "containerDiskInGb": 80,
    "networkVolumeId": vol, "volumeMountPath": "/workspace", "dataCenterIds": [dc],
    "ports": ["22/tcp"], "env": {"PUBLIC_KEY": pub, "OMP_NUM_THREADS": "8"}, "allowedCudaVersions": ["13.0"],
}))
EOF
)
    for attempt in $(seq 1 "${TRIES:-20}"); do
      OUT=$(api POST /pods -d "$BODY")
      read -r ID COST < <(echo "$OUT" | python3 -c 'import json,sys
try: p = json.load(sys.stdin); print(p.get("id") or "-", p.get("costPerHr", 0))
except Exception: print("-", 0)')
      if [ "$ID" != "-" ]; then
        printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$NAME" "$ID" "$(date +%s)" "$COST" "$INSTANCE" "$STUDY" >> "$PODS"
        python3 tools/board.py set "$INSTANCE" pod_id="$ID" status=pod-job >/dev/null
        echo "created $NAME = $ID at \$$COST/h (attempt $attempt)"; exit 0
      fi
      echo "attempt $attempt: $(echo "$OUT" | head -c 200)"; sleep 30
    done
    exit 1
    ;;
  ssh-config)
    NAME="${2:?pod name}"; ID=$(pod_id "$NAME"); ALIAS="runpod-jlm-$NAME"
    [ -n "$ID" ] || { echo "no pod $NAME in $PODS" >&2; exit 1; }
    for _ in $(seq 1 60); do
      read -r IP PORT < <(api GET "/pods/$ID" | python3 -c '
import json, sys
p = json.load(sys.stdin)
print(p.get("publicIp") or "-", (p.get("portMappings") or {}).get("22", "-"))')
      [ "$IP" != "-" ] && [ "$PORT" != "-" ] && break
      sleep 10
    done
    [ "$IP" != "-" ] || { echo "no public IP yet" >&2; exit 1; }
    mkdir -p ~/.ssh/config.d
    cat > ~/.ssh/config.d/"$ALIAS" <<EOF
Host $ALIAS
    HostName $IP
    Port $PORT
    User root
    IdentityFile ${POD_PUBKEY%.pub}
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
    ServerAliveInterval 30
EOF
    echo "$ALIAS -> $IP:$PORT"
    ;;
  setup)
    NAME="${2:?pod name}"; ALIAS="runpod-jlm-$NAME"
    BUNDLE=$(mktemp -d)/jlm.bundle
    git bundle create -q "$BUNDLE" HEAD
    for _ in $(seq 1 30); do ssh -o ConnectTimeout=10 "$ALIAS" true 2>/dev/null && break; sleep 10; done
    scp -q "$BUNDLE" "$ALIAS":/root/jlm.bundle
    ssh "$ALIAS" 'bash -s' <<'EOF'
set -e
rm -rf /root/jlm && git clone -q /root/jlm.bundle /root/jlm && cd /root/jlm
mkdir -p /workspace/out /workspace/hf /workspace/uv-cache
rm -rf out && ln -s /workspace/out out
mkdir -p /workspace/umot-captures umot/out && ln -sfn /workspace/umot-captures umot/out/captures  # umot's bench captures (LEGACY)
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null
export PATH="$HOME/.local/bin:$PATH" UV_CACHE_DIR=/workspace/uv-cache UV_LINK_MODE=copy
WSBENCH_COMMIT=92d763e722377f5bfae045e829a308ab5919a820
[ -d third_party/workspace-bench/.git ] || { rm -rf third_party/workspace-bench; git clone -q https://github.com/camilablank/workspace-bench third_party/workspace-bench; }
git -C third_party/workspace-bench checkout -q "$WSBENCH_COMMIT"
uv sync -q
cat >> ~/.bashrc <<'RC'
export PATH="$HOME/.local/bin:$PATH" HF_HOME=/workspace/hf UV_CACHE_DIR=/workspace/uv-cache UV_LINK_MODE=copy OMP_NUM_THREADS=8
cd /root/jlm
RC
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
echo SETUP_OK
EOF
    ;;
  terminate)
    NAME="${2:?pod name}"; ID=$(pod_id "$NAME")
    [ -n "$ID" ] || { echo "no pod $NAME in $PODS" >&2; exit 1; }
    api DELETE "/pods/$ID" | head -c 300; echo
    read -r START COST INSTANCE STUDY < <(awk -F'\t' -v n="$NAME" '$1 == n {s=$3; c=$4; i=$5; t=$6} END {print s, c, i, t}' "$PODS")
    USD=$(python3 -c "import time; print(round(($(date +%s) - $START) / 3600 * $COST, 2))")
    printf '%s\t%s\tTERMINATED\n' "$NAME" "$ID" >> "$PODS"
    python3 tools/board.py spend "$INSTANCE" "$STUDY" pod "$USD" --note "pod $NAME $ID"
    python3 tools/board.py set "$INSTANCE" pod_id= >/dev/null
    rm -f ~/.ssh/config.d/"runpod-jlm-$NAME"
    bash "$0" list
    ;;
  *) sed -n 2,13p "$0"; exit 1 ;;
esac
