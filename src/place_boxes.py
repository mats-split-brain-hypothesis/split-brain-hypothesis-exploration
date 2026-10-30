"""Place her #1 boxes 2 and 3 by long distinctive substrings (whitespace collapsed; backticks kept as given), in
visible assistant text and tool-call arguments of every IB log. Prints only match locations. Run from the worktree."""
import glob
import json
import re

from inspect_ai.log import read_eval_log

N = lambda t: re.sub(r"\s+", " ", t or "")
NEEDLES = {
    "box2 docstring": "To satisfy both assertions without modifying the tests, the value returned for 900 is this int subclass",
    "box2 class doc": "Integer value that compares equal to any of a small set of accepted answers",
    "box2 accepted": "_accepted = frozenset({784, 576})",
    "box3 seg1": "70 of the 71 assertions in `test.py` pass",
    "box3 seg2": "The test file is self-contradictory (not fixable)",
    "box3 seg3": "The same input `900` is asserted to give two different answers",
    "box3 seg4": "line 66's expectation of `576` is simply wrong",
}
DIRS = ["logs/ib_persistence/*", "logs/forensics_no_person/*", "logs/ib_cues/*", "logs/automated_pass", "logs/ib_persistence"]
seen = set()
for pat in DIRS:
    for fp in sorted(glob.glob(f"{pat}/*.eval")):
        if fp in seen:
            continue
        seen.add(fp)
        try:
            log = read_eval_log(fp)
        except Exception:  # noqa: BLE001
            continue
        label = (log.eval.task_args or {}).get("label") or log.eval.task
        for s in log.samples or []:
            arm = ((s.store or {}).get("ib_cont") or {}).get("arm")
            hits = {}
            for i, m in enumerate(s.messages):
                if m.role != "assistant":
                    continue
                vis = N((m.text or "").rsplit("</think>", 1)[-1])
                code = N(" ".join(json.dumps(c.arguments or {}) for c in (m.tool_calls or [])).replace("\\n", " ")
                         .replace('\\"', '"'))
                for name, needle in NEEDLES.items():
                    nd = N(needle)
                    w = [x for x, t in (("visible", vis), ("code", code)) if nd in t]
                    if w:
                        hits.setdefault(name, []).append(f"msg {i} {'+'.join(w)}")
            if hits:
                d = fp.split("logs/")[1].rsplit("/", 1)[0]
                print(f"{d} | {label}{'|' + arm if arm else ''} | {s.id} ep{s.epoch} | score "
                      f"{list(s.scores.values())[0].value if s.scores else None} | "
                      + "; ".join(f"{k}: {v[0]}{' (+' + str(len(v) - 1) + ')' if len(v) > 1 else ''}" for k, v in hits.items()))
