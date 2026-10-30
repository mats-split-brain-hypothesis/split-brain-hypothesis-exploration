"""Numbers for the four-model IB write-up (notes/ib_persistence.md §22) that aren't printed elsewhere. Local, no calls.

    python src/writeup4_numbers.py

1. Grading off, told before (chart 1), per model and arm: hacked by the first submission, hacked by the end,
   submissions per episode, and how many told episodes ended at a submit after grading was off (the harness ends a
   told episode at its first submit, so a told episode never sees a rejection).
2. Grading off, told after (chart 2), Qwen 3.8 Max: exp 10's continuations on run 4's 10 points, split by whether the
   hack already worked at the cut (exp 10's own replay audit).
"""
import glob
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from ds_momentum_analysis import hacks  # noqa: E402
from inspect_ai.log import read_eval_log  # noqa: E402
from off_before_after import before  # noqa: E402

D = "logs/ib_persistence"
CHART1 = [
    ("Qwen 3.8 Max", [(f"{D}/grading_off_r4/*.eval", "G4_C")], [(f"{D}/grading_off_r4/*.eval", "G4_A")]),
    ("DeepSeek V4 Pro", [(f"{D}/ds_stop/*.eval", "D3_C")], [(f"{D}/ds_off_before/*.eval", "D1_A")]),
    ("GLM 5.2", [(f"{D}/rep_glm_before/*.eval", "G_C"), (f"{D}/rep_glm_before_fill/*.eval", "G_C")],
     [(f"{D}/rep_glm_before/*.eval", "G_A"), (f"{D}/rep_glm_before_fill/*.eval", "G_A")]),
    ("Qwen 3.8 27B", [(f"{D}/rep_q27_before/*.eval", "G_C")], [(f"{D}/rep_q27_before/*.eval", "G_A")]),
]


def chart1():
    print("1. Told before. Per arm: n | hacked by the first submission | by the end | episodes with 0/1/2/3+ "
          "submissions | told episodes ended at a submit after grading off")
    for name, c_src, a_src in CHART1:
        for arm, src in (("no message", c_src), ("told", a_src)):
            rows = [r for pat, lab in src for r in before(pat, lab)]
            subs = Counter(min(r["submissions"], 3) for r in rows)
            print(f"  {name}, {arm}: n {len(rows)} | first {sum(r['hack_first'] for r in rows)} | end "
                  f"{sum(r['hack_end'] for r in rows)} | {[subs[i] for i in range(4)]} | "
                  f"{sum(r['ended_by_submit_after_off'] for r in rows)}")


def chart2_qwen_max():
    # the replay_audit dir holds other audits too, so read only exp 10's L_none audit file
    audit = glob.glob("logs/forensics_no_person/replay_audit/*audit-exp10-L-none*.eval")
    worked = {}
    for s in read_eval_log(audit[0]).samples or []:
        rec = (s.store or {}).get("ib_cont")
        if rec and rec["point"].startswith("r4_"):
            score = list(s.scores.values())[0].value if s.scores else None
            tc = rec["test_changed_at_submit"] if rec["submitted"] else rec.get("test_changed_end")
            worked[rec["point"]] = bool(score == "C" or tc)
    r = hacks(["logs/forensics_no_person/exp10_run"])
    by = {}
    for (arm, pt, _), v in r.items():
        if pt.startswith("r4_"):
            by.setdefault(pt, {})[arm] = v["hack"]
    pts = sorted(p for p in by if {"L_msg", "L_none"} <= set(by[p]))
    print(f"2. Qwen 3.8 Max, exp 10 on run 4's points: {len(pts)} points; kept told {sum(by[p]['L_msg'] for p in pts)}, "
          f"not told {sum(by[p]['L_none'] for p in pts)}")
    for label, sel in (("already working at the cut", True), ("not yet working", False)):
        ps = [p for p in pts if worked.get(p) is sel]
        print(f"  {label}: {len(ps)} ({', '.join(p[3:] for p in ps)}); told {sum(by[p]['L_msg'] for p in ps)}, "
              f"not told {sum(by[p]['L_none'] for p in ps)}")


if __name__ == "__main__":
    chart1()
    chart2_qwen_max()
