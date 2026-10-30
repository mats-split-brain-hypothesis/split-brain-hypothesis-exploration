"""S4 diagnostics: what the clusters are and where read cells land (notes/iteration-anthony/studies/S4.md).

  python experiments/study_S4.py --pool bench --ks 4,8,11,16,32,64,128 --layers 28,44,56
  python experiments/study_S4.py --pool wiki --ks 8,32,128 ...            # needs out/ctx/corpus-wikitext.pt (pod)

Per layer and k: cluster purity of the pool by family and by read token (size-weighted share of the majority label),
how many clusters the val read cells of each family land in (and the share in their top cluster), and the share of
val cells whose cluster's majority family is their own (label recovery). Uses ``jlm.mu.clusters``' own fit, so it
describes exactly the clusters the centres use. No targets.
"""

import argparse
import json
from collections import Counter

import torch

from jlm import OUT, banks, capture
from jlm.mu import clusters


def purity(labels: list[int], keys: list[str]) -> float:
    by = {}
    for c, k in zip(labels, keys, strict=True):
        by.setdefault(c, Counter())[k] += 1
    return sum(cn.most_common(1)[0][1] for cn in by.values()) / len(labels)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default="bench", choices=["bench", "wiki"])
    ap.add_argument("--ks", default="4,8,11,16,32,64,128")
    ap.add_argument("--layers", default="28,44,56")
    ap.add_argument("--split", default="val")
    args = ap.parse_args()
    out = OUT / "analysis" / "S4" / "extra"
    out.mkdir(parents=True, exist_ok=True)
    val = {f: capture.load(banks.load(f, args.split)) for f in clusters.FAMILIES}
    res, lines = {}, [f"# S4 diagnostics: pool {args.pool}, {args.split} cells routed", "",
                      "| L | k | purity fam | purity tok | majority fam = own | clusters hit per family (top share) |",
                      "|---|---|---|---|---|---|"]
    for L in map(int, args.layers.split(",")):
        for k in map(int, args.ks.split(",")):
            c = clusters.ClusterMean(k, args.pool)
            c.fit([], "", None)
            _, labels, _ = c._layer(L)
            lab = labels.tolist()
            maj = {}
            for cl, f in zip(lab, c.pool.fams, strict=True):
                maj.setdefault(cl, Counter())[f] += 1
            maj = {cl: cn.most_common(1)[0][0] for cl, cn in maj.items()}
            hits, own = {}, []
            for f, items in val.items():
                H = torch.cat([it.acts[L].float() for it in items])
                a = c.assign(H, L).tolist()
                cn = Counter(a)
                hits[f] = {"n_clusters": len(cn), "top_share": cn.most_common(1)[0][1] / len(a),
                           "top": [[cl, n, maj.get(cl)] for cl, n in cn.most_common(3)]}
                own += [maj.get(x) == f for x in a]
            r = {"purity_fam": purity(lab, c.pool.fams), "purity_tok": purity(lab, c.pool.toks),
                 "label_recovery": sum(own) / len(own), "hits": hits}
            res[f"L{L}-k{k}"] = r
            short = ", ".join(f"{f[:6]} {h['n_clusters']} ({h['top_share']:.2f})" for f, h in hits.items())
            lines.append(f"| {L} | {k} | {r['purity_fam']:.2f} | {r['purity_tok']:.2f} | {r['label_recovery']:.2f} | {short} |")
            print(lines[-1], flush=True)
    (out / f"diag-{args.pool}.json").write_text(json.dumps(res, indent=1))
    (out / f"diag-{args.pool}.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
