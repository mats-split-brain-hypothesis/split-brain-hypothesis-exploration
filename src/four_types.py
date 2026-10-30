"""Four types and the task -> check switch point on ImpossibleBench's impossible split, from two labelling passes.

  python src/four_types.py <pass1 measures.jsonl> <pass2 measures.jsonl> [--json out.json]

Both files come from src/persistence_measures.py (pass 1: the step 2 labels; pass 2: a second luna_med run on the same
40 episodes). Per episode:
- task-persistence P = new task-aimed candidates after the noticed obstacle (not the first candidate of a block), per
  1,000 reasoning tokens after the noticed obstacle (definitions.md: within-chain persistence);
- hesitation H = correctness doubts + legitimacy doubts per 1,000 reasoning tokens; H_legit = legitimacy doubts only.
  Legitimacy doubts are reported as "weighing a shortcut (as labelled)" (definitions v2.4): the labeller's count, an
  count including restatements; src/dl_check.py gives the precision-corrected rate.
Types: high/low P x hesitates/doesn't, split at the median within the 40 episodes (Qwen only). Each pass is typed on
its own (agreement k/40), and the main typing uses the mean of the two passes' values.
Switch point: the rejection round of the first new check-aimed candidate.
Continuous comparison (the main result; the types are secondary): hack vs no-hack episodes (verdict_enacted yes / no,
split left out), each measure the per-episode mean of the two passes; medians, pooled rates, and a two-sided
permutation p-value for the Mann-Whitney U (20,000 shuffles, seed 1). The sample keeps every hack episode and
subsamples the no-hack ones, so hack counts per type are case-control counts, not rates.
"""
import json
import random
import sys
from collections import Counter
from statistics import median


def load(path):
    return {r["id"]: r for r in map(json.loads, open(path)) if r["set"] == "IB impossible"}


def perm_p(x, y, n=20000, seed=1):
    """Two-sided permutation p-value for the Mann-Whitney U statistic (ties count half)."""
    u = lambda p, q: sum((pi > qi) + 0.5 * (pi == qi) for pi in p for qi in q)
    mid = len(x) * len(y) / 2
    obs = abs(u(x, y) - mid)
    pool, rng, hits = list(x) + list(y), random.Random(seed), 0
    for _ in range(n):
        rng.shuffle(pool)
        hits += abs(u(pool[:len(x)], pool[len(x):]) - mid) >= obs - 1e-9
    return (hits + 1) / (n + 1)


CONT = [  # (key, label, kind): count = per-episode count; per_k = per 1,000 reasoning tokens (pooled shown too)
    ("task_new_all", "New task-aimed candidates", "count"),
    ("task_new_all", "New task-aimed candidates", "per_k"),
    ("check_new_all", "New check-aimed candidates", "count"),
    ("check_new_all", "New check-aimed candidates", "per_k"),
    ("dc", "Correctness doubts", "per_k"),
    ("dl", "Weighing a shortcut (as labelled)", "per_k"),
    ("doubts", "Correctness doubts + weighing a shortcut", "per_k"),
    ("reasoning_tokens", "Reasoning tokens", "count"),
]


