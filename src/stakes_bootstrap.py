"""Is "stakes don't matter" a real null? Task-clustered bootstrap of pooled-rate ratios, with a positive control
(evaluation words in the instruction) on the same data, labeller and method. Agent 6, 2026-10-22; plan and reading in
notes/stakes.md, written before computing.

  python src/stakes_bootstrap.py   -> logs/stakes/cot/bootstrap.json, prints a table

Rates: counts per 1,000 thinking tokens pooled over a group's trials (src/stakes_cot.py). Each bootstrap draw
resamples tasks with replacement within each group (both trials of a task kept together); 10,000 draws, seed 6;
95% percentile intervals of the ratio of two groups' pooled rates.
"""
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stakes_cot import MEASURES  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LABELS = [ROOT / "logs/stakes/cot/v34_main.jsonl", ROOT / "logs/stakes/cot/v34_rest.jsonl"]
STAKES = ["new candidates (persistence)", "correctness doubt", "legitimacy doubt"]
CONTROL = ["legitimacy doubt", "G (grading)", "B (capability eval)"]
COMPARISONS = [("high", "low_cuefree", STAKES, "stakes"), ("high", "medium_control", STAKES, "stakes"),
               ("low_cued", "low_cuefree", CONTROL, "control")]
B, SEED = 10_000, 6


def load():
    trials = {t["trial"]: t for t in json.load(open(ROOT / "logs/stakes/trial_table.json"))}
    counts = defaultdict(lambda: defaultdict(int))
    seen = set()
    for p in LABELS:
        for line in open(p):
            u = json.loads(line)
            if u.get("channel") != "reasoning":
                continue
            key = (u["episode"], u["turn"], u["unit"])
            if key in seen:
                continue
            seen.add(key)
            for name in set(STAKES + CONTROL):
                if MEASURES[name](u):
                    counts[u["episode"]][name] += 1
    tasks = defaultdict(lambda: defaultdict(list))  # group -> task -> trials
    for t, r in trials.items():
        tasks[r["group"]][r["task"]].append(t)
    return trials, counts, tasks


def pooled(task_list, tasks_g, trials, counts, m):
    ts = [t for task in task_list for t in tasks_g[task]]
    tk = sum(trials[t]["thinking_k"] for t in ts)
    return sum(counts[t][m] for t in ts) / tk if tk else float("nan")


def _betacf(a, b, x):
    """Continued fraction for the regularized incomplete beta (Numerical Recipes)."""
    import math
    qab, qap, qam, c, d = a + b, a + 1, a - 1, 1.0, 1 - (a + b) * x / (a + 1)
    d = 1 / (d if abs(d) > 1e-300 else 1e-300)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1 + aa / c if abs(1 + aa / c) > 1e-300 else 1e-300
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1 + aa / c if abs(1 + aa / c) > 1e-300 else 1e-300
        de = d * c
        h *= de
        if abs(de - 1) < 1e-12:
            break
    return h


def t_cdf(t, df):
    import math
    x = df / (df + t * t)
    a, b = df / 2, 0.5
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x))
    ib = bt * _betacf(a, b, x) / a if x < (a + 1) / (a + b + 2) else 1 - bt * _betacf(b, a, 1 - x) / b
    return 1 - 0.5 * ib if t > 0 else 0.5 * ib


def t_quantile(p, df):
    lo, hi = 0.0, 100.0
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if t_cdf(mid, df) < p else (lo, mid)
    return (lo + hi) / 2


def welch_log(ta, tb, tasks_a, tasks_b, trials, counts, m):
    """Sensitivity check (verifier): Welch t-interval on per-task log rates, unweighted. Returns ratio, lo, hi."""
    import math
    la = [math.log(pooled([t], tasks_a, trials, counts, m)) for t in ta if pooled([t], tasks_a, trials, counts, m) > 0]
    lb = [math.log(pooled([t], tasks_b, trials, counts, m)) for t in tb if pooled([t], tasks_b, trials, counts, m) > 0]
    if len(la) < 2 or len(lb) < 2:
        return None, None, None, len(ta) - len(la) + len(tb) - len(lb)
    ma, mb = sum(la) / len(la), sum(lb) / len(lb)
    va = sum((x - ma) ** 2 for x in la) / (len(la) - 1)
    vb = sum((x - mb) ** 2 for x in lb) / (len(lb) - 1)
    se2 = va / len(la) + vb / len(lb)
    df = se2 ** 2 / ((va / len(la)) ** 2 / (len(la) - 1) + (vb / len(lb)) ** 2 / (len(lb) - 1))
    q = t_quantile(0.975, df)
    d = ma - mb
    return (round(math.exp(d), 2), round(math.exp(d - q * se2 ** 0.5), 2), round(math.exp(d + q * se2 ** 0.5), 2),
            len(ta) - len(la) + len(tb) - len(lb))


