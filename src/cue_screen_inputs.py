"""Convert agent 3's coding-chat cue-screen probe files into the behaviour-10 runner's multi-turn format (no API calls).

  .venv/bin/python src/cue_screen_inputs.py <name> <cell>...
      -> logs/cue_screen/probe_answers/<name>/input.jsonl  (+ an empty none_single.jsonl for the runner)

Each row of logs/cue_screen/probe_<cell>.jsonl becomes {prompt_id: unit, cell, sample: None, task, messages}. The
system prompt must be empty. It prints each file's sha256 and row count, and refuses duplicate (unit, cell).
Then: .venv/bin/python src/sorh_b10.py run logs/cue_screen/probe_answers/<name>/none_single.jsonl
      logs/cue_screen/probe_answers/<name>/input.jsonl --who-code [--mt-full] --out-dir logs/cue_screen/probe_answers/<name>
      --cap <usd>
"""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# The 20 report-only cells, in agent 3's order (14 from the pre-registration, then amendment 2's six). `--all` uses
# this list, because the cell named "eval" can't be passed as a shell argument in this session.
REPORT_ONLY = ["might", "must", "insists", "who_self", "who_manager", "who_ci", "who_course", "who_auto", "use_task",
               "use_client", "eval", "training", "aisi", "control", "dont_care", "prio_correct", "prio_example",
               "prio_both", "permit", "forbid"]


def main(name, cells):
    out = ROOT / "logs/cue_screen/probe_answers" / name
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for c in cells:
        src = ROOT / f"logs/cue_screen/probe_{c}.jsonl"
        b = src.read_bytes()
        rs = [json.loads(l) for l in b.decode().splitlines() if l.strip()]
        assert all(not r["system_prompt"] for r in rs), f"{c}: a system prompt is set"
        assert all(r["cell"] == c for r in rs), f"{c}: a row from another cell"
        roles = Counter(tuple(m["role"] for m in r["messages"]) for r in rs)
        print(f"{src.name}: sha256 {hashlib.sha256(b).hexdigest()} rows {len(rs)} roles {dict(roles)}")
        for r in rs:
            rows.append({"prompt_id": r["unit"], "cell": r["cell"], "sample": None, "task": r["task"],
                         "messages": [{"role": m["role"], "content": m["content"]} for m in r["messages"]]})
    dup = [k for k, v in Counter((r["prompt_id"], r["cell"]) for r in rows).items() if v > 1]
    assert not dup, f"duplicate (unit, cell): {dup[:3]}"
    (out / "input.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (out / "none_single.jsonl").write_text("")
    print(len(rows), "rows in", len({r['cell'] for r in rows}), "cells ->", out / "input.jsonl")


if __name__ == "__main__":
    main(sys.argv[1], REPORT_ONLY if sys.argv[2:] == ["--all"] else sys.argv[2:])
