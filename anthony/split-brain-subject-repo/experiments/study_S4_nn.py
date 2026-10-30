"""S4 deep dive: who are a read cell's nearest pooled fit cells (knnx), per family (studies/S4.md).

  python experiments/study_S4_nn.py --k 8 --layers 28,44,56

Per family (val cells routed into the bench fit pool): the share of the k neighbours from the cell's own family, with
the same read token, at the same relative position (index from the end), and the mean Jaccard overlap of prompt
words (lower-cased alphabetic words of 4+ letters) between the cell's item and its neighbours' items, against the
same overlap for k random own-family fit items: the content-sharing check for kNN means. No targets.
"""

import argparse
import json
import random
import re
from collections import defaultdict

import torch

from jlm import OUT, banks, capture
from jlm.mu import clusters


def words(it) -> set[str]:
    return {w.lower() for w in re.findall(r"[A-Za-z]{4,}", "".join(it.decoded))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--layers", default="28,44,56")
    args = ap.parse_args()
    fitcaps = {f: capture.load(banks.load(f, "fit")) for f in clusters.FAMILIES}
    rows_item, rows_rel = [], []  # pool row -> (family, item), rel position
    for f in clusters.FAMILIES:
        for it in fitcaps[f]:
            for i in range(len(it.positions)):
                rows_item.append((f, it))
                rows_rel.append(len(it.decoded) - 1 - it.idx[i])
    W = {id(it): words(it) for f in fitcaps for it in fitcaps[f]}
    c = clusters.NearestMean(args.k, "bench")
    c.fit([], "", None)
    P = c.pool
    rng = random.Random(0)
    out, lines = {}, ["| L | family | own family | same token | same pos-from-end | prompt-word Jaccard nn / random own-family |",
                      "|---|---|---|---|---|---|"]
    for L in map(int, args.layers.split(",")):
        U, centre = clusters.unit_space(P.X[L].float())
        for f in clusters.FAMILIES:
            items = capture.load(banks.load(f, "val"))
            H = torch.cat([it.acts[L].float() for it in items])
            meta = [(it, i) for it in items for i in range(len(it.positions))]
            idx = (clusters.unit_space(H, centre)[0] @ U.T).topk(args.k, dim=1).indices
            s = defaultdict(list)
            for (it, i), nn in zip(meta, idx.tolist(), strict=True):
                wi, tok, rel = words(it), it.token(i), len(it.decoded) - 1 - it.idx[i]
                for j in nn:
                    s["fam"].append(P.fams[j] == f)
                    s["tok"].append(P.toks[j] == tok)
                    s["pos"].append(rows_rel[j] == rel)
                    wj = W[id(rows_item[j][1])]
                    s["jac"].append(len(wi & wj) / max(1, len(wi | wj)))
                for other in rng.sample(fitcaps[f], min(args.k, len(fitcaps[f]))):
                    wj = W[id(other)]
                    s["jac_rand"].append(len(wi & wj) / max(1, len(wi | wj)))
            m = {k: sum(v) / len(v) for k, v in s.items()}
            out[f"L{L}-{f}"] = m
            lines.append(f"| {L} | {f} | {m['fam']:.2f} | {m['tok']:.2f} | {m['pos']:.2f} | {m['jac']:.3f} / {m['jac_rand']:.3f} |")
            print(lines[-1], flush=True)
    d = OUT / "analysis" / "S4" / "extra"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"nn-k{args.k}.json").write_text(json.dumps(out, indent=1))
    (d / f"nn-k{args.k}.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
