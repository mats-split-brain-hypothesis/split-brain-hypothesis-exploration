"""S20u: one learned constant per layer for every family (card S20u in mu-log; studies/S20.md).

g_l is a single vector fitted with ``ceilings.py``'s surrogate (best accepted id above the 10th competitor, softplus) on
the pooled fit read cells of several families, each family weighted equally. Fits per layer: ``all`` (11 families: the
in-sample ``ceil.u``) and, per family F, ``lofo`` on the other 10 (the centre ``s20u`` reads F with it: other families'
targets only, no family label at read time). Init: the pooled mean of all fit read cells (``s20u0``, untuned).
Writes ``out/priors/S20u/g.pt`` ({layer: {"init", "all", <family>: g}}). Scoring is evaluate.py's.

  python experiments/s20u_fit.py --device cuda
"""

import argparse
import sys
import time
from pathlib import Path

import torch
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ceilings import TOP_K, Problem, candidates

from jlm import OUT, banks, capture
from jlm.lens import Lens
from jlm.mu import clusters

GRID = [20, 24, 28, 32, 36, 40, 42, 44, 48, 52, 56, 60]


def fit(lens: Lens, probs: dict, fams: list[str], L: int, init: torch.Tensor, args) -> torch.Tensor:
    dev = args.device
    Hs, masks, ws, cands = [], [], [], []
    for f in fams:
        p = probs[f]
        rows = torch.arange(len(p.cells))
        cands.append(candidates(p, L, "cos", rows, p.H[L].mean(0), per_cell=32, cap=8192))
    cand = torch.unique(torch.cat(cands))
    pos = {int(t): j for j, t in enumerate(cand.tolist())}
    for f in fams:
        p = probs[f]
        m = torch.zeros(len(p.cells), len(cand), dtype=torch.bool)
        for j in range(len(p.cells)):
            m[j, [pos[t] for t in p.accepted[p.item_of[j]] if t in pos]] = True
        Hs.append(p.H[L])
        masks.append(m)
        ws.append(torch.full((len(p.cells),), 1.0 / len(p.cells)))
    H, M, W8 = torch.cat(Hs).to(dev), torch.cat(masks).to(dev), torch.cat(ws).to(dev)
    keep = M.any(1)
    H, M, W8 = H[keep], M[keep], W8[keep] / W8[keep].sum()
    Wc = lens.w_u[cand.to(lens.w_u.device)].float() @ lens.jac[L]
    Wc = (Wc / lens.denom[L][cand.to(lens.w_u.device), None]).to(dev)
    g = torch.nn.Parameter(init.clone().to(dev))
    opt = torch.optim.Adam([g], lr=args.lr * H.norm(dim=1).mean().item() / H.shape[1] ** 0.5)
    with torch.no_grad():
        tau = args.tau * (H @ Wc.T).std().item()
    for _ in range(args.steps):
        opt.zero_grad()
        S = (H - g) @ Wc.T
        best = S.masked_fill(~M, float("-inf")).max(dim=1).values
        comp = S.masked_fill(M, float("-inf")).topk(TOP_K, dim=1).values[:, -1]
        loss = (F.softplus((comp - best) / tau) * W8).sum() + args.l2 * ((g - init.to(dev)) ** 2).sum() / (H**2).sum(1).mean()
        loss.backward()
        opt.step()
    return g.detach().cpu()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--steps", type=int, default=200)
    ap.add_argument("--lr", type=float, default=0.02)
    ap.add_argument("--tau", type=float, default=0.05)
    ap.add_argument("--l2", type=float, default=1e-3)
    args = ap.parse_args()
    torch.backends.cuda.matmul.allow_tf32 = True
    t0 = time.time()
    lens = Lens(GRID, args.device)
    probs = {}
    for f in clusters.FAMILIES:
        bank = banks.load(f, "fit")
        probs[f] = Problem(lens, bank, capture.load(bank), GRID)
    print(f"problems built ({time.time() - t0:.0f}s)", flush=True)
    out = {"meta": vars(args) | {"note": "lofo: family F's g fitted on the other 10 families' fit targets"}, "layers": {}}
    for L in GRID:
        t = time.time()
        init = torch.cat([probs[f].H[L] for f in clusters.FAMILIES]).mean(0)  # pooled mean of the scored fit cells
        res = {"init": init, "all": fit(lens, probs, clusters.FAMILIES, L, init, args)}
        for f in clusters.FAMILIES:
            res[f] = fit(lens, probs, [g for g in clusters.FAMILIES if g != f], L, init, args)
        out["layers"][L] = res
        d = (res["all"] - init).norm() / init.norm()
        print(f"L{L}: ||g_all - init|| / ||init|| {d:.3f} ({time.time() - t:.0f}s)", flush=True)
    root = OUT / "priors" / "S20u"
    root.mkdir(parents=True, exist_ok=True)
    torch.save(out, root / "g.tmp")
    (root / "g.tmp").rename(root / "g.pt")
    print(f"done ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
