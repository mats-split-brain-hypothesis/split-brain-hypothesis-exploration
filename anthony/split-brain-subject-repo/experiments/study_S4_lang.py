"""S4c: does knnx8 remove the language on multilingual_mt? Per-cell decode of what it subtracts beyond fam.

  python experiments/study_S4_lang.py --device cuda

For each multilingual_mt val cell and layer, d = g_knnx8 - g_fam (fam = the family's fit mean); reads L(d) with the
J-lens (cos) and reports the best rank of the item's language-unit pieces and of its concept-unit pieces (mtproxy
units), against the same ranks for L(-d) and for a shuffled d (another cell's). If the language pieces rank high in
L(d) and not in the controls, knnx8's extra subtraction is the language. Analysis only (reads targets to score).
"""

import argparse
import json

import numpy as np
import torch

from jlm import OUT, banks, capture, centres, mtproxy
from jlm.lens import Lens


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--layers", default="36,44,52,60")
    args = ap.parse_args()
    layers = [int(x) for x in args.layers.split(",")]
    bank, ref = banks.load("multilingual_mt", "val"), banks.load("multilingual_mt", "fit")
    items, ref_items = capture.load(bank), capture.load(ref)
    lens = Lens(layers, args.device)
    units = mtproxy.units_of(bank, lens.tokenizer, lens.display)
    knn, fam = centres.make("knnx8"), centres.make("fam")
    knn.fit(ref_items, "multilingual_mt")
    fam.fit(ref_items, "multilingual_mt")
    res = {}
    rng = np.random.default_rng(0)
    for L in layers:
        cells = centres.cell_refs(items, "multilingual_mt", L)
        H = torch.stack([it.acts[L][c.i].float() for c, it in zip(cells, [i for i in items for _ in i.positions], strict=True)])
        b = centres.Batch(L, cells, H, {it.id: it for it in items})
        D = (H - centres.apply(knn, b)) - (H - centres.apply(fam, b))  # g_knn - g_fam
        perm = rng.permutation(len(D))
        out = {"d": [], "-d": [], "shuf": []}
        for name, X in (("d", D), ("-d", -D), ("shuf", D[perm])):
            S = lens.scores(X, L, "cos")
            order = S.argsort(dim=1, descending=True)
            rank = torch.empty_like(order)
            rank.scatter_(1, order, torch.arange(order.shape[1], device=order.device).expand_as(order))
            for j, c in enumerate(cells):
                us = {u.role: u for u in units.get(c.item, [])}
                r = {role: int(rank[j, list(u.ids)].min()) if u.ids else None for role, u in us.items()}
                out[name].append(r)
        res[L] = {k: {role: float(np.median([r[role] for r in v if r.get(role) is not None]))
                      for role in ("language", "concept")} for k, v in out.items()}
        res[L]["top10_share"] = {k: {role: float(np.mean([r[role] < 10 for r in v if r.get(role) is not None]))
                                     for role in ("language", "concept")} for k, v in out.items()}
        print(L, json.dumps(res[L]), flush=True)
    d = OUT / "analysis" / "S4" / "extra"
    d.mkdir(parents=True, exist_ok=True)
    (d / "lang-decode.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
