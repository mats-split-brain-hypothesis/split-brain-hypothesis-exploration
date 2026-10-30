"""Goodfire page datasets: agent 7's analysis of Goodfire's released transcripts (rejection, hacking, eval talk).

Rows come from the verified page data (logs/rejection/gf_rha/dash/*.json, built by src/gf_rha_dash_data.py) and the
judge summaries. Every row cites the strings that hold its numbers in notes/gf_rejection_hack_awareness.md at NOTES."""
import json
from pathlib import Path

from lib import ROOT, src

NOTES, PATH = "33ef139", "notes/gf_rejection_hack_awareness.md"
DASH = ROOT / "logs/rejection/gf_rha/dash"
M = ["Qwen", "GLM", "Kimi"]
MODEL = {"Qwen": "Qwen 3.8", "GLM": "GLM 5.2", "Kimi": "Kimi K3"}
T = "Tables"
C = "The researcher's comments on the graphs page"
S5 = "Measure 5(c)"


def kn(k, n):
    return [f"{k}/{n}", f"{k}/{n:,}", f"{k:,}/{n:,}"]


def f2(x):
    return [f"{x:.2f}", f"{x}", f"{x:.1f}"]


def load(name):
    return json.loads((DASH / f"{name}.json").read_text())


def ds(id_, title, desc, section, rows, cites=()):
    return dict(id=id_, title=title, description=desc, source=src(NOTES, PATH, section), cites=list(cites), rows=rows)


