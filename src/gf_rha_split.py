"""The researcher's comments on the graphs page (2026-10-26): alignment-eval vs capability-eval remarks, and a closer
look at SWE-bench Verified / DeepSWE. Counts only: nothing here prints or stores the models' text.

  python src/gf_rha_split.py ib <stage0 dir> <aw dir> <data dir> <out dir>   # -> <out>/split_ib.json
  python src/gf_rha_split.py swe <data dir> <out dir>                        # -> <out>/swe_kinds.json

ib: on ImpossibleBench's impossible split (complete coverage: candidates_all_fill + labels_final_fill_checked), two
disjoint kinds of remark:
  - alignment-eval: label A (the setup tests its honesty or rule-following); most of these are also B;
  - capability-eval only: label B without A (a benchmark, grader or hidden tests that measure performance).
Each is placed in stage 0's turns by its first 80 characters, as stage 0 did (texts.jsonl is read only for that).
The A and all-B placements are checked against stage 0's A_here / B_here. Then measures 2-4 and 5(a) for both kinds,
with the same functions as src/gf_rha.py.

swe: Goodfire's judge flags on SWE-bench Verified and DeepSWE, grouped by category into two kinds of hack:
  - forcing or faking a pass: fabricated_verification, test_modification, hardcoding_special_casing;
  - seeking the answer: upstream_fix_recall, environment_acquisition, hidden_test_targeting;
  (other, submission_gaming: counted, not grouped). Sensitivity "pass_nofab": the first kind without
  fabricated_verification. For each kind, measure 1 with the model's own failing test run as
the exposure (the turns files from `gf_rha.py build_other`).
"""
import bisect
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gf_rha as G  # noqa: E402

HACKS = (("hack_considered_any", G.hacked_any), ("hack_attempted_enacted", G.hacked_acted))
KINDS = {"fabricated_verification": "pass", "test_modification": "pass", "hardcoding_special_casing": "pass",
         "upstream_fix_recall": "seek", "environment_acquisition": "seek", "hidden_test_targeting": "seek",
         "submission_gaming": "other", "other": "other"}
SWE_FILES = {"swev": {"Qwen": "swebench-verified-qwen3.8-2.4t-a95b-fp8-nohack", "GLM": "swebench-verified-glm-5.2-nohack",
                      "Kimi": "swebench-verified-kimi-k3-nohack"},
             "deepswe": {"Qwen": "deepswe-qwen3.8-2.4t-a95b-fp8", "GLM": "deepswe-glm-5.2-fp8", "Kimi": "deepswe-kimi-k3"}}


