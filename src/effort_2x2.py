"""Run 2's 2x2 (notes section 8, design C): keep vs strip earlier <think> blocks x low vs xhigh effort.

    python src/effort_2x2.py

Reads logs/ib_persistence/effort_replay/replays.jsonl (keep) and replays_stripped.jsonl (strip). Per cell: replies,
reasoning tokens (median, the manipulation check, reported first), act k/n with Wilson intervals, reply kinds.
Registered comparisons, each a two-sided exact sign-flip over states (and over the 5 tasks):
- strip-low vs strip-xhigh, 18 states (strip's primary set);
- strip-low vs keep-low, the 18 shared states;
- keep-low vs keep-xhigh, all 19 states (the harness question).
Writes logs/ib_persistence/effort_replay/analysis_2x2.json; with --hand, applies the hand verdicts for acts the
registered scorer missed (hand_act_overrides.json) and writes analysis_2x2_hand.json.
"""
import json
from collections import Counter
from pathlib import Path

D = Path("logs/ib_persistence/effort_replay")


def wilson(k, n, z=1.96):
    import math
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (round((c - h) / d, 3), round((c + h) / d, 3))


def load(name, col):
    return [dict(json.loads(l), col=col) for l in open(D / name) if "error" not in json.loads(l)]


def signflip(diffs):
    obs = abs(sum(diffs))
    nz = [d for d in diffs if d != 0]
    if not nz:
        return 1.0
    hits = sum(abs(sum(d if (m >> i) & 1 else -d for i, d in enumerate(nz))) >= obs - 1e-9 for m in range(2 ** len(nz)))
    return round(hits / 2 ** len(nz), 4)


def rate(rows, cell, key):
    rs = [r for r in rows if (r["col"], r["arm"]) == cell and key(r)]
    return (sum(r["act"] for r in rs) / len(rs)) if rs else None


def compare(rows, a, b, states):
    """Mean of (b - a) act rates over states and over tasks, with sign-flip p (positive = b higher)."""
    ds = [rate(rows, b, lambda r, s=s: r["state"] == s) - rate(rows, a, lambda r, s=s: r["state"] == s) for s in states]
    tasks = sorted({s.split("|")[1] for s in states})
    dt = [rate(rows, b, lambda r, t=t: r["task"] == t and r["state"] in states)
          - rate(rows, a, lambda r, t=t: r["task"] == t and r["state"] in states) for t in tasks]
    ka = sum(r["act"] for r in rows if (r["col"], r["arm"]) == a and r["state"] in states)
    na = sum(1 for r in rows if (r["col"], r["arm"]) == a and r["state"] in states)
    kb = sum(r["act"] for r in rows if (r["col"], r["arm"]) == b and r["state"] in states)
    nb = sum(1 for r in rows if (r["col"], r["arm"]) == b and r["state"] in states)
    return dict(a=f"{a[0]}-{a[1]}", b=f"{b[0]}-{b[1]}", states=len(states), a_act=f"{ka}/{na}", b_act=f"{kb}/{nb}",
                mean_diff_states=round(sum(ds) / len(ds), 3), p_states=signflip(ds),
                tasks=len(tasks), mean_diff_tasks=round(sum(dt) / len(dt), 3), p_tasks=signflip(dt))


def main():
    import sys
    rows = load("replays.jsonl", "keep") + load("replays_stripped.jsonl", "strip")
    hand = "--hand" in sys.argv  # apply the hand verdicts for acts the registered scorer missed
    if hand:
        ov = json.load(open(D / "hand_act_overrides.json"))["missed"]
        hits = 0
        for o in ov:
            for r in rows:
                if (r["col"] == o["column"] and o["state_key"] in r["state"] and r["task"] == o["task"]
                        and r["arm"] == o["arm"] and r["k"] == o["k"]):
                    assert not r["act"], o
                    r["act"] = True
                    hits += 1
        assert hits == len(ov), (hits, len(ov))
    strip_primary = sorted({r["state"] for r in rows if r["col"] == "strip" and not r["trick_in_context"]})
    all_states = sorted({r["state"] for r in rows})
    res = dict(cost=round(sum(r["cost"] or 0 for r in rows), 3), replies=len(rows), cells={})
    for col in ("keep", "strip"):
        for arm in ("low", "xhigh"):
            sts = all_states if col == "keep" else strip_primary
            rs = [r for r in rows if r["col"] == col and r["arm"] == arm and r["state"] in sts]
            toks = sorted(r["reasoning_tokens"] or 0 for r in rs)
            k = sum(r["act"] for r in rs)
            res["cells"][f"{col}-{arm}"] = dict(
                states=len(sts), replies=len(rs), reasoning_tokens_median=toks[len(toks) // 2],
                reasoning_tokens_iqr=(toks[len(toks) // 4], toks[3 * len(toks) // 4]), act=f"{k}/{len(rs)}",
                rate=round(k / len(rs), 3), wilson=wilson(k, len(rs)),
                kinds=dict(sorted(Counter(r["kind"] for r in rs).items())))
    res["strip_low_vs_strip_xhigh"] = compare(rows, ("strip", "low"), ("strip", "xhigh"), strip_primary)
    res["strip_low_vs_keep_low"] = compare(rows, ("strip", "low"), ("keep", "low"), strip_primary)
    res["keep_low_vs_keep_xhigh"] = compare(rows, ("keep", "low"), ("keep", "xhigh"), all_states)
    res["strip_xhigh_vs_keep_xhigh"] = compare(rows, ("strip", "xhigh"), ("keep", "xhigh"), strip_primary)
    res["scoring"] = "hand-corrected (hand_act_overrides.json)" if hand else "registered (TRICKS signatures)"
    json.dump(res, open(D / ("analysis_2x2_hand.json" if hand else "analysis_2x2.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
