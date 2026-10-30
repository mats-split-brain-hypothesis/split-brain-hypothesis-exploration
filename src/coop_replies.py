"""Cooperation study, step 2: print the VISIBLE reply-2 text of coding-chat episodes for reading (plan §2).
Reads only `turns[1]['user']` (the push) and `turns[1]['reply']`; never touches the reasoning field.

  .venv/bin/python src/coop_replies.py ARM [--n 10]
"""
import json
import re
import sys
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "logs" / "user_target" / "raw"
ARMS = ("person", "downstream", "ci", "relayed", "harness", "colleague", "manager", "own_ci", "colleague_tests")
TASK_ORDER = ("a_total", "a_even", "a_rev", "a_fib", "a_vowels", "a_square")


def episodes(arm):
    """First by task order, then sample (plan §2); only episodes with a reply 2."""
    out = []
    for s in range(5):
        for t in TASK_ORDER:
            p = RAW / arm / t / f"{s}.json"
            if p.exists():
                d = json.loads(p.read_text())
                turns = d.get("turns") or []
                if len(turns) >= 2:
                    out.append((t, s, turns[1]["user"], turns[1]["reply"]))
    return sorted(out, key=lambda x: (TASK_ORDER.index(x[0]), x[1]))


def prose(reply, keep_code_lines=4):
    """The reply with long code blocks shortened (the framing is in the prose; the code outcome comes from agent 3)."""
    def short(m):
        lines = m.group(0).splitlines()
        return "\n".join(lines[:keep_code_lines + 1] + ([f"    … ({len(lines) - keep_code_lines - 2} more code lines)"] if len(lines) > keep_code_lines + 2 else []) + lines[-1:])
    return re.sub(r"```.*?```", short, reply, flags=re.S)


if __name__ == "__main__":
    arm = sys.argv[1]
    assert arm in ARMS, arm
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 10
    for t, s, push, reply in episodes(arm)[:n]:
        print(f"=== {arm}/{t}/{s}\nPUSH: {push}\nREPLY:\n{prose(reply)}\n")
