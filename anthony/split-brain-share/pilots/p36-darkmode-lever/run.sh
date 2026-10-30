#!/usr/bin/env bash
# p36: the Dark Mode lever (p33's environment and config, one sentence of the prompt changed per arm), DeepSeek only.
#   bash run.sh <ci|compare|look|smoke-ci|smoke-compare|smoke-look> <count>
# Written for the Mac (Colima): the containers sit on an --internal docker network (no egress), and the API proxy
# must listen on that network's gateway, which exists only inside the Colima VM. So the proxy runs in the VM
# (`colima ssh`), reading the key over Colima's home mount: the key is never copied and never enters a container.
# On the desktop (Linux) set PROXY_MODE=host to run the proxy on the host as p33 did.
set -euo pipefail
ARM=$1; N=$2
case $ARM in ci|smoke-ci) CFG=ci; PORT=18761 ;; compare|smoke-compare) CFG=compare; PORT=18762 ;; look|smoke-look) CFG=look; PORT=18763 ;;
  *) echo "arm?" >&2; exit 2 ;; esac
SB=~/split-brain; AIE=~/agent-interp-envs; GW=172.31.250.1; MID=deepseek/deepseek-v4-pro-0813
OUT=~/split-brain-run/aie/p36/dsv4-$ARM; mkdir -p "$OUT"
PROXY_CMD=(python3 "$SB/container/api_proxy.py" --listen "$GW:$PORT" --key-file "$HOME/j-lens-mean/umot/.env"
           --provider alibaba --model "$MID" --log "$OUT/api.jsonl")
if [ "${PROXY_MODE:-colima}" = colima ]; then
  colima ssh -- "${PROXY_CMD[@]}" > "$OUT/api_proxy.log" 2>&1 &
else
  "${PROXY_CMD[@]}" > "$OUT/api_proxy.log" 2>&1 &
fi
PROXY=$!; trap 'kill $PROXY 2>/dev/null; [ "${PROXY_MODE:-colima}" = colima ] && colima ssh -- pkill -f "[a]pi_proxy.py --listen $GW:$PORT" || true' EXIT
ENVF=$(mktemp); chmod 600 "$ENVF"
printf 'OPENROUTER_API_KEY=via-proxy\nOPENROUTER_BASE_URL=http://%s:%s/v1\n' "$GW" "$PORT" > "$ENVF"
sleep 3
cd "$AIE"
env -u ANTHROPIC_API_KEY -u OPENAI_API_KEY -u OPENROUTER_API_KEY -u FIREWORKS_API_KEY -u MINIMAX_API_KEY \
    -u MOONSHOT_API_KEY .venv/bin/python scripts/run.py "$SB/pilots/p36-darkmode-lever/darkmode__dsv4-$CFG.yaml" --no-build \
    --network aie-int --env-file "$ENVF" --results-dir "$OUT/results" --count "$N" --max-concurrent "$N" \
    --no-judge --timeout 7200
rm -f "$ENVF"
echo "done: $OUT"
