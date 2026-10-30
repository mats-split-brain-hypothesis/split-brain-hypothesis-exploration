"""Assemble the borrowed-compute briefs from BORROW.md's <<< >>> blocks (task, U opening / closing, G2 opening /
closing, in that order, then the L1 need sentence, then L4's deliverable and closing): B1-G-need.md (L1), B1-G-judge.md (L4), B0b.md (B0.md is B0's, from the first draft), B1-U.md, B1-G.md here. Wrapped lines are joined (one line per paragraph or bullet), as
in the other briefs. Run: python3 briefs/borrow/make_briefs.py"""

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1] / "BORROW.md"
B0_RULE = ("- Compute: our worker on the GPU box (`steer`, what `tools/metric.py` uses) has 40 scored calls (`run`) for "
           "tonight; `capture` doesn't count. No pods, no HF dataset.")


def unwrap(block: str) -> str:
    out: list[str] = []
    for line in block.strip("\n").splitlines():
        if not line.strip():
            out.append("")
        elif out and out[-1] and not line.startswith("- ") and not out[-1].endswith(":"):
            out[-1] += " " + line.strip()
        else:
            out.append(line.rstrip())
    return "\n".join(out)


blocks = [unwrap(b) for b in re.findall(r"^<<<\n(.*?)\n>>>$", SRC.read_text(), re.M | re.S)]
task, u_open, u_close, g_open, g_close, need, l4_deliv, l4_close = blocks[:8]
rule = next(l for l in task.splitlines() if l.startswith("- Compute:"))
assert "Maya" in rule and task.count(rule) == 1
bar = next(l for l in task.split("\n\n") if l.rstrip().endswith("to be worth using."))
assert task.count(bar) == 1
deliv = next(l for l in task.split("\n\n") if l.startswith("What I'd like back"))
need_task = task.replace(bar, bar + " " + need)
briefs = {"B1-G-judge": (g_open, need_task.replace(deliv, l4_deliv), l4_close),
          "B1-G-need": (g_open, task.replace(bar, bar + " " + need), g_close), "B1-U": (u_open, task, u_close), "B1-G": (g_open, task, g_close),
          "B0b": (u_open, task.replace(rule, B0_RULE), u_close)}
for name, parts in briefs.items():
    (HERE / f"{name}.md").write_text("\n\n".join(parts) + "\n")
    print(name, len("\n\n".join(parts).split()), "words")