def main():
    trials, counts, tasks = load()
    rng = random.Random(SEED)
    out = []
    for a, b, ms, kind in COMPARISONS:
        ta, tb = sorted(tasks[a]), sorted(tasks[b])
        for m in ms:
            ra, rb = pooled(ta, tasks[a], trials, counts, m), pooled(tb, tasks[b], trials, counts, m)
            draws = []
            for _ in range(B):
                sa = [rng.choice(ta) for _ in ta]
                sb = [rng.choice(tb) for _ in tb]
                x, y = pooled(sa, tasks[a], trials, counts, m), pooled(sb, tasks[b], trials, counts, m)
                draws.append(x / y if y > 0 else float("inf"))
            draws.sort()
            lo, hi = draws[int(0.025 * B)], draws[int(0.975 * B) - 1]
            # Leave one task out (either group): how far a single task moves the ratio.
            loo = []
            for drop in ta:
                y = pooled(tb, tasks[b], trials, counts, m)
                loo.append(pooled([t for t in ta if t != drop], tasks[a], trials, counts, m) / y if y else float("nan"))
            for drop in tb:
                y = pooled([t for t in tb if t != drop], tasks[b], trials, counts, m)
                loo.append(ra / y if y else float("nan"))
            out.append({"kind": kind, "a": a, "b": b, "measure": m, "tasks_a": len(ta), "tasks_b": len(tb),
                        "rate_a": round(ra, 3), "rate_b": round(rb, 3), "ratio": round(ra / rb, 2) if rb else None,
                        "lo": round(lo, 2), "hi": round(hi, 2) if hi != float("inf") else None,
                        "zero_draws_b": sum(1 for d in draws if d == float("inf")),
                        "leave_one_task_out": [round(min(loo), 2), round(max(loo), 2)],
                        "welch_per_task_log": dict(zip(("ratio", "lo", "hi", "tasks_with_zero_dropped"),
                                                       welch_log(ta, tb, tasks[a], tasks[b], trials, counts, m))),
                        "counts": [sum(counts[t][m] for task in ta for t in tasks[a][task]),
                                   sum(counts[t][m] for task in tb for t in tasks[b][task])]})
    passing = [r for r in out if r["kind"] == "control" and (r["lo"] > 1 or (r["hi"] is not None and r["hi"] < 1))]
    R = min(max(r["ratio"], 1 / r["ratio"]) for r in passing) if passing else None
    for r in out:
        if r["kind"] != "stakes":
            continue
        hi = r["hi"] if r["hi"] is not None else float("inf")
        r["excludes_1"] = r["lo"] > 1 or hi < 1
        r["rules_out"] = round(max(hi, 1 / r["lo"]), 2) if r["lo"] > 0 else None  # smallest k with CI inside (1/k, k)
        r["verdict"] = ("no control passed" if R is None else
                        "real null (rules out an effect as large as the cue effect)" if (1 / R < r["lo"] and hi < R)
                        else "underpowered (interval reaches the cue effect's size)")
    # Sensitivity (verifier): the same rule with the per-task Welch interval.
    wpass = [r for r in out if r["kind"] == "control" and r["welch_per_task_log"]["lo"] is not None
             and (r["welch_per_task_log"]["lo"] > 1 or r["welch_per_task_log"]["hi"] < 1)]
    for r in out:
        if r["kind"] == "stakes":
            r["verdict_welch"] = ("underpowered: no control ratio excludes 1 under this interval" if not wpass else
                                  "see bootstrap rule")
    res = {"control_passing": [f"{r['measure']} {r['ratio']} [{r['lo']}, {r['hi']}]" for r in passing],
           "control_passing_welch": [r["measure"] for r in wpass],
           "R_smallest_passing_control_ratio": R, "rows": out,
           "method": "pooled rate ratios; task-clustered bootstrap within groups, 10,000 draws, seed 6, 95% percentile"}
    (ROOT / "logs/stakes/cot/bootstrap.json").write_text(json.dumps(res, indent=1))
    for r in out:
        print(f"{r['kind']:8s} {r['a']:>11s} vs {r['b']:<15s} {r['measure']:30s} {r['rate_a']:7.3f} {r['rate_b']:7.3f} "
              f"ratio {r['ratio']} [{r['lo']}, {r['hi']}] loo {r['leave_one_task_out']} n {r['counts']} "
              f"welch {r['welch_per_task_log']} "
              + (f"rules out >{r['rules_out']}x  {r['verdict']}"
                                                              if r["kind"] == "stakes" else ""))
    print("control passing:", res["control_passing"], "| R =", R)


if __name__ == "__main__":
    main()
