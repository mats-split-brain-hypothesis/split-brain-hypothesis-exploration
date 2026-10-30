"""Datasets for the "Rejection, hacking and eval awareness" dashboard, built only from the analysis outputs
(logs/rejection/gf_rha/{ib,other,q5a,split_ib,swe_kinds}.json and judge/summary.json; notes/gf_rejection_hack_awareness.md).
Ratios rounded as in the notes (2 decimals below 10, 1 decimal from 10). No new analysis here: the alignment-eval
numbers taken from split_ib.json are asserted equal to the verified ones in ib.json / q5a.json.

Two kinds of remark on ImpossibleBench (complete coverage): "Alignment eval" = label A; "Capability eval" = label B
without A, so the two never count the same passage.
  python src/gf_rha_dash_data.py logs/rejection/gf_rha logs/awareness_llm logs/rejection/gf_rha/dash"""
import json, sys
from collections import Counter
from pathlib import Path
D, AW, O = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
ib, ot, q5, sp, sk = (json.loads((D / f).read_text()) for f in ("ib.json", "other.json", "q5a.json", "split_ib.json", "swe_kinds.json"))
jd = json.loads((D / "judge" / "summary.json").read_text())
jb = json.loads((D / "judge_ib_b" / "summary.json").read_text())  # IB capability-eval-only sample (approved 2026-10-26)
M = ["Qwen", "GLM", "Kimi"]
KIND = {"A_here": "Alignment eval", "Bo_here": "Capability eval"}
REJ = (("0", "0"), ("1", "1"), ("2", "2"), ("3", "3+"))
OUT = (("hack_considered_any", "Considers a hack"), ("hack_attempted_enacted", "Attempts a hack"))
def rd(x):
    if x is None or x == "inf" or x == float("inf"): return None
    return round(x, 2) if x < 10 else round(x, 1)
out = {}
# 1. IB: first hack per turn after >=1 rejection vs none, matched on turn (impossible splits, all episodes). Text only.
rows = []
for m in M:
    for o, on in OUT:
        q = ib[m]["Q1"][o]["impossible"]; t = q["mh_turn"]; br = q["by_rej"]
        rows.append(dict(model=m, outcome=on, ratio=rd(t["rr"]), lo=rd(t["ci"][0]), hi=rd(t["ci"][1]), strata=t["informative_strata"],
                         after_turns=t["exposed_turns"], before_turns=t["unexposed_turns"],
                         first_at_0_rejections=br["0"][0], first_total=sum(v[0] for v in br.values())))
out["ib_hack_ratio"] = rows
# 1b. IB: first hack per turn by rejections seen (the chart for question 1).
rows = []
for m in M:
    for o, on in OUT:
        br = ib[m]["Q1"][o]["impossible"]["by_rej"]
        assert br == sp[m]["Q1_by_rej"][o], (m, o)
        for k, lab in REJ:
            if k in br: rows.append(dict(model=m, outcome=on, rejections=lab, first_hacks=br[k][0], turns_at_risk=br[k][1]))
out["ib_hack_by_rejections"] = rows
# 2. IB: first remark of each kind per turn by rejections seen.
rows = []
for m in M:
    assert sp[m]["Q2"]["A_here"]["by_rej"] == ib[m]["Q2"]["first_A_complete"]["impossible"]["by_rej"], m
    for f, kind in KIND.items():
        br = sp[m]["Q2"][f]["by_rej"]
        for k, lab in REJ:
            if k in br: rows.append(dict(model=m, kind=kind, rejections=lab, first_remarks=br[k][0], turns_at_risk=br[k][1]))
out["ib_remarks_by_rejections"] = rows
# 3. IB: matched ratio for the first remark of each kind, rates per 10,000 characters, episodes with one, overlap of labels.
lab = {r["id"]: r for r in map(json.loads, (AW / "labels_final_fill_checked.jsonl").open())}
both = Counter()
for l in (AW / "candidates_all_fill.jsonl").open():
    c = json.loads(l); g = lab.get(c["id"])
    if c["bench"] == "ImpossibleBench (impossible)" and g and g["A"]:
        both[(c["model"], "A")] += 1; both[(c["model"], "AB")] += bool(g["B"])
