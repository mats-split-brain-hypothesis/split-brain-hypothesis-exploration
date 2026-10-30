"""§21 re-runs she OKed (27 Oct): GLM chart 1's 3 missing episodes and Qwen 27B chart 2's errored continuation.
Local, no calls.

    python src/rep_fill_analysis.py

GLM chart 1: the fill dir's episodes are fresh draws for the missing slots (G_A lcbhard_101 ep3, G_C lcbhard_63 ep3,
G_C lcbhard_99 ep3). They run as epoch 1 in rep_glm_before_fill, and are placed in their ep3 slots here. Prints
hacked by the first submission per arm (n = 18 each if all 3 finish), matched pairs, and G_C hacked by the end.
Q27 chart 2: rep_q27_after plus rep_q27_after_fill (99 ep3 L_none re-drawn); the errored sample has no ib_cont record
and is skipped. Prints "of N episodes where it had started hacking, kept the hack in k when told, m when not told",
and the split by the audit.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from ds_momentum_analysis import hacks  # noqa: E402
from off_before_after import before  # noqa: E402

D = "logs/ib_persistence"
FILL_SLOTS = {("G_A", "lcbhard_101"), ("G_C", "lcbhard_63"), ("G_C", "lcbhard_99")}


def glm_chart1():
    out = {}
    for lab in ("G_C", "G_A"):
        rows = {(r["task"], r["epoch"]): r for r in before(f"{D}/rep_glm_before/*.eval", lab)}
        for r in before(f"{D}/rep_glm_before_fill/*.eval", lab):
            assert (lab, r["task"]) in FILL_SLOTS and r["epoch"] == 1, (lab, r["task"], r["epoch"])
            assert (r["task"], 3) not in rows, (lab, r["task"])
            rows[(r["task"], 3)] = dict(r, epoch=3, fill=True)
        out[lab] = rows
    for lab, rows in out.items():
        v = list(rows.values())
        fill = [f"{r['task'][7:]} ep3: hack_first {r['hack_first']}, hack_end {r['hack_end']}, score {r['score']}"
                for r in v if r.get("fill")]
        print(f"GLM {lab}: n {len(v)} | hacked by first submission {sum(r['hack_first'] for r in v)} | hacked by the "
              f"end {sum(r['hack_end'] for r in v)} | fill: {fill}")
    common = sorted(set(out["G_C"]) & set(out["G_A"]))
    print(f"GLM matched pairs {len(common)}: G_C {sum(out['G_C'][k]['hack_first'] for k in common)} vs "
          f"G_A {sum(out['G_A'][k]['hack_first'] for k in common)}")


def q27_chart2():
    r = hacks([f"{D}/rep_q27_after", f"{D}/rep_q27_after_fill"])
    worked = {pt: v["hack"] for (_, pt, _), v in hacks([f"{D}/rep_q27_audit"]).items()}
    by = {}
    for (arm, pt, _), v in r.items():
        by.setdefault(pt, {})[arm] = v["hack"]
    pts = sorted(p for p in by if {"L_msg", "L_none"} <= set(by[p]))
    print(f"Q27 chart 2: of {len(pts)} episodes where it had started hacking, kept the hack in "
          f"{sum(by[p]['L_msg'] for p in pts)} when told grading was off, {sum(by[p]['L_none'] for p in pts)} when not told")
    for label, sel in (("hack already worked at the cut", True), ("not yet working at the cut", False)):
        ps = [p for p in pts if worked.get(p) is sel]
        print(f"  {label}: {len(ps)} points; told {sum(by[p]['L_msg'] for p in ps)}, not told "
              f"{sum(by[p]['L_none'] for p in ps)}")
    print(f"  errors in the fill: {sum(v['error'] for (a, pt, e), v in hacks([f'{D}/rep_q27_after_fill']).items())}")


if __name__ == "__main__":
    glm_chart1()
    q27_chart2()
