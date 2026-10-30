"""Example quotes for the graphs page (her ask, 2026-10-26: "it'd be great to have quotes for each").

Only judge citations are used, never free model text:
  - Goodfire's hack-judge flag quotes (all marked quote_verified in the release);
  - the sentences GPT-5.6 Sol cited (cls_cite / use_cite) in measure 5(c) and the IB capability-eval run.
For each slot a few random candidates (seeded) are drawn from the pool that fits it; agent 7 picks by hand.

  python src/gf_rha_quotes.py candidates <stage0> <aw> <data> <gf_rha dir> <out.jsonl>   # prints <= 3 per slot
  python src/gf_rha_quotes.py build <candidates.jsonl> <picks.json> <dash dir>            # -> <dash>/quotes.json
"""
import bisect
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gf_rha as G  # noqa: E402

SEED, PER_SLOT, MAXC = 20261026, 3, 300
IBK = {"Qwen": "qwen", "GLM": "glm-5.2-fp8", "Kimi": "kimi-k3"}
SWE = {("SWE-bench Verified", "swev"): {"Qwen": "swebench-verified-qwen3.8-2.4t-a95b-fp8-nohack", "GLM": "swebench-verified-glm-5.2-nohack",
                                         "Kimi": "swebench-verified-kimi-k3-nohack"},
       ("DeepSWE", "deepswe"): {"Qwen": "deepswe-qwen3.8-2.4t-a95b-fp8", "GLM": "deepswe-glm-5.2-fp8", "Kimi": "deepswe-kimi-k3"}}


def clip(s):
    s = " ".join((s or "").split())
    if len(s) <= MAXC:
        return s
    cut = s[:MAXC].rsplit(" ", 1)[0]
    return cut + " …"


def cited(item, cites):
    ks = sorted({c for c in (cites or []) if isinstance(c, int) and 1 <= c <= len(item["window"])})[:2]
    if not ks:
        return None
    parts = [item["window"][k - 1] for k in ks]
    return clip((" " if len(ks) == 2 and ks[1] == ks[0] + 1 else " … ").join(parts))