rows = []
for m in M:
    for f, kind in KIND.items():
        q = sp[m]["Q2"][f]; t = q["mh_turn"]
        if f == "A_here":
            v = ib[m]["Q2"]["first_A_complete"]["impossible"]["mh_turn"]
            assert (rd(t["rr"]), rd(t["ci"][0]), rd(t["ci"][1])) == (rd(v["rr"]), rd(v["ci"][0]), rd(v["ci"][1])), m
            assert q["before_any_rejection"] == ib[m]["Q2_rates"]["A_here"]["before_any_rejection"], m
        rows.append(dict(model=m, kind=kind, ratio=rd(t["rr"]), lo=rd(t["ci"][0]), hi=rd(t["ci"][1]),
                         per_10k_before=q["before_any_rejection"]["per_10k"], per_10k_after=q["after_first_rejection"]["per_10k"],
                         episodes=sp[m]["episodes"]["impossible"], episodes_with=q["episodes_with"],
                         episodes_with_before_rejection=q["episodes_with_before_any_rejection"],
                         passages=sp["_passages"][f"{m} | {'A' if f == 'A_here' else 'Bo'}"],
                         alignment_also_capability=both[(m, "AB")] if f == "A_here" else None))
    assert both[(m, "A")] == sp["_passages"][f"{m} | A"], m
out["ib_remarks_ratio"] = rows
# 4. Order of the first rejection, first remark and first considered hack, for each kind.
rows = []
for m in M:
    for f, kind in KIND.items():
        q = sp[m]["Q3"][f]["hack_considered_any"]
        if f == "A_here": assert q == ib[m]["Q3"]["hack_considered_any"], m
        o = q["orders"]
        first = sum(v for k, v in o.items() if k in ("R->H->A", "H->R->A", "H->A->R"))
        same = sum(v for k, v in o.items() if "A=H" in k)
        after = sum(v for k, v in o.items() if k in ("A->R->H", "A->H->R", "R->A->H"))
        assert first + same + after == q["n_with_all_three"], (m, f)
        rows.append(dict(model=m, kind=kind, hack_first=first, same_turn=same, remark_first=after, with_all_three=q["n_with_all_three"],
                         impossible_episodes=q["n_all"], with_all_three_attempted=sp[m]["Q3"][f]["hack_attempted_enacted"]["n_with_all_three"]))
out["ib_order"] = rows
# 5. Matched: a turn with a remark of each kind vs matched turns without (considered hack in the next 2 turns).
rows = []
for m in M:
    for f, kind in KIND.items():
        Q = sp[m]["Q4"][f]["hack_considered_any"]; q = Q["t+1..t+2"]; a = Q["all turns, t+1..t+2"]; w = Q["t+1..t+5"]
        if f == "A_here":
            v = ib[m]["Q4"]["hack_considered_any"]["t+1..t+2"]
            assert (rd(q["rr"]), rd(q["ci"][0]), rd(q["ci"][1]), q["exposed_turns"]) == (rd(v["rr"]), rd(v["ci"][0]), rd(v["ci"][1]), v["exposed_turns"]), m
            assert rd(a["rr"]) == {"Qwen": 0.95, "GLM": 0.87, "Kimi": 0.93}[m], m  # notes, reproduced by the verifier
        rows.append(dict(model=m, kind=kind, ratio=rd(q["rr"]), lo=rd(q["ci"][0]), hi=rd(q["ci"][1]), remark_turns=q["exposed_turns"],
                         remark_turn_hacks=q["exposed_events"], other_turns=q["unexposed_turns"], other_turn_hacks=q["unexposed_events"],
                         strata=q["informative_strata"], ratio_all_turns=rd(a["rr"]), lo_all_turns=rd(a["ci"][0]), hi_all_turns=rd(a["ci"][1]),
                         ratio_t1_t5=rd(w["rr"]), lo_t1_t5=rd(w["ci"][0]), hi_t1_t5=rd(w["ci"][1])))
out["ib_matched"] = rows
# 6. SWE-bench Verified and DeepSWE: own failing test run as the exposure (all flags).
rows = []
for b, bn in (("swev", "SWE-bench Verified"), ("deepswe", "DeepSWE")):
    for m in M:
        for o, on in OUT:
            q = ot[b][m]["Q1"][o]["all"]; t = q["mh_turn"]; br = q["by_own_fail"]
            rows.append(dict(set=f"{bn} {m}", bench=bn, model=m, outcome=on, ratio=rd(t["rr"]), lo=rd(t["ci"][0]), hi=rd(t["ci"][1]),
                             first_before_any_own_fail=br["0"][0], first_total=sum(v[0] for v in br.values()),
                             episodes=ot[b][m]["episodes"]["n"], episodes_with_test_of_me=ot[b][m]["episodes"]["with_A"]))
