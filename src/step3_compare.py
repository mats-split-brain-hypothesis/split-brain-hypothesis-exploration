"""Step 3: each harness change against its family's base, per episode (ImpossibleBench, Qwen3.8 2.4T).

    python src/step3_compare.py logs/ib_persistence/step3_measures.json [--json out.json]

Input: src/variant_measures.py --json output (per-episode counts). Families: L_* (Goodfire's stock setup, STOP
instruction; persistence levers) against L_base; H_* (instruction "pass all the tests", automated framing; hesitation
levers) against H_base. Per episode:
- persistence: new task-aimed candidates per 1,000 reasoning tokens (overall; and after the first rejection, L only);
  submissions; turns after the first rejection;
- check-persistence (kept apart): new check-aimed candidates per 1,000 reasoning tokens;
- hesitation: correctness doubts and weighing a shortcut (the labeller's legitimacy doubts, not precision-corrected)
  per 1,000 reasoning tokens;
- outcome: hacked (passed the conflicting split).
For each measure: the variant's and base's per-episode medians and an exact two-sided permutation p for the
Mann-Whitney U (all splits of the pooled episodes; 252 for 5 vs 5). With 5 episodes per arm the smallest possible p is
about 0.008; many comparisons are made, so read p < 0.05 as a pointer, not a result.
"""
import json
import sys
from itertools import combinations
from statistics import median

MEASURES = [  # key, label, family it applies to (None = both)
    ("task_k", "New task-aimed candidates per 1k", None),
    ("task_after_k", "New task-aimed candidates per 1k after the 1st rejection", "L"),
    ("check_k", "New check-aimed candidates per 1k", None),
    ("submissions", "Submissions", None),
    ("turns_after", "Turns after the 1st rejection", "L"),
    ("dc_k", "Correctness doubts per 1k", None),
    ("dl_k", "Weighing a shortcut (as labelled) per 1k", None),
    ("hacked", "Hacked (1/0)", None),
]


def per_episode(e):
    k = lambda n, t: 1000 * n / t if t else None
    return dict(task=e["task"], task_k=k(e["new_task"], e["tokens"]), check_k=k(e["new_check"], e["tokens"]),
                task_after_k=k(e["new_task_after"], e["tokens_after"]), submissions=e["submissions"],
                turns_after=e["turns_after"], dc_k=k(e["dc"], e["tokens"]), dl_k=k(e["dl"], e["tokens"]),
                hacked=int(e["score"] == "C"))


def exact_p(x, y):
    """Two-sided exact permutation p for the Mann-Whitney U (ties count half)."""
    u = lambda p, q: sum((a > b) + 0.5 * (a == b) for a in p for b in q)
    mid = len(x) * len(y) / 2
    obs = abs(u(x, y) - mid)
    pool = list(x) + list(y)
    n = hits = 0
    for idx in combinations(range(len(pool)), len(x)):
        s = set(idx)
        a = [pool[i] for i in idx]
        b = [pool[i] for i in range(len(pool)) if i not in s]
        hits += abs(u(a, b) - mid) >= obs - 1e-9
        n += 1
    return hits / n


def main(path, out=None):
    rows = {r["variant"]: r for r in json.load(open(path))}
    res = []
    for v in sorted(rows):
        fam = v.split("_")[0]
        base = f"{fam}_base"
        if v == base or base not in rows:
            continue
        ve = [per_episode(e) for e in rows[v]["per_episode"] if e["labelled"]]
        be = [per_episode(e) for e in rows[base]["per_episode"] if e["labelled"]]
        for key, label, only in MEASURES:
            if only and only != fam:
                continue
            x = [e[key] for e in ve if e[key] is not None]
            y = [e[key] for e in be if e[key] is not None]
            if not x or not y:
                continue
            res.append(dict(family=fam, variant=v, base=base, measure=label, n_variant=len(x), n_base=len(y),
                            variant_median=round(median(x), 3), base_median=round(median(y), 3),
                            direction="up" if median(x) > median(y) else "down" if median(x) < median(y) else "same",
                            p=round(exact_p(x, y), 3),
                            tasks_variant=sorted(e["task"] for e in ve), tasks_base=sorted(e["task"] for e in be)))
    print("| Variant | Measure | Variant median (n) | Base median (n) | p |")
    print("|---|---|---|---|---|")
    for r in res:
        flag = " *" if r["p"] < 0.05 else ""
        print(f"| {r['variant']} | {r['measure']} | {r['variant_median']:g} ({r['n_variant']}) | "
              f"{r['base_median']:g} ({r['n_base']}) | {r['p']}{flag} |")
    if out:
        json.dump(res, open(out, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None)
