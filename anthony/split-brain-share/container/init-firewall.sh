#!/bin/bash
# Outbound allowlist (after Anthropic's reference devcontainer): DNS, Anthropic's API and login hosts, and the metric
# server on the Docker host. Everything else is rejected. Checks itself before handing over.
# With another model (ANTHROPIC_BASE_URL pointing at launch.sh's API proxy on the host), Anthropic's hosts are left
# out and the API proxy's port on the host is allowed instead.
set -euo pipefail
HOSTS="api.anthropic.com claude.ai platform.claude.com console.anthropic.com"
METRIC_PORT="${JLM_METRIC_URL:-${JLE_METRIC_URL:-}}"; METRIC_PORT="${METRIC_PORT##*:}"  # the per-run proxy's port (launch.sh; JLE_: --jle)
METRIC_PORT="${METRIC_PORT%%/*}"
API_PORT=""
if [ -n "${ANTHROPIC_BASE_URL:-}" ]; then
    HOSTS=""
    API_PORT="${ANTHROPIC_BASE_URL##*:}"
    API_PORT="${API_PORT%%/*}"
fi

iptables -F; iptables -X; ipset destroy allowed 2>/dev/null || true
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

ipset create allowed hash:net
for h in $HOSTS; do
    ips=$(dig +short A "$h" | grep -E '^[0-9.]+$' || true)
    [ -n "$ips" ] || { echo "firewall: cannot resolve $h" >&2; exit 1; }
    for ip in $ips; do ipset add allowed "$ip" -exist; done
done
host_ip=$(getent hosts host.docker.internal | awk '{print $1; exit}')
[ -n "$host_ip" ] || { echo "firewall: no host.docker.internal (run with --add-host)" >&2; exit 1; }

iptables -P INPUT DROP; iptables -P FORWARD DROP; iptables -P OUTPUT DROP
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
[ -z "$METRIC_PORT" ] || iptables -A OUTPUT -p tcp -d "$host_ip" --dport "$METRIC_PORT" -j ACCEPT   # none: --envs runs
[ -z "$API_PORT" ] || iptables -A OUTPUT -p tcp -d "$host_ip" --dport "$API_PORT" -j ACCEPT
iptables -A OUTPUT -m set --match-set allowed dst -j ACCEPT
iptables -A OUTPUT -j REJECT --reject-with icmp-admin-prohibited

if curl -s --max-time 5 https://example.com >/dev/null; then echo "firewall: example.com reachable" >&2; exit 1; fi
if curl -s --max-time 5 https://huggingface.co >/dev/null; then echo "firewall: huggingface.co reachable" >&2; exit 1; fi
if [ -n "$API_PORT" ]; then
    if curl -s --max-time 5 -o /dev/null https://api.anthropic.com; then echo "firewall: api.anthropic.com reachable" >&2; exit 1; fi
    curl -s --max-time 10 -o /dev/null "http://$host_ip:$API_PORT/" || { echo "firewall: API proxy unreachable" >&2; exit 1; }
    echo "firewall: up (metric server $host_ip:$METRIC_PORT, API proxy $host_ip:$API_PORT)" >&2
else
    curl -s --max-time 10 -o /dev/null https://api.anthropic.com || { echo "firewall: api.anthropic.com unreachable" >&2; exit 1; }
    echo "firewall: up (metric server $host_ip:$METRIC_PORT)" >&2
fi
