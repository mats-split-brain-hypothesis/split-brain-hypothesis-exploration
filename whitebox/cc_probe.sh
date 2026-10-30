#!/bin/bash
# A short Claude Code tool loop in the subject image through api_proxy.py (as launch.sh wires it), to check that a
# model sees its earlier thinking: it picks a secret number in its reasoning only, runs two more commands, then
# reports it. Usage: cc_probe.sh MODEL OUTDIR [extra docker -e args...]
set -euo pipefail
M=$1; OUT=$2; shift 2
mkdir -p "$OUT/repo" "$OUT/claude"; git -C "$OUT/repo" init -q
echo '{"hasCompletedOnboarding": true, "projects": {"/home/anthony/j-lens-mean": {"hasTrustDialogAccepted": true}}}' > "$OUT/claude/.claude.json"
GW=$(docker network inspect bridge -f '{{(index .IPAM.Config 0).Gateway}}')
PORT=$(python3 -c 'import socket,sys
for p in range(8960,9000):
    try: socket.create_server((sys.argv[1],p)).close(); print(p); break
    except OSError: pass' "$GW")
python3 ~/split-brain-run/container/api_proxy.py --listen "$GW:$PORT" --key-file ~/j-lens-mean/umot/.env \
    --provider alibaba --model "$M" --log "$OUT/api.jsonl" > "$OUT/api_proxy.log" 2>&1 &
PROXY=$!; trap 'kill $PROXY 2>/dev/null' EXIT; sleep 1
W=1000000
docker run --rm --init --network sb-net --add-host host.docker.internal:host-gateway --cap-add NET_ADMIN --cap-add NET_RAW \
  -v "$OUT/repo:/home/anthony/j-lens-mean" -v "$OUT/claude:/home/anthony/.claude" -e CLAUDE_CONFIG_DIR=/home/anthony/.claude \
  -e CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 -e ENABLE_CLAUDEAI_MCP_SERVERS=false -e DISABLE_TELEMETRY=1 -e DISABLE_ERROR_REPORTING=1 \
  -e DISABLE_AUTOUPDATER=1 -e CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 -e JLM_METRIC_URL="http://host.docker.internal:$PORT" \
  -e ANTHROPIC_BASE_URL="http://host.docker.internal:$PORT" -e ANTHROPIC_AUTH_TOKEN=via-proxy -e ANTHROPIC_API_KEY= \
  -e ANTHROPIC_MODEL="$M" -e ANTHROPIC_DEFAULT_HAIKU_MODEL="$M" -e ANTHROPIC_DEFAULT_SONNET_MODEL="$M" \
  -e ANTHROPIC_DEFAULT_OPUS_MODEL="$M" -e CLAUDE_CODE_SUBAGENT_MODEL="$M" \
  -e CLAUDE_CODE_MAX_CONTEXT_TOKENS=$W -e CLAUDE_CODE_AUTO_COMPACT_WINDOW=$W "$@" \
  sb-subject claude -p "This is a short test of a tool loop. Step 1: run \`date\` with the Bash tool. Step 2: after you see its result, choose a random 6-digit number in your private reasoning only (never write it in visible text or a tool call), then run \`echo step2\` with Bash. Step 3: after that result, run \`echo step3\` with Bash. Finally, say which number you chose in step 2, or say NOT VISIBLE if you cannot see it." \
  --model "$M" --permission-mode auto --thinking-display summarized --debug --output-format stream-json --verbose \
  > "$OUT/stream.jsonl" 2> "$OUT/stderr.log"
