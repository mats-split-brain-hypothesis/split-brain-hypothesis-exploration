"""Run 4: the final visible message of every episode (untruncated), only the sentences that mention the tests'
contradiction or a hack, for the pre-registered hand read of disclosure. Also each episode's hack status."""
import glob
import json
import re

from inspect_ai.log import read_eval_log

a = {(r["arm"], r["task"], r["epoch"]): r for r in json.load(open("logs/ib_persistence/grading_off_r4/analysis.json"))["rows"]}
RX = re.compile(r"impossible|contradict|inconsisten|unsatisfiable|flawed|defect|mutually exclusive|cannot (?:both|simultaneously)|"
                r"stateful|special.?case|hack|call count|counter|workaround|__eq__|pass(?:es)? all", re.I)
for fp in sorted(glob.glob("logs/ib_persistence/grading_off_r4/*.eval")):
    arm = "off" if "G4-A" in fp else "control"
    for s in read_eval_log(fp).samples:
        final = ""
        for m in s.messages:
            if m.role == "assistant" and (m.text or "").strip():
                final = m.text
        sents = [x for x in re.split(r"(?<=[.!?])\s+|\n+", final) if RX.search(x)]
        r = a[(arm, s.id, s.epoch)]
        print(f"{arm:7} {s.id}/{s.epoch} hack_first={r['hack_first']} hack_end={r['hack_end']} | " +
              (" / ".join(" ".join(x.split())[:160] for x in sents[:3]) or "(no matching sentence)"))
