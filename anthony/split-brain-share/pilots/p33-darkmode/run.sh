#!/usr/bin/env bash
# p33: their Dark Mode environment (agent-interp-envs `puppeteer`, prompts verbatim) on our models.
#   bash run.sh <dsv4|q27b|glm52> <count> [tag]
# Setup (once): ~/agent-interp-envs cloned at 310c03f + aie-openrouter-base-url.patch, `uv sync`, image built with
#   docker build -f environments/puppeteer/Dockerfile -t agent-interp-envs/puppeteer:base .
#   docker network create --internal --subnet 172.31.250.0/24 --gateway 172.31.250.1 aie-int
# The container sits on the internal network (no egress, as their Modal sandbox); the harness reaches OpenRouter only
# through our api_proxy on the gateway, which holds the key (never in the container) and the Alibaba pin is in the config.
set -euo pipefail
M=$1; N=$2; TAG=${3:-$(date +%m%d-%H%M)}
SB=~/split-brain; AIE=~/agent-interp-envs; GW=172.31.250.1
case $M in dsv4) MID=deepseek/deepseek-v4-pro-0813 ;; q27b) MID=qwen/qwen3.8-27b ;; glm52) MID=z-ai/glm-5.2 ;;
  *) echo "model?" >&2; exit 2 ;; esac
OUT=~/split-brain-run/aie/p33/$M-$TAG; mkdir -p "$OUT"
PORT=$(python3 -c "import socket; s=socket.socket(); s.bind(('$GW',0)); print(s.getsockname()[1])")
python3 "$SB/container/api_proxy.py" --listen "$GW:$PORT" --key-file ~/j-lens-mean/umot/.env --provider alibaba \
    --model "$MID" --log "$OUT/api.jsonl" > "$OUT/api_proxy.log" 2>&1 &
PROXY=$!; trap 'kill $PROXY 2>/dev/null' EXIT
ENVF=$(mktemp); chmod 600 "$ENVF"
printf 'OPENROUTER_API_KEY=via-proxy\nOPENROUTER_BASE_URL=http://%s:%s/v1\n' "$GW" "$PORT" > "$ENVF"
sleep 1
cd "$AIE"
env -u ANTHROPIC_API_KEY -u OPENAI_API_KEY -u OPENROUTER_API_KEY -u FIREWORKS_API_KEY -u MINIMAX_API_KEY \
    -u MOONSHOT_API_KEY .venv/bin/python scripts/run.py "$SB/pilots/p33-darkmode/darkmode__$M.yaml" --no-build \
    --network aie-int --env-file "$ENVF" --results-dir "$OUT/results" --count "$N" --max-concurrent "$N" \
    --no-judge --timeout 7200
rm -f "$ENVF"
echo "done: $OUT"