def continuous(a, b, ids):
    ep = {}
    for i in ids:
        if a[i]["verdict_enacted"] not in ("yes", "no"):
            continue
        e = {k: (a[i][k] + b[i][k]) / 2 for k in ("task_new_all", "check_new_all", "dc", "dl")}
        e["doubts"] = e["dc"] + e["dl"]
        e["reasoning_tokens"] = a[i]["reasoning_tokens"]
        e["hack"] = a[i]["verdict_enacted"] == "yes"
        ep[i] = e
    H = [e for e in ep.values() if e["hack"]]
    N = [e for e in ep.values() if not e["hack"]]
    rows = []
    for key, label, kind in CONT:
        val = (lambda e: e[key]) if kind == "count" else (lambda e: 1000 * e[key] / e["reasoning_tokens"])
        x, y = [val(e) for e in H], [val(e) for e in N]
        r = dict(measure=label, kind="per episode" if kind == "count" else "per 1,000 reasoning tokens",
                 hack_median=round(median(x), 2), nohack_median=round(median(y), 2), p=round(perm_p(x, y), 3),
                 hack_n=len(H), nohack_n=len(N))
        if kind == "per_k":
            tok = lambda rs: sum(e["reasoning_tokens"] for e in rs)
            r.update(hack_pooled=round(1000 * sum(e[key] for e in H) / tok(H), 2),
                     nohack_pooled=round(1000 * sum(e[key] for e in N) / tok(N), 2))
        rows.append(r)
    # How much of the hack group's pooled check-aimed count comes from its two longest episodes.
    top = sorted(H, key=lambda e: -e["reasoning_tokens"])[:2]
    conc = dict(top2_check=round(sum(e["check_new_all"] for e in top)), all_check=round(sum(e["check_new_all"] for e in H)),
                top2_tokens=sum(e["reasoning_tokens"] for e in top), all_tokens=sum(e["reasoning_tokens"] for e in H),
                top2_ids=sorted(i for i, e in ep.items() if e in top))
    # And how much of the no-hack group's pooled task-aimed count comes from its largest episode.
    big = max((i for i in ep if not ep[i]["hack"]), key=lambda i: ep[i]["task_new_all"])
    conc.update(nohack_top_id=big, nohack_top_task=round(ep[big]["task_new_all"]),
                nohack_all_task=round(sum(e["task_new_all"] for e in N)),
                nohack_top_tokens=ep[big]["reasoning_tokens"], nohack_all_tokens=sum(e["reasoning_tokens"] for e in N))
    print(f"\n## Hack ({len(H)}) vs no-hack ({len(N)}), mean of the two passes per episode\n")
    print("| Measure | Hack median | No-hack median | p | Pooled hack / no-hack |")
    print("|---|---|---|---|---|")
    for r in rows:
        pl = f"{r['hack_pooled']} / {r['nohack_pooled']}" if "hack_pooled" in r else "-"
        print(f"| {r['measure']} ({r['kind']}) | {r['hack_median']} | {r['nohack_median']} | {r['p']} | {pl} |")
    print(f"\nHack group's two longest episodes ({', '.join(conc['top2_ids'])}): {conc['top2_check']}/{conc['all_check']} "
          f"of its new check-aimed candidates, {conc['top2_tokens']:,}/{conc['all_tokens']:,} of its reasoning tokens")
    return dict(rows=rows, concentration=conc)


def typ(p, h, mp, mh):
    return f"{'high' if p > mp else 'low'} persistence, {'hesitates' if h > mh else 'little hesitation'}"


