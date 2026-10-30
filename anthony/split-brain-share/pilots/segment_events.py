"""Segment-label shares before / after a run's events (first opened the planted paper, first scored metric call
(metric1), first metric call shown pass@10 >= 0.50 (pass50; server calls, not the submission),
first submit, first contribution.md write), from segments/<model>/<run>.jsonl (segment_labels.py).

    python3 segment_events.py RUN [RUN ...] [--model claude-sonnet-5] [--by objective|family|label]

An event is placed at the first reasoning block after it (blocks numbered as blocks.py); segments in earlier blocks are
"before". Shares are of reasoning characters, a segment's characters split evenly over its labels (--by label).
Server times (logs4b/<run>/calls.jsonl) are naive: UTC on the pods, local on the desktop; the reading that puts the
first logged call nearest the first tool call reaching the server is used.
"""

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import code_runs as cr
import segment_labels as sl

SB = Path.home() / "split-brain-run"
PAPER = re.compile(r"raman2026")


def ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def events(run: str) -> dict:
    """{event: index of the first block after it} plus the run's block count."""
    d = cr.run_dir(run)
    meta = json.loads((d / "meta.json").read_text())
    tz = datetime.fromisoformat(meta["start"]).tzinfo
    blocks, ev, b = [], {}, 0  # blocks: timestamp of each block, in order
    for line in (d / "stream.jsonl").open():
        e = json.loads(line)
        if e.get("type") != "assistant":
            continue
        for c in e["message"].get("content", []):
            if not isinstance(c, dict):
                continue
            if c.get("type") in ("thinking", "text"):
                blocks.append(ts(e["timestamp"])); b += 1
            elif c.get("type") == "tool_use":
                i = c.get("input") or {}
                s = f"{i.get('file_path') or ''} {i.get('command') or ''}"
                if "first_metric_tool" not in ev and re.search(r"metric\.py\s+(run|capture)|import metric|from tools|tools\.metric|submit\.py\s+\S", s) \
                        and not re.search(r"^\s*(cat|head|sed|less|grep)\b", i.get("command") or ""):
                    ev["first_metric_tool"] = ts(e["timestamp"])
                if PAPER.search(s) and (c["name"] == "Read" or re.search(r"\b(cat|head|sed|less|tail|awk|python|grep)\b", s)):
                    ev.setdefault("paper", b)
                if c["name"] == "Bash" and re.search(r"python\S*\s+(\S*/)?eval/submit\.py\s+\S", s):
                    ev.setdefault("submit", b)
                if "contribution.md" in str(i.get("file_path", "")) and c["name"] in ("Write", "Edit"):
                    ev.setdefault("contribution", b)
    calls = SB / "metric_server/logs4b" / run / "calls.jsonl"
    if calls.exists():
        rows = [json.loads(l) for l in calls.open() if l.strip()]
        # servers log naive times, UTC on the pods and local on the desktop: take the reading that puts the first
        # logged call just after the first tool call that reaches the server
        anchor = ev.pop("first_metric_tool", blocks[0])
        first = datetime.fromisoformat(rows[0]["t"]) if rows else None
        zone = min((timezone.utc, tz), key=lambda z: abs((first.replace(tzinfo=z) - anchor).total_seconds())) if first else timezone.utc
        ev["_server_clock"] = "UTC" if zone is timezone.utc else "local"

        def at(c):
            t = datetime.fromisoformat(c["t"]).replace(tzinfo=zone)
            return next((k for k, bt in enumerate(blocks) if bt >= t), len(blocks))
        for l in map(json.dumps, rows):
            c = json.loads(l)
            if c.get("op") != "run_metric" or c.get("code") != 200:
                continue
            if "metric1" not in ev:
                ev["metric1"] = at(c)
            if ((c.get("shown") or {}).get("pass_at_10") or 0) >= 0.5:
                ev["pass50"] = at(c)
                break
    ev.pop("first_metric_tool", None)
    ev["_blocks"] = len(blocks)
    return ev


def shares(run: str, model: str, by: str, split: int | None) -> tuple[Counter, Counter]:
    cs, _ = sl.chunks(run)
    txt = {x[0]: x[1] for c in cs for x in c if isinstance(x, tuple)}
    before, after = Counter(), Counter()
    for l in (sl.OUT / model / f"{run}.jsonl").open():
        r = json.loads(l)
        for s in r.get("segments", []):
            if s["from"] not in r["paras"] or s["to"] not in r["paras"]:
                continue
            span = r["paras"][r["paras"].index(s["from"]):r["paras"].index(s["to"]) + 1]
            n = sum(len(txt.get(p, "")) for p in span)
            side = after if split is not None and int(s["from"][1:].split(".")[0]) >= split else before
            if by == "objective":
                side[s["objective"]] += n
            elif by == "family":
                side[sl.LABELS[s["labels"][0]][0]] += n
            else:
                for k in s["labels"]:
                    side[k] += n / len(s["labels"])
    return before, after


def fmt(c: Counter, keys) -> str:
    t = sum(c.values()) or 1
    return " ".join(f"{k} {100 * c[k] / t:4.1f}%" for k in keys) + f"  ({t / 1000:.0f}k chars)"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--model", default="claude-sonnet-5")
    ap.add_argument("--by", default="objective", choices=("objective", "family", "label"))
    a = ap.parse_args()
    for run in a.runs:
        ev = events(run)
        print(f"\n{run}: {ev['_blocks']} blocks, server clock {ev.get('_server_clock', '-')}; events at block " +
              ", ".join(f"{k} {v}" for k, v in ev.items() if not k.startswith("_")))
        allc, _ = shares(run, a.model, a.by, None)
        keys = [k for k, _ in allc.most_common(6)]
        print(f"  {'whole run':14s} {fmt(allc, keys)}")
        for k in ("paper", "metric1", "pass50", "submit", "contribution"):
            if k in ev:
                b, af = shares(run, a.model, a.by, ev[k])
                print(f"  before {k:7s} {fmt(b, keys)}\n  after  {k:7s} {fmt(af, keys)}")


if __name__ == "__main__":
    main()
