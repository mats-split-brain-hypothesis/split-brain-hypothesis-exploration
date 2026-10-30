"""S24d: val2 + val3 pooled (items pooled within family, macro over typo / association / multihop), each arm's Δ vs fam
with a paired bootstrap (resampling items within family), per split beside it, and the pairwise differences between
the leading arms. Strict, cos. Writes out/analysis/S24/pooled.md.

  python experiments/s24_pool.py
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate import parse_arm, read_jsonl, slug

from jlm import OUT, banks, score

FAMS = ["typo", "association", "multihop"]
ARMS = {"zero": "zero|cos", "fam": "fam@fit|cos",
        "S14bL": "sched:40:kmx64+s14:template:64:mean=knnxd8l:a=0.5@fit|cos",
        "S14b-knnxs8": "sched:40:kmx64+s14:template:64:mean=knnxs8:a=0.5@fit|cos",
        "S20x": "s20xt:1@fit|cos", "s20xon": "s20xon:1:kmx64@fit|cos",
        "S21b": "sched:40:s20xon:1:kmx64+s14:template:64:mean=kmx64:a=0.5@fit|cos",
        "rand.S14bL": "rand.sched:40:kmx64+s14:template:64:mean=knnxd8l:a=0.5@fit|cos",
        "rand.S20x": "rand.s20xt:1@fit|cos", "rand.s20xon": "rand.s20xon:1:kmx64@fit|cos"}
LEAD = ["S14bL", "S14b-knnxs8", "S20x", "s20xon", "S21b"]
#: post-read matched nulls (famr: fam + a random direction with the norm of the arm's change from fam), 3 seeds averaged
NULLS = {"null.S20x": "s20xt:1", "null.s20xon": "s20xon:1:kmx64",
         "null.S14bL": "sched:40:kmx64+s14:template:64:mean=knnxd8l:a=0.5"}
for _n, _inner in NULLS.items():
    for _s in range(3):
        ARMS[f"{_n}.s{_s}"] = f"famr:{_s}:{_inner}@fit|cos"


def load(split: str) -> dict:
    P = {}
    import json
    for f in FAMS:
        b = banks.load(f, split)
        scored = set(json.loads((OUT / "eval" / f / split / "summary.json").read_text())["result"]["scored_ids"])
        for name, arm in ARMS.items():
            p = OUT / "eval" / f / split / slug(parse_arm(arm)) / "readouts.jsonl"
            if p.exists():
                for i, v in score.strict_items(read_jsonl(p), b).items():
                    if i in scored:  # the bank's scored items (leaky items excluded), as the pipeline reports
                        P.setdefault(name, {})[(split, f, i)] = v
    return P


def macro_delta(P, a, ref, keys_by_fam, rng=None):
    tot = 0.0
    for f, ks in keys_by_fam.items():
        ks = [rng.choice(ks) for _ in ks] if rng else ks
        tot += sum(P[a][k] - P[ref][k] for k in ks) / len(ks)
    return tot / len(keys_by_fam)


def interval(P, a, ref, kb):
    rng = random.Random(0)
    bs = sorted(macro_delta(P, a, ref, kb, rng) for _ in range(2000))
    return macro_delta(P, a, ref, kb), bs[50], bs[1949]


def main() -> None:
    P = {}
    for split in ("val2", "val3"):
        for k, v in load(split).items():
            P.setdefault(k, {}).update(v)
    for n in NULLS:  # seed-averaged null (pass rate in [0, 1] per item)
        seeds = [P[f"{n}.s{s}"] for s in range(3) if f"{n}.s{s}" in P]
        if len(seeds) == 3:
            P[n] = {k: sum(x[k] for x in seeds) / 3 for k in set.intersection(*(set(x) for x in seeds))}
            ARMS[n] = "(mean of 3 seeds)"
    base = set(P["fam"])
    lines = ["# S24d: val2 + val3 pooled (strict, cos; Δ vs fam, macro over typo / association / multihop, paired bootstrap)", ""]
    for scope in ("val2", "val3", "pooled"):
        kb0 = {f: sorted(k for k in base if k[1] == f and (scope == "pooled" or k[0] == scope)) for f in FAMS}
        n = {f: len(v) for f, v in kb0.items()}
        lines += [f"## {scope} (n {n})", "", "| arm | macro pass | Δ fam [95 %] |", "|---|---|---|"]
        for a in ARMS:
            if a not in P:
                continue
            kb = {f: [k for k in ks if k in P[a]] for f, ks in kb0.items()}
            if any(len(kb[f]) < len(kb0[f]) for f in FAMS):
                lines.append(f"| {a} | (not read on every split of this scope) | |")
                continue
            m = sum(sum(P[a][k] for k in ks) / len(ks) for ks in kb.values()) / len(kb)
            d, lo, hi = interval(P, a, "fam", kb)
            lines.append(f"| {a} | {m:.3f} | {d:+.3f} [{lo:+.3f}, {hi:+.3f}] |")
        kb = kb0
        if scope == "pooled":
            lines += ["", "Pairwise (row minus column, pooled, paired bootstrap):", "",
                      "| | " + " | ".join(LEAD) + " |", "|---" * (len(LEAD) + 1) + "|"]
            for a in LEAD:
                cells = []
                for b in LEAD:
                    if a == b:
                        cells.append("–")
                        continue
                    d, lo, hi = interval(P, a, b, kb)
                    cells.append(f"{d:+.3f} [{lo:+.3f}, {hi:+.3f}]")
                lines.append(f"| {a} | " + " | ".join(cells) + " |")
        if scope == "pooled" and all(n in P for n in NULLS):
            lines += ["", "Arm minus its matched null (post-read control; pooled, paired bootstrap):", ""]
            for arm, n in (("S20x", "null.S20x"), ("s20xon", "null.s20xon"), ("S14bL", "null.S14bL")):
                d, lo, hi = interval(P, arm, n, kb)
                lines.append(f"- {arm} - {n}: {d:+.3f} [{lo:+.3f}, {hi:+.3f}]")
        lines.append("")
    out = OUT / "analysis" / "S24"
    out.mkdir(parents=True, exist_ok=True)
    (out / "pooled.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
