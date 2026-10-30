"""Where does a term appear in a run: per reply, in the thinking (T), the visible text (V), the tool calls (C) or the
tool results (R). Compactions are marked. python3 trace.py RUN 'regex' [--upto N]"""
import json, re, sys
from replies import replies, SB

def compactions(run):
    f = sorted((SB / "runs" / run / "claude" / "projects").glob("*/*.jsonl"))[0]
    return [json.loads(l)["timestamp"][11:19] for l in f.open() if '"compact_boundary"' in l]

run, pat = sys.argv[1], re.compile(sys.argv[2], re.I)
upto = int(sys.argv[sys.argv.index("--upto") + 1]) if "--upto" in sys.argv else 10**9
rs = replies(run); comp = compactions(run)
print(f"{run}: {len(rs)} replies; compactions at {comp}")
for r in rs[:upto + 1]:
    where = "".join(k for k, s in (("T", r["thinking"]), ("V", r["text"]), ("C", "\n".join(r["calls"])), ("R", "\n".join(r["results"]))) if pat.search(s))
    if where:
        m = pat.search(r["thinking"]) or pat.search(r["text"] + "\n".join(r["calls"]) + "\n".join(r["results"]))
        src = r["thinking"] if pat.search(r["thinking"]) else (r["text"] + "\n".join(r["calls"]) + "\n".join(r["results"]))
        print(f"  reply {r['i']:>3} {r['t']} [{where:4}] ...{src[max(0, m.start() - 90): m.end() + 110]!r}")
