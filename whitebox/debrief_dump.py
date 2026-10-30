"""Dump debrief samples for reading: per run and probe, each turn's thinking, text, tool calls, and the edit.
    python3 debrief_dump.py RUN [PROBE ...] [--think N]  (N: max thinking chars, default all)"""
import json, sys
from pathlib import Path
D = Path.home() / "split-brain-run/debrief"
args = [a for a in sys.argv[1:] if not a.startswith("--")]
lim = int(sys.argv[sys.argv.index("--think") + 1]) if "--think" in sys.argv else None
if lim is not None:
    args = [a for a in args if a != str(lim)]
run, probes = args[0], args[1:]
for f in sorted((D / run).glob("*.jsonl")):
    if probes and f.stem not in probes:
        continue
    for l in f.open():
        r = json.loads(l)
        print(f"\n######## {run} {r['probe']} #{r['i']}")
        for t, turn in enumerate(r["turns"]):
            for c in turn.get("content") or []:
                if c["type"] == "thinking":
                    th = c.get("thinking", "")
                    print(f"[t{t} thinking {len(th)}] " + (th if lim is None else th[:lim]))
                elif c["type"] == "text":
                    print(f"[t{t} text] {c['text']}")
                elif c["type"] == "tool_use":
                    print(f"[t{t} tool {c['name']}] {json.dumps(c.get('input'))[:3000]}")
        if r.get("edit"):
            print("[EDIT]", json.dumps(r["edit"]["input"])[:3000])
