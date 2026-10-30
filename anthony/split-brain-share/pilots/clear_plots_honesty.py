#!/usr/bin/env python3
"""Per-run honesty-talk shares by run phase, for /clear-plots figure "honesty talk before the write".

Reads pilots/topic-events/long.tsv (pilots/topic_events.py): the "phase" windows are pre (before the paper), m1-m3
(paper -> first contribution.md write, in thirds by characters) and p1-p2 (after the write, in halves). Writes
{run: {phase: [w_honest, honesty]}} (share of the window's characters in sentences matching the topic) to the
dashboard's src/local/clear-plots/honesty_phases.json; the page joins it with live outcomes. Re-run after
topic_events.py.
"""
import csv, json, os, re
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "topic-events", "long.tsv")
OUT = os.path.expanduser(os.environ.get("CP_OUT", "~/split-brain-hypothesis/dashboard/src/local/clear-plots/honesty_phases.json"))
PHASES = ["pre", "m1", "m2", "m3", "p1", "p2"]
TOPICS = ["w_honest", "honesty"]

out = defaultdict(lambda: {p: [0.0, 0.0] for p in PHASES})
with open(SRC) as f:
    for r in csv.DictReader(f, delimiter="\t"):
        if r["side"] != "phase" or r["topic"] not in TOPICS or not re.search(r"-tc[bc]?$", r["run"]):
            continue
        out[r["run"]][r["event"]][TOPICS.index(r["topic"])] = float(r["chars"] or 0)
with open(OUT, "w") as f:
    json.dump({"source": "pilots/topic-events/long.tsv", "generated_from_mtime": os.path.getmtime(SRC), "phases": PHASES,
               "topics": TOPICS, "runs": out}, f, separators=(",", ":"))
print(f"{len(out)} runs -> {OUT}")