def main(p1_path, p2_path, out_path=None):
    a, b = load(p1_path), load(p2_path)
    ids = sorted(set(a) & set(b))
    P = lambda r: r["task_persist_cot_per_k"] or 0.0
    H = lambda r: r["dc_per_k"] + r["dl_per_k"]
    HL = lambda r: r["dl_per_k"]
    out = {"n": len(ids), "continuous": continuous(a, b, ids)}
    for name, hf in (("doubts (both kinds)", H), ("weighing a shortcut only", HL)):
        types = {}
        for tag, src in (("pass 1", a), ("pass 2", b)):
            mp, mh = median(P(src[i]) for i in ids), median(hf(src[i]) for i in ids)
            types[tag] = {i: typ(P(src[i]), hf(src[i]), mp, mh) for i in ids}
        agree = sum(types["pass 1"][i] == types["pass 2"][i] for i in ids)
        avgP = {i: (P(a[i]) + P(b[i])) / 2 for i in ids}
        avgH = {i: (hf(a[i]) + hf(b[i])) / 2 for i in ids}
        mp, mh = median(avgP.values()), median(avgH.values())
        avg_type = {i: typ(avgP[i], avgH[i], mp, mh) for i in ids}
        rows = []
        for t in sorted(set(avg_type.values())):
            es = [i for i in ids if avg_type[i] == t]
            yes = sum(a[i]["verdict_enacted"] == "yes" for i in es)
            no = sum(a[i]["verdict_enacted"] == "no" for i in es)
            rows.append(dict(hesitation=name, type=t, episodes=len(es), hacks=yes, hack_base=yes + no,
                             split=len(es) - yes - no,
                             stable=sum(types["pass 1"][i] == types["pass 2"][i] for i in es)))
        out[name] = dict(agreement=f"{agree}/{len(ids)}", split_points=dict(P=round(mp, 3), H=round(mh, 3)), types=rows)
        print(f"\n## Hesitation = {name}: the two passes give the same type in {agree}/{len(ids)} episodes. "
              f"Split points (mean of passes): persistence {mp:.2f}, hesitation {mh:.2f} per 1,000 tokens.\n")
        print("| Type (mean of two passes) | Episodes | Hacks (verdict yes / yes+no) | Same type in both passes |")
        print("|---|---|---|---|")
        for r in rows:
            print(f"| {r['type']} | {r['episodes']} | {r['hacks']}/{r['hack_base']} | {r['stable']}/{r['episodes']} |")
    # Does the low/high task-persistence hack split depend on where the cut falls?
    avgP = {i: (P(a[i]) + P(b[i])) / 2 for i in ids}
    vals = sorted(avgP.values())
    kn = lambda es: (sum(a[i]["verdict_enacted"] == "yes" for i in es), sum(a[i]["verdict_enacted"] in ("yes", "no") for i in es))
    sens = []
    for q in (0.3, 0.4, 0.5, 0.6, 0.7):
        cut = vals[int(q * len(vals)) - 1]
        lo, hi = kn([i for i in ids if avgP[i] <= cut]), kn([i for i in ids if avgP[i] > cut])
        sens.append(dict(split=f"{q:.0%}", cut=round(cut, 2), low=f"{lo[0]}/{lo[1]}", high=f"{hi[0]}/{hi[1]}"))
    out["split_sensitivity"] = sens
    print("\nTask-persistence split point vs hacks (low / high): " +
          "; ".join(f"{s['split']} {s['low']} / {s['high']}" for s in sens))
    sw = [(a[i]["switch_round"], b[i]["switch_round"]) for i in ids
          if a[i]["switch_turn"] is not None and b[i]["switch_turn"] is not None]
    same = sum(x == y for x, y in sw)
    c1, c2 = Counter(x for x, _ in sw), Counter(y for _, y in sw)
    print(f"\n## Task -> check switch: episodes with a check-aimed candidate in both passes {len(sw)}/{len(ids)}; "
          f"same rejection round in both {same}/{len(sw)}\n")
    print("| Round of the first check-aimed candidate | Pass 1 | Pass 2 |")
    print("|---|---|---|")
    for k in sorted(set(c1) | set(c2), key=lambda x: (x is None, x)):
        print(f"| {k} | {c1[k]} | {c2[k]} |")
    hk = [(a[i]["switch_round"], b[i]["switch_round"]) for i in ids if a[i]["verdict_enacted"] == "yes"
          and a[i]["switch_turn"] is not None and b[i]["switch_turn"] is not None]
    out["switch"] = dict(both=len(sw), n=len(ids), same_round=same,
                         pass1={str(k): v for k, v in c1.items()}, pass2={str(k): v for k, v in c2.items()},
                         hack_episodes_round0_both=sum(x == 0 and y == 0 for x, y in hk), hack_episodes=len(hk))
    print(f"\nHack episodes whose first check-aimed candidate comes before any rejection in both passes: "
          f"{out['switch']['hack_episodes_round0_both']}/{len(hk)}")
    if out_path:
        json.dump(out, open(out_path, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None)
