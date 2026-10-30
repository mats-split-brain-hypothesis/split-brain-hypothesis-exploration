"""U4 cut 4: does the J++ vs J-lens gap concentrate in label-free regimes? (studies/U4.md)

  python experiments/study_U4_clusters.py --k 64 --layer 44

Routes every val read cell of the single-token families (and UM) to the bench-pool k-means cluster that the S4 centre
``kmx<k>`` uses (fit at --layer), and reports, per cluster with >= 5 items, the rate at which an item's best target
rank (any cell, any layer; rank sidecars) is inside the top 10 under zero|cos, jpp:zero|cos, fam@fit|cos and
kmx<k>@fit|cos: the J++ gap and the cluster mean's gain side by side. Analysis only (looks at stored ranks).
"""

import argparse
import json
from collections import defaultdict

import numpy as np
import torch

from jlm import OUT, banks, capture, score
from jlm.mu import clusters

FAMS = ["typo", "association", "basic_readout", "multihop", "multilingual", "user_modeling"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=64)
    ap.add_argument("--layer", type=int, default=44)
    args = ap.parse_args()
    c = clusters.ClusterMean(args.k, "bench")
    c.fit([], "", None)
    arms = ["zero__cos", "jpp~zero__cos", "fam-at-fit__cos", f"kmx{args.k}-at-fit__cos"]
    by = defaultdict(lambda: defaultdict(list))
    for f in FAMS:
        items = capture.load(banks.load(f, "val"))
        ranks = {a: score.best_rank(json.loads(l) for l in (OUT / "eval" / f / "val" / a / "ranks.jsonl").read_text().splitlines())
                 for a in arms}
        for it in items:
            cl = Counter_mode(c.assign(it.acts[args.layer].float(), args.layer).tolist())
            by[cl]["fam"].append(f)
            for a in arms:
                by[cl][a].append(ranks[a][it.id] < 10)
    rows = []
    for cl, d in by.items():
        n = len(d["fam"])
        if n < 5:
            continue
        r = {a: float(np.mean(d[a])) for a in arms}
        fams = {f: d["fam"].count(f) for f in set(d["fam"])}
        rows.append((cl, n, fams, r))
    rows.sort(key=lambda x: -(x[3]["jpp~zero__cos"] - x[3]["zero__cos"]))
    lines = [f"# U4 cut 4: J++ gap by kmx{args.k} cluster (L{args.layer}, val, top-10 by best rank)", "",
             "| cluster | n | families | zero | J++ | fam | kmx | J++ - zero | kmx - zero |", "|---|---|---|---|---|---|---|---|---|"]
    for cl, n, fams, r in rows:
        z, j, fm, km = (r[a] for a in arms)
        lines.append(f"| {cl} | {n} | {', '.join(f'{k} {v}' for k, v in sorted(fams.items(), key=lambda x: -x[1]))} | "
                     f"{z:.2f} | {j:.2f} | {fm:.2f} | {km:.2f} | {j - z:+.2f} | {km - z:+.2f} |")
    gj = np.array([r[arms[1]] - r[arms[0]] for _, _, _, r in rows])
    gk = np.array([r[arms[3]] - r[arms[0]] for _, _, _, r in rows])
    w = np.array([n for _, n, _, _ in rows])
    corr = float(np.corrcoef(gj, gk)[0, 1])
    lines += ["", f"Across clusters (n >= 5): corr(J++ gap, kmx gain) = {corr:+.2f}; size-weighted mean J++ gap "
              f"{np.average(gj, weights=w):+.3f}, kmx gain {np.average(gk, weights=w):+.3f}."]
    d = OUT / "analysis" / "U4" / "extra"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"clusters-k{args.k}-L{args.layer}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def Counter_mode(xs):
    return max(set(xs), key=xs.count)


if __name__ == "__main__":
    main()