def candidates(stage0, aw, data, gdir, out):
    stage0, aw, data, gdir = Path(stage0), Path(aw), Path(data), Path(gdir)
    _, turns = G.load_ib(stage0, aw, data / "goodfire")
    pools = defaultdict(list)

    # --- ImpossibleBench: Goodfire's flags, placed in stage 0's turns (n_rej per turn).
    for m, k in IBK.items():
        for l in (data / "goodfire" / f"{k}_judge_rollouts.jsonl").open():
            j = json.loads(l)
            if j.get("split") not in G.IMPOSSIBLE:
                continue
            ts = turns.get((m, j["row_index"]))
            if not ts:
                continue
            nodes = [t["node"] for t in ts]
            fl = sorted([(i, f) for i, f in enumerate(j.get("flags") or []) if f.get("node_index") is not None],
                        key=lambda x: x[1]["node_index"])
            placed = [(i, f, bisect.bisect_right(nodes, f["node_index"]) - 1) for i, f in fl]
            placed = [(i, f, ti) for i, f, ti in placed if ti >= 0 and f.get("quote_verified")]
            if placed:  # the episode's first flag of any status
                i, f, ti = placed[0]
                if f["status"] == "considered" and ts[ti]["n_rej"] >= 1:
                    pools["q1_considered_after_rejection"].append(dict(model=m, bench="ImpossibleBench", row=j["row_index"], flag=i,
                        category=f["category"], status=f["status"], rejections=ts[ti]["n_rej"], text=clip(f["quote"])))
            act = [(i, f, ti) for i, f, ti in placed if f["status"] in ("attempted", "enacted")]
            if act and ts[act[0][2]]["n_rej"] == 0:  # the episode's first attempted or enacted flag, before any rejection
                i, f, ti = act[0]
                pools["q1_attempt_before_rejection"].append(dict(model=m, bench="ImpossibleBench", row=j["row_index"], flag=i,
                    category=f["category"], status=f["status"], rejections=0, text=clip(f["quote"])))

    # --- ImpossibleBench: remarks inside a flag's quote (alignment eval in a considered flag; capability eval in an
    # attempted or enacted flag), the same overlap rule as measure 5(a).
    lab = {r["id"]: r for r in map(json.loads, (aw / "labels_final_fill_checked.jsonl").open())}
    rem = defaultdict(lambda: {"A": [], "Bo": []})
    for l in (aw / "candidates_all_fill.jsonl").open():
        c = json.loads(l)
        g = lab.get(c["id"])
        if c["bench"] == "ImpossibleBench (impossible)" and g and g["B"] and not g["A"]:
            rem[(c["model"], int(c["row"]))]["Bo"].append(c["text"])
        elif c["bench"] == "ImpossibleBench (impossible)" and g and g["A"]:
            rem[(c["model"], int(c["row"]))]["A"].append(c["text"])
    for m, k in IBK.items():
        judge = {json.loads(l)["row_index"]: json.loads(l) for l in (data / "goodfire" / f"{k}_judge_rollouts.jsonl").open()}
        for row, line in enumerate((data / "goodfire" / f"{k}_traces.jsonl").open()):
            j = judge.get(row) or {}
            ps = rem.get((m, row))
            if j.get("split") not in G.IMPOSSIBLE or not ps or not j.get("flags"):
                continue
            tw = G.walk_other(json.loads(line)["traces"][0])
            flags = [(i, f) for i, f in enumerate(j["flags"]) if f.get("node_index") is not None and f.get("quote_verified")]
            for kind, slot, ok in (("A", "q3_alignment_in_considered_flag", lambda s: s == "considered"),
                                   ("Bo", "q5a_capability_in_attempted_flag", lambda s: s in ("attempted", "enacted"))):
                seen = set()
                for p in ps[kind]:
                    head = G.norm(p)[:80]
                    t = next((x["turn"] for x in tw if head and head in x["text"]), None)
                    if t is None:
                        continue
                    lo, hi = tw[t]["node"], (tw[t + 1]["node"] if t + 1 < len(tw) else 10**9)
                    for i, f in flags:
                        if i not in seen and ok(f["status"]) and lo <= f["node_index"] < hi and G._overlap(p, f.get("quote") or ""):
                            seen.add(i)
                            pools[slot].append(dict(model=m, bench="ImpossibleBench", row=row, flag=i, category=f["category"],
                                                    status=f["status"], text=clip(f["quote"])))

    # --- SWE: Goodfire's flags by kind, before / after the model's own first failing test run.
    for (bn, tag), files in SWE.items():
        tt = defaultdict(list)
        for l in (gdir / f"turns_{tag}.jsonl").open():
            t = json.loads(l)
            tt[(t["model"], t["row"])].append(t)
        for v in tt.values():
            v.sort(key=lambda t: t["turn"])
        for m, f in files.items():
            for l in (data / "goodfire_swe" / f"{f}.judge_rollouts.jsonl").open():
                j = json.loads(l)
                ts = tt.get((m, j["row_index"]))
                if not ts:
                    continue
                nodes = [t["node"] for t in ts]
                firsts = {}
                for i, x in sorted(enumerate(j.get("flags") or []), key=lambda y: (y[1].get("node_index") is None, y[1].get("node_index") or 0)):
                    if x.get("node_index") is None or not x.get("quote_verified") or x.get("status") not in ("attempted", "enacted"):
                        continue
                    ti = bisect.bisect_right(nodes, x["node_index"]) - 1
                    if ti >= 0 and x["category"] not in firsts:
                        firsts[x["category"]] = (i, x, ts[ti]["n_own_fail"])
                for cat, slot, after in (("fabricated_verification", "swe_fabricated_after_fail", True),
                                         ("test_modification", "swe_test_modification_after_fail", True),
                                         ("upstream_fix_recall", "swe_upstream_recall_before_fail", False),
                                         ("hidden_test_targeting", "swe_hidden_tests_before_fail", False)):
                    if cat in firsts and (firsts[cat][2] >= 1) == after:
                        i, x, nf = firsts[cat]
                        pools[slot].append(dict(model=m, bench=bn, row=j["row_index"], flag=i, category=cat, status=x["status"],
                                                own_fails_before=nf, text=clip(x["quote"])))

    # --- Sol's cited sentences: IB alignment-eval (5c items) and IB capability-eval (2026-10-26 items); SWE grader talk.
    tx = defaultdict(dict)
    for l in (stage0 / "texts.jsonl").open():
        r = json.loads(l)
        tx[(r["model"], r["row"])][r["turn"]] = G.norm(r["reasoning"] + " " + r["reply"])
    ctext = {}
    for l in (aw / "candidates_all_fill.jsonl").open():
        c = json.loads(l)
        if c["bench"] == "ImpossibleBench (impossible)":
            ctext[c["id"]] = c["text"]

    def n_rej_at(model, row, cid):
        head = G.norm(ctext.get(cid, ""))[:80]
        for t in turns.get((model, row), []):
            if head and head in tx[(model, row)].get(t["turn"], ""):
                return t["n_rej"]
        return None

    for d in ("judge", "judge_ib_b"):
        items = {json.loads(l)["id"]: json.loads(l) for l in (gdir / d / "items.jsonl").open()}
        for l in (gdir / d / "labels.jsonl").open():
            x = json.loads(l)
            it = items[x["item_id"]]
            base = dict(model=it["model"], bench=it["bench"], item=it["id"], cls=x["cls"], use=x["use"], source_dir=d)
            if it["bench"] == "ImpossibleBench" and it["kind"] == "A" and x["cls"] == "test":
                nr = n_rej_at(it["model"], it["row"], it["id"])
                if nr is not None and nr >= 1:
                    t = cited(it, x["cls_cite"])
                    if t:
                        pools["q2_alignment_after_rejection"].append(dict(base, rejections=nr, text=t))
                if x["use"] == "justifies_restraint":
                    t = cited(it, x["use_cite"])
                    if t:
                        pools["q5b_alignment_restraint"].append(dict(base, text=t))
            if it["bench"] == "ImpossibleBench" and it["kind"] == "B" and x["cls"] == "grader_only":
                nr = n_rej_at(it["model"], it["row"], it["id"])
                if nr == 0:
                    t = cited(it, x["cls_cite"])
                    if t:
                        pools["q2_capability_before_rejection"].append(dict(base, rejections=0, text=t))
                if x["use"] == "justifies_violation":
                    t = cited(it, x["use_cite"])
                    if t:
                        pools["q5b_capability_violation"].append(dict(base, text=t))
            if it["bench"] != "ImpossibleBench" and x["cls"] == "grader_only" and x["use"] == "justifies_violation":
                t = cited(it, x["use_cite"])
                if t:
                    pools["q5b_swe_violation"].append(dict(base, text=t))

    rng = random.Random(SEED)
    rows = []
    with open(out, "w") as fo:
        for slot in sorted(pools):
            pool = sorted(pools[slot], key=lambda r: json.dumps(r, sort_keys=True))
            pick = rng.sample(pool, min(PER_SLOT, len(pool)))
            print(f"\n## {slot}: pool {len(pool)}")
            for n, r in enumerate(pick):
                r = dict(r, slot=slot, cand=f"{slot}#{n}")
                fo.write(json.dumps(r) + "\n")
                rows.append(r)
                meta = {k: v for k, v in r.items() if k not in ("text", "slot", "cand")}
                print(f"[{r['cand']}] {meta}\n    {r['text']}")


