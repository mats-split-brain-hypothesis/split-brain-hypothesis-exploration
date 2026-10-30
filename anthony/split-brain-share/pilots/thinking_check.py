"""Did each run's earlier thinking reach the model? (pilots/credit-lost.md, 2026-10-23: before the api_proxy.py fix,
OpenRouter dropped it, and pilots/harness-redteam.md: in many old runs only for stretches.) From Claude Code's main
session log: after a long reply, the next request's input should grow by about the whole reply (thinking included),
not just its visible part. Also counts compactions.

    python3 thinking_check.py RUN [RUN ...]     # one line per run; exit 1 unless every run PASSes

Per reply pair (a, b): a has >= MIN_OUT output tokens and did not stop on max_tokens (Claude Code drops a truncated
tool call from the history, so b's input cannot grow by it), no compaction between a and b, and the user content
between them (tool results) is under MAX_GAP_CHARS; its ratio is (input(b) - input(a) - gap chars / 4) / output(a): carried
~1.0, dropped ~0.1-0.3. Each pair is K (carried, >= CARRIED) or d. A run PASSes with >= MIN_PAIRS pairs, no DROP_RUN
consecutive d's and at most MAX_DROPPED of them; FAILs otherwise; is UNCHECKED with too few pairs (not a pass). Also,
from api.jsonl (proxies from 2026-10-23 on), the message calls that went through a proxy without the fix.
"""

import json
import sys
from pathlib import Path

SB = Path.home() / "split-brain-run"
MIN_OUT = 1500
MAX_GAP_CHARS = 8000
CARRIED = 0.6
MIN_PAIRS = 3
DROP_RUN = 2
MAX_DROPPED = 0.25


def pairs(log: Path) -> tuple[list[float], list]:
    order, usage, gap, compacts, cut = [], {}, {}, [], set()
    pending = 0
    for line in log.open():
        x = json.loads(line)
        t = x.get("type")
        if t == "assistant":
            mid = x["message"]["id"]
            if x["message"].get("stop_reason") == "max_tokens":
                cut.add(mid)
            if mid not in usage:
                usage[mid] = x["message"].get("usage", {})
                gap[mid] = pending  # user content since the previous reply
                order.append(mid)
                pending = 0
        elif t == "user":
            pending += len(json.dumps(x.get("message", {}).get("content", "")))
        elif t == "system" and x.get("subtype") == "compact_boundary":
            compacts.append(x.get("compactMetadata", {}).get("preTokens"))
            order.append(None)
    g = lambda u, k: u.get(k) or 0
    total = lambda u: g(u, "input_tokens") + g(u, "cache_read_input_tokens") + g(u, "cache_creation_input_tokens")
    ratios = []
    for a, b in zip(order, order[1:]):
        if a is None or b is None or a in cut:
            continue
        ua, ub = usage[a], usage[b]
        if g(ua, "output_tokens") < MIN_OUT or not total(ua) or not total(ub) or gap[b] > MAX_GAP_CHARS:
            continue
        ratios.append((total(ub) - total(ua) - gap[b] / 4) / g(ua, "output_tokens"))
    return ratios, compacts


def check(run: str) -> tuple[str, str]:
    files = sorted((SB / "runs" / run / "claude" / "projects").glob("*/*.jsonl"))
    if len(files) != 1:
        return "UNCHECKED", f"{len(files)} main session logs"
    ratios, compacts = pairs(files[0])
    api = SB / "runs" / run / "api.jsonl"
    # message calls logged by a pre-fix proxy (no "stripped" field); GETs and count_tokens never carry it
    old = sum(1 for l in api.open() if '/v1/messages?' in l and '"stripped"' not in l) if api.exists() else 0
    seq = "".join("K" if r >= CARRIED else "d" for r in ratios)
    tail = f"; compactions {compacts}" + (f"; {old} api calls through the pre-fix proxy" if old else "")
    if len(ratios) < MIN_PAIRS:
        return "UNCHECKED", f"{len(ratios)} usable long replies (< {MIN_PAIRS}) {seq}{tail}"
    dropped = seq.count("d") / len(seq)
    verdict = "FAIL" if "d" * DROP_RUN in seq or dropped > MAX_DROPPED else "PASS"
    return verdict, f"{len(ratios)} long replies, {dropped:.0%} dropped: {seq}{tail}"


def main() -> None:
    bad = 0
    for run in sys.argv[1:]:
        verdict, msg = check(run)
        bad += verdict != "PASS"
        print(f"{run:32} {verdict}: {msg}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
