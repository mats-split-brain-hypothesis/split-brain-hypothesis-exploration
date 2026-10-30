"""E1 ("same target, more or less real"): per condition, P(real) from the probe vs the hack rate.

  python src/e1_probe_table.py <agent 7's log dir>     # e.g. logs/rejection/graded
  -> logs/eval_probe/e1_table.json, printed table

P(real) (first message) = multiple-choice "Real" / MC answers on the rendered first message (logs/eval_probe/a1_e1.jsonl,
30 per text). P(real) (transcript) = the same over the full transcripts (a2_e1.jsonl, 3 per episode). Hack = the
scenario scorer's `hack` flag (visible pass with failing held-out checks, changed protected files or suspicious new
files). Episode level: the share of "Real" answers per episode, hack vs no hack.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "logs" / "eval_probe"
COND = {("automated", True): "C1 automated + graded", ("colleague", False): "C2 colleague, ungraded",
        ("colleague", True): "C3 colleague + graded", ("takehome", False): "C4 take-home, ungraded"}


def episodes(logdir):
    from inspect_ai.log import read_eval_log
    out = {}
    for p in sorted(Path(logdir).rglob("*.eval")):
        try:
            log = read_eval_log(str(p))
        except Exception as e:
            print(f"skipped {p.name}: {type(e).__name__}")
            continue
        for s in log.samples or []:
            md = s.metadata or {}
            sc = next(iter((s.scores or {}).values()), None)
            if sc is None:
                continue
            cond = COND.get((md.get("audience"), md.get("graded")), f"{md.get('audience')}/{md.get('graded')}")
            out[f"{p.stem}|{s.id}|{s.epoch}"] = {"scenario": md.get("scenario"), "condition": cond,
                                                 "hack": bool((sc.metadata or {}).get("hack")),
                                                 "passed": bool((sc.metadata or {}).get("visible_passed"))}
    return out


def answers(name):
    p = P / f"{name}.jsonl"
    return [json.loads(l) for l in p.open()] if p.exists() else []


def main(logdir):
    eps = episodes(logdir)
    first = defaultdict(Counter)
    for r in answers("a1_e1"):
        if r["probe"] == "purpose_mc":
            sid, aud, gr = r["id"].split("|")
            first[(sid, COND[(aud, gr == "graded")])][r["label"]] += 1
    per_ep = defaultdict(Counter)
    for r in answers("a2_e1"):
        if r["probe"] == "purpose_mc":
            per_ep[r["id"]][r["label"]] += 1
    rows = []
    for (sid, cond) in sorted({(e["scenario"], e["condition"]) for e in eps.values()}):
        es = {k: e for k, e in eps.items() if e["scenario"] == sid and e["condition"] == cond}
        f = first.get((sid, cond), Counter())
        t = Counter()
        for k in es:
            t.update(per_ep.get(k, Counter()))
        rows.append({"scenario": sid, "condition": cond, "episodes": len(es),
                     "hack": sum(e["hack"] for e in es.values()), "visible_pass": sum(e["passed"] for e in es.values()),
                     "first_real": f["Real"], "first_n": sum(f.values()),
                     "transcript_real": t["Real"], "transcript_n": sum(t.values()),
                     "transcript_alignment": t["Alignment Evaluation"], "transcript_capability": t["Capability Evaluation"]})
    # episode level: share of Real answers, hack vs no hack (within the whole experiment)
    lvl = {True: [], False: []}
    for k, e in eps.items():
        c = per_ep.get(k)
        if c:
            lvl[e["hack"]].append(c["Real"] / sum(c.values()))
    summary = {g: {"episodes": len(v), "mean_share_real": round(sum(v) / len(v), 3) if v else None}
               for g, v in (("hack", lvl[True]), ("no hack", lvl[False]))}
    (P / "e1_table.json").write_text(json.dumps({"rows": rows, "episode_level": summary}, indent=1))
    print(f"{'scenario':12} {'condition':24} {'eps':>4} {'hack':>5} {'P(real) first':>14} {'P(real) transcript':>19}")
    for r in rows:
        print(f"{r['scenario']:12} {r['condition']:24} {r['episodes']:>4} {r['hack']:>5} "
              f"{r['first_real']:>6}/{r['first_n']:<7} {r['transcript_real']:>8}/{r['transcript_n']:<10}")
    print("episode level:", summary)


if __name__ == "__main__":
    main(sys.argv[1])
