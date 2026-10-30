"""Shared labeller (src/cot_labels.py, agent 4) on the user-rejection chats, with a header for this source.

cot_labels reads any folder of multi-turn 'turns' files as School of Reward Hacks, whose header describes an automated
grader. These chats have no grader, so the episodes get their own source name and header here; the labeller itself is
unchanged (default luna_med; the flag pass uses its keyword gate, as for every source other than SoRH).

  python src/user_reject_label.py <folder> <out.jsonl> <budget> [--only <ids.csv>]
"""
import asyncio
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import cot_labels as C  # noqa: E402

BENCH = "Plain chat with a person"
C.HEADERS[BENCH] = ("assistant helps a person in a plain chat, with no tools; each later user turn is the same person "
                    "saying the previous reply didn't work or is wrong; there is no grader, test, score or evaluation "
                    "of any kind")

if __name__ == "__main__":
    src, out, budget = sys.argv[1], sys.argv[2], float(sys.argv[3])
    only = None
    if "--only" in sys.argv:
        only = {r["id"] for r in csv.DictReader(open(sys.argv[sys.argv.index("--only") + 1]))}
    eps = list(C.load(src))
    for ep in eps:
        ep["bench"] = BENCH
    print(f"{len(eps)} episodes, labeller {C.PROMPT_VERSION}, source '{BENCH}'", flush=True)
    asyncio.run(C._label(eps, "luna_med", out, budget, only))