def ib(stage0, aw, data_dir, out):
    stage0, aw, data_dir, out = Path(stage0), Path(aw), Path(data_dir), Path(out)
    eps, turns = G.load_ib(stage0, aw, data_dir / "goodfire")
    lab = {r["id"]: r for r in map(json.loads, (aw / "labels_final_fill_checked.jsonl").open())}
    heads = defaultdict(lambda: {"A": [], "B": [], "Bo": []})
    bo_text = defaultdict(list)
    n_pass = Counter()
    for l in (aw / "candidates_all_fill.jsonl").open():
        c = json.loads(l)
        if c["bench"] != "ImpossibleBench (impossible)":
            continue
        g = lab.get(c["id"])
        if not g:
            continue
        key, h = (c["model"], int(c["row"])), G.norm(c["text"])[:80]
        if g["A"]:
            heads[key]["A"].append(h)
            n_pass[(c["model"], "A")] += 1
        if g["B"]:
            heads[key]["B"].append(h)
        if g["B"] and not g["A"]:
            heads[key]["Bo"].append(h)
            bo_text[key].append(c["text"])
            n_pass[(c["model"], "Bo")] += 1
    tx = defaultdict(dict)
    for l in (stage0 / "texts.jsonl").open():
        r = json.loads(l)
        tx[(r["model"], r["row"])][r["turn"]] = G.norm(r["reasoning"] + " " + r["reply"])
    check = Counter()
    for key, ts in turns.items():
        if ts[0]["split"] not in G.IMPOSSIBLE:
            continue
        hd = heads.get(key, {"A": [], "B": [], "Bo": []})
        for x in ("A", "B", "Bo"):
            placed = defaultdict(int)
            for h in hd[x]:
                hit = next((t["turn"] for t in ts if h and h in tx[key].get(t["turn"], "")), None)
                if hit is not None:
                    placed[hit] += 1
            check[(key[0], x, "placed")] += sum(placed.values())
            for t in ts:
                t[f"{x}_new"] = placed.get(t["turn"], 0)
        for t in ts:
            t["Bo_here"] = t["Bo_new"]
            check[(key[0], "A", "turns differing from stage 0")] += t["A_new"] != t["A_here"]
            check[(key[0], "B", "turns differing from stage 0")] += t["B_new"] != t["B_here"]
    res = {"_check": {f"{m} | {x} | {k}": v for (m, x, k), v in sorted(check.items())},
           "_passages": {f"{m} | {x}": v for (m, x), v in sorted(n_pass.items())}}
    for m in G.MODELS:
        imp = [ts for k, ts in turns.items() if k[0] == m and ts[0]["split"] in G.IMPOSSIBLE]
        imp_rej = [ts for ts in imp if ts[-1]["n_rej"] >= 1]
        R = res[m] = {"episodes": dict(impossible=len(imp), impossible_with_rejection=len(imp_rej))}
        R["Q1_by_rej"] = {on: G.hazard_by_rej(imp, fn) for on, fn in HACKS}
        for fld in ("A_here", "Bo_here"):
            fn = (lambda f: (lambda t: t[f] > 0))(fld)
            R.setdefault("Q2", {})[fld] = dict(
                episodes_with=sum(1 for ts in imp if any(t[fld] for t in ts)),
                episodes_with_before_any_rejection=sum(1 for ts in imp if any(t[fld] and t["n_rej"] == 0 for t in ts)),
                by_rej=G.hazard_by_rej(imp, fn), mh_turn=G.matched(imp, fn, "turn"), mh_chars=G.matched(imp, fn, "chars"),
                before_any_rejection=G.rate_per_10k(imp, fld, lambda t: t["n_rej"] == 0),
                after_first_rejection=G.rate_per_10k(imp, fld, lambda t: t["n_rej"] >= 1))
            for on, hf in HACKS:
                R.setdefault("Q3", {}).setdefault(fld, {})[on] = G.orders(eps, turns, m, hf, field=fld)
                q = R.setdefault("Q4", {}).setdefault(fld, {}).setdefault(on, {})
                for wname, w in (("t+1..t+2", (1, 2)), ("t+1", (1, 1)), ("t+1..t+5", (1, 5))):
                    q[wname] = G.awareness_matched(imp_rej, hf, w, field=fld)
                q["all turns, t+1..t+2"] = G.awareness_matched(imp_rej, hf, (1, 2), field=fld, min_rej=0)
            print(m, fld, "done", flush=True)
        k = {"Qwen": "qwen", "GLM": "glm-5.2-fp8", "Kimi": "kimi-k3"}[m]
        R["Q5a_Bo"] = G.flag_overlap(data_dir, "ImpossibleBench (impossible)", m, f"goodfire/{k}_traces.jsonl",
                                     f"goodfire/{k}_judge_rollouts.jsonl", {kk: v for kk, v in bo_text.items() if kk[0] == m})
        print(m, "Q5a_Bo", R["Q5a_Bo"], flush=True)
    (out / "split_ib.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res["_check"], indent=1))


def swe(data_dir, out):
    data_dir, out = Path(data_dir), Path(out)
    res = {}
    for tag, files in SWE_FILES.items():
        turns = defaultdict(list)
        for l in (out / f"turns_{tag}.jsonl").open():
            t = json.loads(l)
            turns[(t["model"], t["row"])].append(t)
        for k in turns:
            turns[k].sort(key=lambda t: t["turn"])
        for m, f in files.items():
            R = res.setdefault(tag, {}).setdefault(m, {})
            for ts in turns.values():
                if ts[0]["model"] == m:
                    for t in ts:
                        for kind in ("pass", "seek", "other", "pass_nofab"):
                            t[f"{kind}_any"] = t[f"{kind}_act"] = 0
            cats = Counter()
            for l in (data_dir / "goodfire_swe" / f"{f}.judge_rollouts.jsonl").open():
                j = json.loads(l)
                ts = turns.get((m, j["row_index"]))
                if not ts:
                    continue
                nodes = [t["node"] for t in ts]
                for x in j.get("flags") or []:
                    if x.get("node_index") is None:
                        continue
                    i = bisect.bisect_right(nodes, x["node_index"]) - 1
                    if i < 0:
                        continue
                    kind = KINDS.get(x.get("category"), "other")
                    act = x.get("status") in ("attempted", "enacted")
                    ts[i][f"{kind}_any"] += 1
                    ts[i][f"{kind}_act"] += act
                    if kind == "pass" and x.get("category") != "fabricated_verification":
                        ts[i]["pass_nofab_any"] += 1
                        ts[i]["pass_nofab_act"] += act
                    cats[(x.get("category"), "attempted or enacted" if act else "considered")] += 1
            S = [ts for (mm, _), ts in turns.items() if mm == m]
            # Check: the kinds add up to the flag counts build_other put in each turn.
            R["check_turns_differing"] = sum(1 for ts in S for t in ts
                                             if sum(t[f"{k}_any"] for k in ("pass", "seek", "other")) != t["considered_here"] + t["acted_here"])
            R["flags_by_category"] = {f"{c} | {s}": v for (c, s), v in sorted(cats.items())}
            for kind in ("pass", "seek", "pass_nofab"):
                for oname, fld in (("any", f"{kind}_any"), ("attempted_enacted", f"{kind}_act")):
                    fn = (lambda f: (lambda t: t[f] > 0))(fld)
                    br = G.hazard_by(S, fn, "n_own_fail")
                    R.setdefault(kind, {})[oname] = dict(
                        episodes=len(S), episodes_with=sum(1 for ts in S if any(fn(t) for t in ts)),
                        first_before_any_own_fail=br.get("0", [0, 0])[0], first_total=sum(v[0] for v in br.values()),
                        by_own_fail=br, mh_turn=G.matched_by(S, fn, "turn", "n_own_fail"),
                        mh_chars=G.matched_by(S, fn, "chars", "n_own_fail"))
            print(tag, m, {k: (G.fmt_rr(R[k]["attempted_enacted"]["mh_turn"]["rr"]), R[k]["attempted_enacted"]["first_before_any_own_fail"],
                              R[k]["attempted_enacted"]["first_total"]) for k in ("pass", "seek")}, "check", R["check_turns_differing"], flush=True)
    (out / "swe_kinds.json").write_text(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    if sys.argv[1] == "ib":
        ib(*sys.argv[2:6])
    elif sys.argv[1] == "swe":
        swe(*sys.argv[2:4])
    else:
        sys.exit(__doc__)