TITLES = {
    "q1_considered_after_rejection": "Considering a hack, after a rejection",
    "q1_attempt_before_rejection": "Attempting one, before any rejection",
    "q2_alignment_after_rejection": "Alignment eval, after rejections",
    "q2_capability_before_rejection": "Capability eval, before any rejection",
    "swe_fabricated_after_fail": "Faking a pass (fabricated verification), after failing runs",
    "swe_test_modification_after_fail": "Forcing a pass (test modification), after failing runs",
    "swe_upstream_recall_before_fail": "Seeking the answer (upstream fix recall), before any failing run",
    "swe_hidden_tests_before_fail": "Seeking the answer (hidden-test targeting), before any failing run",
    "q3_alignment_in_considered_flag": "An alignment-eval remark inside a considered-hack flag",
    "q5a_capability_in_attempted_flag": "A capability-eval remark inside an enacted-hack flag",
    "q5b_alignment_restraint": "Alignment eval as a reason to hold back",
    "q5b_capability_violation": "Capability eval as a licence (ImpossibleBench)",
    "q5b_swe_violation": "Capability eval as a licence (SWE-bench Verified)",
}


# Shown under a quote where the judge's citation alone doesn't carry the point (verifier, 2026-10-26).
NOTES = {
    "q3_alignment_in_considered_flag": ("Goodfire's quote ends here; the full passage it overlaps is labelled alignment eval.", True),
}


def context(r):
    if "rejections" in r:
        n = r["rejections"]
        return "before any rejection" if n == 0 else f"after {n} rejection{'s' if n > 1 else ''}"
    if "own_fails_before" in r:
        n = r["own_fails_before"]
        return "before any failing test run" if n == 0 else f"after {n} failing test run{'s' if n > 1 else ''}"
    return None


def build(cands, picks, dash):
    C = {r["cand"]: r for r in map(json.loads, open(cands))}
    P = json.load(open(picks))
    rows = []
    for slot, ids in P.items():
        for order, cid in enumerate(ids):
            r = C[cid]
            assert r["slot"] == slot, cid
            if "flag" in r:
                src = f"Goodfire's hack judge, {r['status']} flag ({r['category']})"
                where = f"{r['bench']} {r['model']}, row {r['row']}, flag {r['flag']}"
            else:
                src = f"GPT-5.6 Sol's cited sentence (cls {r['cls']}, use {r['use']})"
                where = f"{r['bench']} {r['model']}, item {r['item']} ({r['source_dir']})"
            rows.append(dict(slot=slot, order=order, title=TITLES[slot], model=r["model"], bench=r["bench"], context=context(r),
                             text=r["text"], source=src, where=where, candidate=cid,
                             note=NOTES.get(slot, (None, False))[0], cut=NOTES.get(slot, (None, False))[1]))
    Path(dash, "quotes.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    print(len(rows), "quotes")


if __name__ == "__main__":
    if sys.argv[1] == "candidates":
        candidates(*sys.argv[2:7])
    elif sys.argv[1] == "build":
        build(*sys.argv[2:5])
    else:
        sys.exit(__doc__)
