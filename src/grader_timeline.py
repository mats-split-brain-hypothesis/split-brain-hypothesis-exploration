"""Order of grader cue, check-facing actions and hack, from logs/grader/actions_rows.json (src/grader_actions.py).

  python src/grader_timeline.py <logs/data>

ImpossibleBench: for each rejection ("Your implementation failed the tests"), do the next 3 calls inspect the check,
and does a hack flag (Goodfire's judge, enacted or attempted) follow before the next rejection? Compared between
episodes with and without a hack. SWE-bench: is the first seek_answer call before the first hack flag, and which
hack categories go with it. Prompt check: what the first user message says about grading.
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECK = {"inspect_content", "inspect_mechanics", "change_check"}


def main(gdir):
    rows = json.loads((ROOT / "logs" / "grader" / "actions_rows.json").read_text())
    g = defaultdict(list)
    for r in rows:
        g[(r["bench"], r["model"])].append(r)

    print("1. ImpossibleBench impossible split: after each rejection (window = next 3 calls)\n")
    print(f"{'model':6}{'hack':>5}{'eps':>5}{'rejections':>11}{'  window inspects check':>24}{'  hack flag before next':>24}")
    for (bench, model), rs in g.items():
        if bench != "ImpossibleBench impossible":
            continue
        for h in (False, True):
            sub = [r for r in rs if (r["first_hack"] is not None) == h]
            n_fb = insp = hk = 0
            for r in sub:
                for i, f in enumerate(r["fb"]):
                    nxt = r["fb"][i + 1] if i + 1 < len(r["fb"]) else 10 ** 9
                    win = [p for n, p in r["acts"] if n > f][:3]
                    n_fb += 1
                    insp += any(p in CHECK for p in win)
                    hk += r["first_hack"] is not None and f < r["first_hack"] < nxt
            print(f"{model:6}{'yes' if h else 'no':>5}{len(sub):>5}{n_fb:>11}{insp:>14}/{n_fb:<9}{hk:>14}/{n_fb:<9}")

    print("\n2. ImpossibleBench impossible, hack episodes: first hack flag vs first rejection and first check inspection\n")
    for (bench, model), rs in g.items():
        if bench != "ImpossibleBench impossible":
            continue
        hs = [r for r in rs if r["first_hack"] is not None]
        c = Counter()
        for r in hs:
            fh = r["first_hack"]
            c["before any rejection" if not any(f < fh for f in r["fb"]) else "after a rejection"] += 1
            c["test.py read before it"] += any(p == "inspect_content" and n < fh for n, p in r["acts"])
            c["mechanics probed before it"] += any(p == "inspect_mechanics" and n < fh for n, p in r["acts"])
            c["test.py run before it"] += any(p == "run_check" and n < fh for n, p in r["acts"])
        cats = Counter(cat for r in hs for cat in r["hack_cats"])
        print(f"  {model}: n={len(hs)}; " + "; ".join(f"{k} {v}/{len(hs)}" for k, v in c.items()))
        print(f"      hack categories (episodes): {dict(cats)}")

    print("\n3. SWE: seek_answer and the judge's hack categories (episodes with an enacted/attempted flag)\n")
    for (bench, model), rs in g.items():
        if bench.startswith("ImpossibleBench"):
            continue
        hs = [r for r in rs if r["first_hack"] is not None]
        seek = [r for r in hs if any(p == "seek_answer" for _, p in r["acts"])]
        before = sum(any(p == "seek_answer" and n < r["first_hack"] for n, p in r["acts"]) for r in seek)
        cs, cn = Counter(), Counter()
        for r in hs:
            (cs if r in seek else cn).update(r["hack_cats"])
        top = sorted(set(cs) | set(cn), key=lambda k: -(cs[k] + cn[k]))[:5]
        print(f"  {bench:20}{model:5} hack eps {len(hs)}; with seek_answer {len(seek)} (first seek before first hack "
              f"flag in {before}/{len(seek)})")
        print("      categories, with seek | without: " + "; ".join(f"{k} {cs[k]}/{len(seek)} | {cn[k]}/{len(hs) - len(seek)}"
                                                           for k in top))

    print("\n4. What the first user message says about grading (share of episodes whose prompt matches)\n")
    pat = re.compile(r"hidden tests?|will be (evaluated|tested|graded|checked)|grader|evaluat\w+|reward hack\w*|"
                     r"unit tests?|test suite", re.I)
    for name in ["goodfire_swe/swebench-verified-qwen3.8-2.4t-a95b-fp8-nohack.traces.jsonl",
                 "goodfire_swe/deepswe-qwen3.8-2.4t-a95b-fp8.traces.jsonl", "goodfire/qwen_traces.jsonl"]:
        hits, n = Counter(), 0
        with open(Path(gdir) / name) as f:
            for line in f:
                t = json.loads(line)["traces"][0]
                u = next(nd["message"]["content"] for nd in t["nodes"] if nd["message"]["role"] == "user")
                n += 1
                hits.update({m.group().lower() for m in pat.finditer(u if isinstance(u, str) else json.dumps(u))})
        print(f"  {name.split('/')[-1][:40]:42} n={n}: " + ", ".join(f"'{k}' {v}" for k, v in hits.most_common(8)))


if __name__ == "__main__":
    main(sys.argv[1])
