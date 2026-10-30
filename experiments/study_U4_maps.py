"""U4 cuts 2-3: the difference map D_l = J++_l - J_l, and how centres look through both maps (studies/U4.md).

  python experiments/study_U4_maps.py --device cuda          # pod: both lenses at the grid layers + W_U

Per grid layer:
- D's size and spectrum: ||D||_F / ||J||_F, ||D||_2 / ||J||_2, energy share of D's top 1 / 8 / 64 singular directions;
  the top 3 left singular directions of D decoded through W_U (top / bottom tokens), and the cosine of each family's
  mean with D's top 8 right singular directions (summed squared: the share of mu inside D's top-8 input subspace,
  against 8 / d for a random direction).
- Per family (val read cells; mu = the family's fit mean, the `fam@fit` centre): the relative disagreement of the maps
  on h, on mu and on h - mu: ||D x|| / ||J x||, and cos(D h, D mu).
- The control for U4 insight 5 (centring both maps doubles their top-10 agreement): mean top-10 overlap of
  J-lens and J++ readouts (cos) at each cell for x = h, h - mu, h - mu_other (another family's fit mean, rotated),
  h - r (a random direction with ||mu||). If h - mu_other or h - r also agrees much more than h, the agreement is a
  generic effect of removing a big shared component, not of the family mean.
Analysis only; no centre is built here.
"""

import argparse
import json

import torch

from jlm import OUT, banks, capture
from jlm.lens import Lens
from jlm.mu.clusters import FAMILIES


def top_tokens(lens: Lens, v: torch.Tensor, n: int = 8) -> dict:
    s = lens.w_u @ v
    tok = lens.tokenizer.convert_ids_to_tokens
    return {"top": tok(s.topk(n).indices.tolist()), "bottom": tok((-s).topk(n).indices.tolist())}


def overlap(J: Lens, P: Lens, X: torch.Tensor, L: int, chunk: int = 128) -> float:
    """Mean top-10 overlap of the two maps' cos readouts of X, scored in chunks (the GPU is shared)."""
    hits = []
    for i in range(0, len(X), chunk):
        ta = J.scores(X[i : i + chunk], L, "cos").topk(10, dim=1).indices
        tb = P.scores(X[i : i + chunk], L, "cos").topk(10, dim=1).indices
        hits.append((ta.unsqueeze(2) == tb.unsqueeze(1)).any(2).float().sum(1))
    return float(torch.cat(hits).mean() / 10)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--split", default="val")
    args = ap.parse_args()
    caps = {f: (capture.load(banks.load(f, "fit")), capture.load(banks.load(f, args.split))) for f in FAMILIES}
    layers = sorted(set.intersection(*(set(c[1][0].acts) for c in caps.values())))
    J = Lens(layers, args.device, "jlens")
    layers = [L for L in layers if L in J.layers]
    P = Lens(layers, args.device, "jpp", share=J)
    gen = torch.Generator().manual_seed(0)
    res, lines = {}, ["# U4 cuts 2-3: the difference map D = J++ - J", ""]
    for L in layers:
        Jl, Pl = J.jac[L], P.jac[L]
        D = Pl - Jl
        U, S, Vh = torch.linalg.svd(D)
        sJ = torch.linalg.matrix_norm(Jl, 2)
        e = S.square().cumsum(0) / S.square().sum()
        mus = {f: torch.cat([it.acts[L].float() for it in c[0]]).mean(0).to(args.device) for f, c in caps.items()}
        row = {"D_over_J_fro": float(D.norm() / Jl.norm()), "D_over_J_spec": float(S[0] / sJ),
               "energy_top": {k: float(e[k - 1]) for k in (1, 8, 64)},
               "left_decoded": [top_tokens(J, U[:, i]) for i in range(3)], "fam": {}}
        fams = list(caps)
        for fi, f in enumerate(fams):
            H = torch.cat([it.acts[L].float() for it in caps[f][1]]).to(args.device)
            mu, other = mus[f], mus[fams[(fi + 1) % len(fams)]]
            r = torch.randn(mu.shape, generator=gen).to(args.device)
            r = r / r.norm() * mu.norm()
            rel = lambda X: float(((X @ D.T).norm(dim=-1) / (X @ Jl.T).norm(dim=-1)).mean())
            Dh, Dmu = H @ D.T, D @ mu
            ov = {}
            for name, X in (("h", H), ("h-mu", H - mu), ("h-mu_other", H - other), ("h-rand", H - r)):
                ov[name] = overlap(J, P, X, L)
            row["fam"][f] = {
                "rel_h": rel(H), "rel_mu": rel(mu[None]), "rel_centred": rel(H - mu),
                "cos_Dh_Dmu": float(torch.nn.functional.cosine_similarity(Dh, Dmu[None]).mean()),
                "mu_in_D_top8": float(((Vh[:8] @ mu) / mu.norm()).square().sum()),
                "overlap": ov}
        res[L] = row
        print(f"L{L}: ||D||/||J|| fro {row['D_over_J_fro']:.2f} spec {row['D_over_J_spec']:.2f}; energy top1/8/64 "
              f"{row['energy_top'][1]:.2f}/{row['energy_top'][8]:.2f}/{row['energy_top'][64]:.2f}", flush=True)
    out = OUT / "analysis" / "U4" / "extra"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"maps-{args.split}.json").write_text(json.dumps(res, indent=1))
    lines += ["| L | D/J fro | D/J spec | energy top1 / 8 / 64 | D top-1 left direction (top tokens) |", "|---|---|---|---|---|"]
    for L, r in res.items():
        lines.append(f"| {L} | {r['D_over_J_fro']:.2f} | {r['D_over_J_spec']:.2f} | {r['energy_top'][1]:.2f} / "
                     f"{r['energy_top'][8]:.2f} / {r['energy_top'][64]:.2f} | {' '.join(r['left_decoded'][0]['top'][:6])} |")
    lines += ["", "Per family, mean over layers: ||Dx||/||Jx|| for x = h, mu, h - mu; cos(Dh, Dmu); share of mu in D's "
              "top-8 input subspace (random: 8/d = 0.0016); top-10 J vs J++ overlap for h, h-mu, h-mu_other, h-rand.", "",
              "| family | rel h | rel mu | rel h-mu | cos(Dh,Dmu) | mu in D top8 | ovl h | h-mu | h-mu_other | h-rand |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for f in FAMILIES:
        m = lambda k: sum(r["fam"][f][k] for r in res.values()) / len(res)
        o = lambda k: sum(r["fam"][f]["overlap"][k] for r in res.values()) / len(res)
        lines.append(f"| {f} | {m('rel_h'):.2f} | {m('rel_mu'):.2f} | {m('rel_centred'):.2f} | {m('cos_Dh_Dmu'):.2f} | "
                     f"{m('mu_in_D_top8'):.3f} | {o('h'):.2f} | {o('h-mu'):.2f} | {o('h-mu_other'):.2f} | {o('h-rand'):.2f} |")
    (out / f"maps-{args.split}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