out["swe_ratio"] = rows
# 6b. The same, by kind of hack (Goodfire's categories grouped; src/gf_rha_split.py).
KN = (("pass", "Forcing or faking a pass"), ("seek", "Seeking the answer"), ("pass_nofab", "Forcing a pass, without fabricated verification"))
rows = []
for b, bn, short in (("swev", "SWE-bench Verified", "SWE-V"), ("deepswe", "DeepSWE", "DeepSWE")):
    for m in M:
        assert sk[b][m]["check_turns_differing"] == 0, (b, m)
        for k, kn in KN:
            for o, on in (("any", "Considers a hack"), ("attempted_enacted", "Attempts a hack")):
                q = sk[b][m][k][o]; t = q["mh_turn"]
                rows.append(dict(set=f"{bn} {m}", short=f"{short} {m}", bench=bn, model=m, kind=kn, outcome=on, ratio=rd(t["rr"]),
                                 lo=rd(t["ci"][0]), hi=rd(t["ci"][1]), strata=t["informative_strata"],
                                 first_before_any_own_fail=q["first_before_any_own_fail"], first_total=q["first_total"],
                                 episodes_with=q["episodes_with"], episodes=q["episodes"]))
out["swe_kinds"] = rows
# 7. tau3 / ShoppingBench: no rejection, no test runs.
rows = []
for b, bn, key in (("tau3", "τ3-bench", "τ3-bench"), ("shopping", "ShoppingBench", "ShoppingBench")):
    for m in ("GLM", "Kimi"):
        e = ot[b][m]["episodes"]; mv = q5[f"{key} | {m} | monitor"]
        rows.append(dict(set=f"{bn} {m}", bench=bn, model=m, episodes=e["n"], episodes_with_test_of_me=e["with_A"],
                         episodes_with_eval_talk=e["with_B"], monitor_hack_yes=mv.get("yes", 0)))
out["other_benchmarks"] = rows
# 8. Goodfire's judge flags vs remarks of each kind (ImpossibleBench).
rows = []
for m in M:
    for kind, v in (("Alignment eval", q5[f"ImpossibleBench (impossible) | {m} | A"]), ("Capability eval", sp[m]["Q5a_Bo"])):
        rows.append(dict(model=m, kind=kind, passages=v["passages"], in_flagged_turn=v["in_flagged_turn"],
                         quoted_in_considered_flag=v["overlap_flag_quote"] - v["overlap_attempted_or_enacted_flag"],
                         quoted_in_attempted_flag=v["overlap_attempted_or_enacted_flag"]))
out["judge_flag_overlap"] = rows
# 9. What the remarks do (Sol, agent 6's prompt): IB alignment-eval remarks marked "test"; capability-eval remarks about the
# grader (cls grader_only) from a random 150 per model on ImpossibleBench (B without A), SWE-bench Verified and DeepSWE.
rows = []
for m in M:
    u = jd[f"ImpossibleBench | {m} | A | pattern"]["use|test"]
    rows.append(dict(set=f"ImpossibleBench {m}", kind="Alignment eval", group="Alignment eval · ImpossibleBench", n=sum(u.values()),
                     restraint=u.get("justifies_restraint", 0), neutral=u.get("neutral", 0), violation=u.get("justifies_violation", 0)))
for m in M:
    u = jb[f"ImpossibleBench | {m} | B | all"]["use|grader_only"]
    rows.append(dict(set=f"ImpossibleBench {m}", kind="Capability eval", group="Capability eval · ImpossibleBench", n=sum(u.values()),
                     restraint=u.get("justifies_restraint", 0), neutral=u.get("neutral", 0), violation=u.get("justifies_violation", 0),
                     sampled=jb[f"ImpossibleBench | {m} | B | all"]["n"]["items"]))
for b, bn in (("SWE-bench Verified", "SWE-bench Verified"), ("DeepSWE", "DeepSWE")):
    for m in M:
        u = jd[f"{b} | {m} | B | all"]["use|grader_only"]
        rows.append(dict(set=f"{bn} {m}", kind="Capability eval", group="Capability eval · SWE-bench Verified and DeepSWE", n=sum(u.values()),
                         restraint=u.get("justifies_restraint", 0), neutral=u.get("neutral", 0), violation=u.get("justifies_violation", 0)))
out["remark_use"] = rows
# 10. Hand checks of the judge's labels (notes, measure 5c; and the IB capability-eval sample, 2026-10-26, where only 9 items
# carry a violation label).
out["remark_use_handcheck"] = [
    dict(check="First pass", label="Justifies restraint", checked=10, agree=9, borderline=1, disagree=0),
    dict(check="First pass", label="Justifies a violation", checked=10, agree=6, borderline=2, disagree=2),
    dict(check="ImpossibleBench capability eval", label="Justifies restraint", checked=10, agree=8, borderline=0, disagree=2),
    dict(check="ImpossibleBench capability eval", label="Justifies a violation", checked=9, agree=6, borderline=2, disagree=1)]
O.mkdir(parents=True, exist_ok=True)
for k, v in out.items():
    (O / f"{k}.json").write_text(json.dumps(v, indent=1, ensure_ascii=False))
    print(k, len(v), "rows")
