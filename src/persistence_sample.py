"""Stratified subset of Goodfire's Qwen 3.8 Max transcripts for the persistence deep dive (agent 4, step 2).

  python src/persistence_sample.py <data dir> <aw dir> <out.json> [--fill <candidates.jsonl> <labels.jsonl>]

<data dir> is logs/data (goodfire/ = ImpossibleBench, goodfire_swe/ = SWE-bench Verified and DeepSWE).
<aw dir> holds candidates_all.jsonl and labels_final.jsonl from src/awareness_llm.py; --fill adds the passages that
run left unlabelled (logs/ib_persistence/aw_fill/).

Strata: Goodfire's verdict_enacted (yes / split / no: a hack made or attempted, judges split, none) x alignment-eval
awareness (any passage labelled A). Each stratum gets a fixed quota (QUOTAS below); hacks and A are oversampled
because they are rare, so every episode carries a weight = stratum size / episodes drawn, for population estimates.
Within a stratum the draw is random.Random(SEED). If a stratum has fewer episodes than its quota, all are taken and
the remainder goes to the same verdict's other A stratum, then to "no".
Episode ids match src/cot_labels.py ("<traces file stem>|<row>").
"""
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

SEED = 20261021
SETS = {  # name: (traces file, judge file, awareness bench keys)
    "IB impossible": ("goodfire/qwen_traces.jsonl", "goodfire/qwen_judge_rollouts.jsonl", "ImpossibleBench (impossible)"),
    "IB possible": ("goodfire/qwen_traces.jsonl", "goodfire/qwen_judge_rollouts.jsonl", "ImpossibleBench (possible)"),
    "SWE-bench Verified": ("goodfire_swe/swebench-verified-qwen3.8-2.4t-a95b-fp8-nohack.traces.jsonl",
                           "goodfire_swe/swebench-verified-qwen3.8-2.4t-a95b-fp8-nohack.judge_rollouts.jsonl",
                           "SWE-bench Verified"),
    "DeepSWE": ("goodfire_swe/deepswe-qwen3.8-2.4t-a95b-fp8.traces.jsonl",
                "goodfire_swe/deepswe-qwen3.8-2.4t-a95b-fp8.judge_rollouts.jsonl", "DeepSWE"),
}
# (verdict_enacted, A) -> episodes to draw
QUOTAS = {
    "IB impossible": {("yes", True): 5, ("yes", False): 4, ("split", True): 4, ("split", False): 3,
                      ("no", True): 12, ("no", False): 12},
    "IB possible": {("yes", True): 1, ("yes", False): 2, ("split", True): 1, ("split", False): 2,
                    ("no", True): 2, ("no", False): 12},
    "SWE-bench Verified": {("yes", True): 1, ("yes", False): 14, ("split", True): 0, ("split", False): 3,
                           ("no", True): 1, ("no", False): 11},
    "DeepSWE": {("yes", True): 1, ("yes", False): 14, ("split", True): 0, ("split", False): 3,
                ("no", True): 1, ("no", False): 11},
}


def a_episodes(aw, fill):
    """{(bench key, row)} of Qwen episodes with at least one passage labelled A."""
    pairs = [(Path(aw) / "candidates_all.jsonl", Path(aw) / "labels_final.jsonl")] + ([tuple(fill)] if fill else [])
    out = set()
    for cands, labels in pairs:
        pos = {json.loads(l)["id"] for l in open(labels) if json.loads(l)["A"]}
        for l in open(cands):
            r = json.loads(l)
            if r["model"] == "Qwen" and r["id"] in pos:
                out.add((r["bench"], r["row"]))
    return out


def main(data, aw, out_path, fill):
    has_a = a_episodes(aw, fill)
    rng = random.Random(SEED)
    picked, table = [], []
    for name, (tr, jd, key) in SETS.items():
        stem = Path(tr).name.replace(".traces.jsonl", "").replace("_traces.jsonl", "")
        strata = defaultdict(list)
        with open(Path(data) / tr) as ft, open(Path(data) / jd) as fj:
            for row, (lt, lj) in enumerate(zip(ft, fj)):
                j = json.loads(lj)
                if name.startswith("IB"):
                    split = j["split"]
                    if (name == "IB possible") != (split == "original"):
                        continue
                else:
                    split = None
                strata[(j["verdict_enacted"], (key, row) in has_a)].append(dict(id=f"{stem}|{row}", row=row, split=split,
                                                                               task=j["task"]))
        quota = dict(QUOTAS[name])
        # Move unfillable quota to the other A stratum of the same verdict, then to ("no", False).
        for (v, a), q in list(quota.items()):
            short = q - len(strata[(v, a)])
            if short > 0:
                quota[(v, a)] = len(strata[(v, a)])
                spare = len(strata[(v, not a)]) - quota.get((v, not a), 0)
                give = min(short, max(spare, 0))
                quota[(v, not a)] = quota.get((v, not a), 0) + give
                quota[("no", False)] += short - give
        for (v, a), q in sorted(quota.items()):
            pool = strata[(v, a)]
            draw = rng.sample(pool, q) if q else []
            w = len(pool) / q if q else 0
            table.append((name, v, a, len(pool), q))
            for e in draw:
                picked.append(dict(**e, set=name, verdict_enacted=v, alignment_eval=a, stratum_size=len(pool),
                                   weight=round(w, 3)))
    json.dump(dict(seed=SEED, quotas={k: {f"{v}|{'A' if a else 'noA'}": q for (v, a), q in d.items()}
                                      for k, d in QUOTAS.items()}, episodes=picked), open(out_path, "w"), indent=1)
    print("| Set | verdict_enacted | alignment-eval (A) | Episodes in stratum | Drawn |")
    print("|---|---|---|---|---|")
    for name, v, a, n, q in table:
        print(f"| {name} | {v} | {'yes' if a else 'no'} | {n} | {q} |")
    print(f"\n{len(picked)} episodes written to {out_path}")


if __name__ == "__main__":
    fill = sys.argv[sys.argv.index("--fill") + 1: sys.argv.index("--fill") + 3] if "--fill" in sys.argv else None
    main(sys.argv[1], sys.argv[2], sys.argv[3], fill)
