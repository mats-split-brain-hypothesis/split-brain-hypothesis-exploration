"""Who are knnxs8's neighbours? For each read cell of a val bank at a late layer, the share of its 8 neighbours (knnx8
without same-carrier cells, the late partial mean of A's S14b-x) that come from the same family, and from the same family
and subfamily (the same prompt template), against the pool's base rates. Light (read-cell captures; Mac).

  python experiments/e1_knn_composition.py --layer 52
"""

import argparse
import json
from collections import Counter

import torch

from jlm import OUT, banks, capture, centres
from jlm.mu.clusters import FAMILIES


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", type=int, default=52)
    args = ap.parse_args()
    L = args.layer
    sub = {}
    for f in FAMILIES:
        for s in ("fit", "val"):
            for it in banks.load(f, s).items:
                sub[it["id"]] = (f, it.get("subfamily") or it.get("template") or "-")
    c = centres.make("knnxs8")
    first = True
    lines = [f"# knnxs8 neighbour composition (val read cells, L{L})", "",
             "| bank | cells | same family | base rate | same family + subfamily | base rate |", "|---|---|---|---|---|---|"]
    res = {}
    for f in FAMILIES:
        bank = banks.load(f, "val")
        items = capture.load(bank)
        groups = {it["id"]: it.get("pair_id") or it["id"] for it in bank.items}
        c.fit(items, f, groups)
        if first:  # pool row -> (family, subfamily) by the pool's group order (bench_fit: family by family, item order)
            rows = []
            for g in FAMILIES:
                for it in capture.load(banks.load(g, "fit")):
                    rows += [sub[it.id]] * len(it.positions)
            assert len(rows) == len(c.pool.groups)
            fams = Counter(r[0] for r in rows)
            subs = Counter(rows)
            first = False
        cells = centres.cell_refs(items, f, L, groups)
        H = torch.stack([next(x for x in items if x.id == cr.item).acts[L][cr.i].float() for cr in cells])
        nb = c._neighbours(centres.Batch(L, cells, H, {it.id: it for it in items}))
        sf = ss = n = 0
        bf = bs = 0.0
        for cr, row in zip(cells, nb.tolist(), strict=True):
            me = sub[cr.item]
            for r in row:
                sf += rows[r][0] == me[0]
                ss += rows[r] == me
                n += 1
            bf += fams[me[0]] / len(rows)
            bs += subs[me] / len(rows)
        res[f] = {"same_family": sf / n, "base_family": bf / len(cells), "same_sub": ss / n, "base_sub": bs / len(cells)}
        lines.append(f"| {f} | {len(cells)} | {sf / n:.2f} | {bf / len(cells):.2f} | {ss / n:.2f} | {bs / len(cells):.2f} |")
        print(lines[-1], flush=True)
    out = OUT / "analysis" / "xcheck-S14bx"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"knn-composition-L{L}.json").write_text(json.dumps(res, indent=1))
    (out / f"knn-composition-L{L}.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