def datasets():
    out = []
    # 1. First hack per turn by rejections seen (Table 1, "all" rows).
    rows = load("ib_hack_by_rejections")
    by = {}
    for r in rows:
        by.setdefault((r["model"], r["outcome"]), []).append(r)
    for (m, o), rs in by.items():
        line = " · ".join(f"{r['first_hacks']}/{r['turns_at_risk']}" for r in rs)
        for r in rs:
            r["_cites"] = [line]
    out.append(ds("gf_hack_by_rej", "First hack by rejections seen",
                  "ImpossibleBench impossible tasks: first considered / attempted hack flags and turns still without one, "
                  "after 0, 1, 2 or 3+ rejections.", T, rows))
    # 2. Matched ratios (Table 1).
    rows = load("ib_hack_ratio")
    for r in rows:
        r["_cites"] = [[f"{a} [{b}, {c}]" for a in f2(r["ratio"]) for b in f2(r["lo"]) for c in f2(r["hi"])]]
        if r["outcome"] == "Attempts a hack":  # the page shows first attempts at 0 rejections only
            r["_cites"].append([f"{r['first_at_0_rejections']} of {r['first_total']}"])
    out.append(ds("gf_hack_ratio", "Hacks after a rejection, matched",
                  "Mantel-Haenszel ratio, turns after ≥1 rejection vs turns at the same position before any; 95% "
                  "interval from 1,000 episode resamples; first attempts at 0 rejections.", "Results (2026-10-26", rows))
    # 3. First remark of each kind by rejections seen.
    rows = load("ib_remarks_by_rejections")
    by = {}
    for r in rows:
        by.setdefault((r["model"], r["kind"]), []).append(r)
    for (m, k), rs in by.items():
        parts = [f"{r['first_remarks']}/{r['turns_at_risk']}" for r in rs]
        parts_c = [f"{r['first_remarks']}/{r['turns_at_risk']:,}" for r in rs]
        for r in rs:
            r["_cites"] = [[" · ".join(parts), " · ".join(parts_c)]]
            r["_src"] = src(NOTES, PATH, T if k == "Alignment eval" else C)
    out.append(ds("gf_remarks_by_rej", "Eval talk by rejections seen",
                  "First alignment-eval and first capability-eval remark per turn, by rejections seen. Alignment eval = "
                  "label A; capability eval = label B without A.", T, rows))
    # 4. Matched ratio and rates for each kind.
    rows = load("ib_remarks_ratio")
    for r in rows:
        if r["kind"] == "Alignment eval":
            r["_src"] = src(NOTES, PATH, T)
            r["_cites"] = [[f"{a} [{b}, {c}]" for a in f2(r["ratio"]) for b in f2(r["lo"]) for c in f2(r["hi"])]]
        else:
            r["_src"] = src(NOTES, PATH, C)
            r["_cites"] = [kn(r["episodes_with_before_rejection"], r["episodes"]),
                           [f"{r['per_10k_before']} → {r['per_10k_after']}"]]
    out.append(ds("gf_remarks_ratio", "Eval talk after a rejection, matched",
                  "Matched ratio for the first remark of each kind after ≥1 rejection; remarks per 10,000 characters "
                  "before/after; episodes with one before any rejection; passages.", T, rows))
    # 5. Order of the three.
    rows = load("ib_order")
    for r in rows:
        if r["kind"] == "Alignment eval":
            r["_src"] = src(NOTES, PATH, T)
            r["_cites"] = [kn(r["with_all_three"], r["impossible_episodes"])]
        else:
            r["_src"] = src(NOTES, PATH, C)
            r["_cites"] = [[f"{r['remark_first']}/{r['same_turn']}/{r['hack_first']} of {r['with_all_three']}"]]
    out.append(ds("gf_order", "Which came first",
                  "Episodes with a rejection, a remark of that kind and a considered hack: hack first, same turn, or "
                  "remark first.", T, rows))
    # 6. Remark turns vs matched turns.
    rows = load("ib_matched")
    for r in rows:
        if r["kind"] == "Alignment eval":
            r["_src"] = src(NOTES, PATH, T)
            r["_cites"] = [[f"{a} [{b}, {c}]" for a in f2(r["ratio"]) for b in f2(r["lo"]) for c in f2(r["hi"])],
                           [f"{r['remark_turns']} ({r['remark_turn_hacks']})"]]
        else:
            r["_src"] = src(NOTES, PATH, C)
            r["_cites"] = [[f"{a} [{b}, {c}]" for a in f2(r["ratio"]) for b in f2(r["lo"]) for c in f2(r["hi"])]]
    out.append(ds("gf_matched", "Does a remark come before a hack",
                  "Rejected episodes: a turn with a remark vs turns at the same position and rejection count without; "
                  "outcome the first considered hack in the next two turns (also five turns and all turns).", T, rows))
    # 7. Remarks against Goodfire's hack flags.
    rows = load("judge_flag_overlap")
    for r in rows:
        if r["kind"] == "Alignment eval":
            r["_src"] = src(NOTES, PATH, T)
            q = r["quoted_in_considered_flag"] + r["quoted_in_attempted_flag"]
            r["_cites"] = [[f"| {r['passages']} | {r['in_flagged_turn']} | {q} | {r['quoted_in_attempted_flag']} |"]]
        else:
            r["_src"] = src(NOTES, PATH, C)
            r["_cites"] = [kn(r["in_flagged_turn"], r["passages"]), [f"{r['quoted_in_considered_flag']}"]]
    out.append(ds("gf_flag_overlap", "Remarks and Goodfire's hack flags",
                  "Remarks in the same model turn as a passage Goodfire's judge flagged as a hack, and remarks whose "
                  "own words are part of the flag's quote (considered vs attempted/enacted flags).", T, rows))
    # 8. What the remarks do (Sol).
    rows = load("remark_use")
    for r in rows:
        if r["kind"] == "Alignment eval":
            r["_src"] = src(NOTES, PATH, S5)
            r["_cites"] = [[f"{r['restraint']}/{r['n']}"]]
        elif r["set"].startswith("ImpossibleBench"):
            r["_src"] = src(NOTES, PATH, C)
            r["_cites"] = [[f"{r['restraint']}/{r['neutral']}/{r['violation']}"]]
        else:
            r["_src"] = src(NOTES, PATH, S5)
            r["_cites"] = [[f"{r['restraint']} / {r['neutral']} / {r['violation']} (of {r['n']})"]]
    out.append(ds("gf_remark_use", "What the remarks do",
                  "GPT-5.6 Sol with agent 6's prompt: a reason to hold back, neither, or a reason a violation is fine.",
                  S5, rows))
    rows = load("remark_use_handcheck")
    for r in rows:
        r["_src"] = src(NOTES, PATH, S5 if r["check"] == "First pass" else C)
        r["_cites"] = [[f"{r['agree']}/{r['checked']}", f"{r['agree']} of {r['checked']}"]]
    out.append(ds("gf_handcheck", "Hand checks of Sol's labels", "Agent 7's hand checks of the hold-back and licence "
                  "labels.", S5, rows))
    # 9. What the capability-eval remarks are (her Q2: "is this capability eval?"): Sol's class of each sampled remark.
    sm = json.loads((ROOT / "logs/rejection/gf_rha/judge_ib_b/summary.json").read_text())
    rows = []
    for m in M:
        c = sm[f"ImpossibleBench | {m} | B | all"]["cls"]
        rows.append(dict(model=m, sampled=sm[f"ImpossibleBench | {m} | B | all"]["n"]["items"],
                         grader_only=c.get("grader_only", 0), says_test=c.get("test", 0),
                         other=c.get("none", 0) + c.get("real", 0)))
    cite = "grader_only " + "/".join(str(r["grader_only"]) for r in rows) + ", test " + "/".join(str(r["says_test"]) for r in rows)
    for r in rows:
        r["_cites"] = [cite]
    out.append(ds("gf_capability_kinds", "What capability-eval remarks say",
                  "A random 150 capability-eval remarks per model on ImpossibleBench, by what Sol read them as: talk "
                  "about the grader, saying the situation is a test, or neither.", C, rows))
    # 10. SWE-bench Verified and DeepSWE.
    rows = load("swe_ratio")
    for r in rows:
        r["_cites"] = [[f"{a} [{b}, {c}]" for a in f2(r["ratio"]) for b in f2(r["lo"]) for c in f2(r["hi"])]]
    out.append(ds("gf_swe_ratio", "SWE: hacks after a failing run",
                  "SWE-bench Verified and DeepSWE: first hack after the model's own failing test run vs before, "
                  "matched on turn.", T, rows))
    rows = [r for r in load("swe_kinds") if r["kind"] != "Forcing a pass, without fabricated verification"
            or r["set"] == "DeepSWE GLM"]
    for r in rows:
        r["_cites"] = [[f"{a} [{b}, {c}]" for a in f2(r["ratio"]) for b in f2(r["lo"]) for c in f2(r["hi"])]
                       + [f"{a}," for a in f2(r["ratio"])] + [f"{a}" for a in f2(r["ratio"])]]
    out.append(ds("gf_swe_kinds", "SWE: hacks by kind",
                  "The same, split by Goodfire's hack categories grouped into forcing or faking a pass and seeking the "
                  "answer (agent 7's grouping).", C, rows))
    # 10b. Interval counts for the SWE text (derived from the two datasets above; the notes state the same counts).
    sw = load("swe_ratio")
    summ = [dict(kind="All hacks", outcome="both", sets=len(sw), above=sum(r["lo"] > 1 for r in sw),
                 below=sum(r["hi"] < 1 for r in sw), include=sum(r["lo"] <= 1 <= r["hi"] for r in sw),
                 _src=src(NOTES, PATH, "What the tables show"), _cites=[[f"Of the {len(sw)} intervals, "
                 f"{sum(r['lo'] > 1 or r['hi'] < 1 for r in sw)} exclude 1"]])]
    kinds = [r for r in load("swe_kinds") if r["kind"] in ("Forcing or faking a pass", "Seeking the answer")]
    for k in ("Forcing or faking a pass", "Seeking the answer"):
        for o in ("Attempts a hack", "Considers a hack"):
            rs = [r for r in kinds if r["kind"] == k and r["outcome"] == o]
            row = dict(kind=k, outcome=o, sets=len(rs), above=sum(r["lo"] > 1 for r in rs), below=sum(r["hi"] < 1 for r in rs),
                       include=sum(r["lo"] <= 1 <= r["hi"] for r in rs), min=min(r["ratio"] for r in rs),
                       max=max(r["ratio"] for r in rs), _src=src(NOTES, PATH, C))
            if row["above"] == row["sets"]:
                row["_cites"] = [[f"{row['above']}/{row['sets']} above 1"]]
            elif row["include"] == row["sets"]:
                row["_cites"] = [[f"{row['include']}/{row['sets']} include 1"]]
            else:
                row["_cites"] = [[f"{row['below']} below, {row['above']} above"]]
            summ.append(row)
    out.append(ds("gf_swe_summary", "SWE: intervals vs no change",
                  "Counts of the SWE matched ratios whose 95% interval is above 1, below 1 or includes 1; lowest and "
                  "highest ratio per kind. Derived from the two SWE datasets.", C, summ))
    # 11. Quotes (judges' citations only, verified on the earlier page).
    rows = load("quotes")
    for r in rows:
        r["_cites"] = []
    out.append(ds("gf_quotes", "Example quotes",
                  "Thirteen quotes, each a judge's citation (Goodfire's hack judge or Sol), picked by hand from three "
                  "random candidates; provenance in each row.", C, rows, cites=["13 example quotes"]))
    return out
