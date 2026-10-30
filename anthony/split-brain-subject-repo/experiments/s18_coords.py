"""S18 diagnostic: is the family mean a few outlier coordinates or a dense vector?

Per family (fit bank) and grid layer: the share of ||mu_fam||^2 in its top-k coordinates by |value| (k = 8, 32, 128),
the same share for a typical read state h, the overlap of fam's top-32 coordinates across families and with the
wikitext mean (corpus8), and the cosine of the restricted means. Light (read-cell captures only); writes
out/analysis/S18/coords.{json,md}.
"""

import json

import torch

from jlm import OUT, banks, capture
from jlm.mu.clusters import FAMILIES

KS = (8, 32, 128, 512)


def topk_share(v: torch.Tensor, k: int) -> float:
    s = (v.double() ** 2)
    return float(s.topk(k).values.sum() / s.sum())


def main() -> None:
    wiki = capture.load_ref("corpus8")
    layers = sorted(next(iter(capture.load(banks.load("typo", "fit")))).acts)
    wmu = {L: torch.cat([it.acts[L].float() for it in wiki if L in it.acts]).mean(0) for L in layers}
    res, top = {}, {}
    for f in FAMILIES:
        items = capture.load(banks.load(f, "fit"))
        for L in layers:
            H = torch.cat([it.acts[L].float() for it in items])
            mu = H.mean(0)
            r = {f"mu_k{k}": topk_share(mu, k) for k in KS}
            r.update({f"h_k{k}": float(sum(topk_share(h, k) for h in H[:200]) / min(200, len(H))) for k in KS})
            r["norm_mu_over_h"] = float(mu.norm() / H.norm(dim=1).mean())
            t32 = set(mu.abs().topk(32).indices.tolist())
            top[(f, L)] = t32
            w32 = set(wmu[L].abs().topk(32).indices.tolist())
            r["overlap32_wiki"] = len(t32 & w32) / 32
            idx = mu.abs().topk(32).indices
            r["cos32_fam_wiki"] = float(torch.nn.functional.cosine_similarity(mu[idx], wmu[L][idx], dim=0))
            r["ratio32_wiki_over_fam"] = float(wmu[L][idx].norm() / mu[idx].norm())
            r["cos_full_fam_wiki"] = float(torch.nn.functional.cosine_similarity(mu, wmu[L], dim=0))
            res[f"{f}/L{L}"] = r
    for L in layers:  # cross-family overlap of the top-32 coordinates
        sets = [top[(f, L)] for f in FAMILIES]
        inter = set.intersection(*sets)
        res[f"all/L{L}"] = {"top32_in_every_family": len(inter), "coords": sorted(inter),
                            "wiki_top32": sorted(wmu[L].abs().topk(32).indices.tolist())[:32]}
    out = OUT / "analysis" / "S18"
    out.mkdir(parents=True, exist_ok=True)
    (out / "coords.json").write_text(json.dumps(res, indent=1))
    lines = ["| family | L | mu k8 | k32 | k128 | k512 | h k8 | h k32 | h k128 | ov32 wiki | cos32 fam/wiki | |w|/|fam| on 32 | cos full |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for key, r in res.items():
        if key.startswith("all/"):
            continue
        f, L = key.split("/")
        lines.append(f"| {f} | {L[1:]} | " + " | ".join(f"{r[c]:.2f}" for c in
                     ["mu_k8", "mu_k32", "mu_k128", "mu_k512", "h_k8", "h_k32", "h_k128", "overlap32_wiki",
                      "cos32_fam_wiki", "ratio32_wiki_over_fam", "cos_full_fam_wiki"]) + " |")
    lines.append("")
    for L in layers:
        lines.append(f"L{L}: top-32 coordinates shared by every family: {res[f'all/L{L}']['top32_in_every_family']}")
    (out / "coords.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
