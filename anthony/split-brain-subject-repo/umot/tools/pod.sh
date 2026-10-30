#!/bin/bash
# RunPod lifecycle through the REST API (recipe from the sibling fisher-jlens / jlens-edits work).
#   bash tools/pod.sh list                 # always run before create: never double-bill
#   bash tools/pod.sh create               # A100 80 GB, CUDA >= 13, retries while none free
#   bash tools/pod.sh ssh-config <pod-id>  # wait for IP/port, write ~/.ssh/config.d/$POD_ALIAS
#   bash tools/pod.sh stop <pod-id> | terminate <pod-id>
# The alias is per project (POD_ALIAS, default runpod-um): `Host runpod` is shared by other
# projects' sessions and gets rewritten under you. ~/.ssh/config must `Include config.d/*`.
# Needs ~/.runpod/config.toml (apikey = '...') and an SSH key pair. POD_PUBKEY is the PUBLIC key
# sent to the pod; never point it at a private key.
set -euo pipefail
API=https://rest.runpod.io/v1
KEY=$(grep apikey ~/.runpod/config.toml | sed "s/.*= *['\"]\{0,1\}\([^'\"]*\)['\"]\{0,1\}.*/\1/")
[ -n "$KEY" ] || { echo "no apikey in ~/.runpod/config.toml" >&2; exit 1; }
POD_PUBKEY="${POD_PUBKEY:-$HOME/.ssh/id_ed25519.pub}"
POD_NAME="${POD_NAME:-UM-A100}"
POD_ALIAS="${POD_ALIAS:-runpod-um}"
DISK_GB="${DISK_GB:-200}"
api() { curl -s -X "$1" "$API$2" -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" "${@:3}"; }

case "${1:-}" in
  list)
    api GET /pods | python3 -c '
import json, sys
for p in json.load(sys.stdin):
    print(p["id"], p.get("name"), p.get("desiredStatus"), p.get("costPerHr"), p.get("publicIp"), p.get("portMappings"))'
    ;;
  create)
    case "$POD_PUBKEY" in *.pub) ;; *) echo "POD_PUBKEY must be a .pub file" >&2; exit 1 ;; esac
    BODY=$(python3 - "$POD_NAME" "$DISK_GB" "$POD_PUBKEY" <<'EOF'
import json, sys
name, disk, pub = sys.argv[1], int(sys.argv[2]), open(sys.argv[3]).read().strip()
assert pub.startswith("ssh-") and "PRIVATE" not in pub
print(json.dumps({
    "name": name,
    "imageName": "runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404",
    "cloudType": "SECURE",
    "gpuTypeIds": ["NVIDIA A100-SXM4-80GB", "NVIDIA A100 80GB PCIe"],
    "gpuCount": 1,
    "containerDiskInGb": disk,
    "ports": ["8888/http", "22/tcp"],
    "env": {"PUBLIC_KEY": pub},
    "allowedCudaVersions": ["13.0"],
}))
EOF
)
    for attempt in $(seq 1 "${TRIES:-20}"); do
      OUT=$(api POST /pods -d "$BODY")
      ID=$(echo "$OUT" | python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("id",""))
except Exception: print("")')
      if [ -n "$ID" ]; then echo "created $ID (attempt $attempt)"; exit 0; fi
      echo "attempt $attempt: $(echo "$OUT" | head -c 200)"; sleep 30
    done
    exit 1
    ;;
  ssh-config)
    ID="${2:?pod id}"
    for _ in $(seq 1 60); do
      read -r IP PORT < <(api GET "/pods/$ID" | python3 -c '
import json, sys
p = json.load(sys.stdin)
print(p.get("publicIp") or "", (p.get("portMappings") or {}).get("22", ""))')
      if [ -n "$IP" ] && [ -n "$PORT" ]; then break; fi
      sleep 10
    done
    [ -n "${IP:-}" ] && [ -n "${PORT:-}" ] || { echo "no public IP/port yet" >&2; exit 1; }
    mkdir -p ~/.ssh/config.d
    cat > ~/.ssh/config.d/"$POD_ALIAS" <<EOF
Host $POD_ALIAS
    HostName $IP
    Port $PORT
    User root
    IdentityFile ${POD_PUBKEY%.pub}
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
EOF
    echo "Host $POD_ALIAS -> $IP:$PORT (~/.ssh/config.d/$POD_ALIAS)"
    ;;
  stop) api POST "/pods/${2:?pod id}/stop" | head -c 300; echo ;;
  terminate) api DELETE "/pods/${2:?pod id}" | head -c 300; echo; bash "$0" list ;;
  *) sed -n 2,8p "$0"; exit 1 ;;
esac
