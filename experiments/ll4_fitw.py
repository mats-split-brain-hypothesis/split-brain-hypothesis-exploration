"""Programme LL, phase 4 (H5): fit J++-style signed expert weights on our fit banks, with and without anchors.

    python experiments/ll4_fitw.py --router w8 --anchors 0,own,fam,knn --device cuda

Per layer, the map is ``J_w = sum_e w_e J_e`` (w signed, unit L2), read as ``J_w (h - g)`` or, for the paired anchor
``own``, ``sum_e w_e J_e (h - mu_e)`` (an affine map: ``J_w h - b``, ``b = sum_e w_e J_e mu_e``). The fit follows
J++'s ``condense_experts`` (rank_objective.py): with the rms readout, ``logits(x) * rms(x) = W_U diag(g) x`` is linear
in x, so per cell and expert ``L_pe = W_U diag(g) T_pe`` is cached once and ``L_p(w) = sum_e w_e L_pe`` ranks exactly
as the rms readout of the weighted map. Objective: the macro over families of the soft pass
``sigmoid((best target logit - 10th logit) / (tau * spread))``; Adam, several starts (count-proportional weights =
the pooled map, uniform, each single expert), the iterate with the best exact macro pass kept.
Fit cells: the fit split of the families with one read cell per item (UM and DM have many cells per item and are
guardrails: excluded from the objective, still scored). Scored on fit and **val** (fit chooses, val confirms), with
both readouts, item rule over the layers; the pooled map (w proportional to counts) and n1000 are the references.
Writes ``out/analysis/LL4/<router>/{weights.pt,scores.json}``.
"""

import argparse
import json
import zlib
import sys
import time
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).parent))
from ll2_screen import EXPERTS, FAMILIES, Bank, log  # noqa: E402

from jlm import OUT  # noqa: E402
from jlm.lens import RMS_EPS, Lens  # noqa: E402

LAYERS = [24, 32, 40, 48, 56]
MULTI_CELL = {"user_modeling", "directed_modulation"}


def read_top10(lens: Lens, Z: torch.Tensor, J: torch.Tensor, readout: str, rows: int = 512) -> torch.Tensor:
    """[n, 10] top ids of transported states Z = J x - b (already transported) under ``readout``."""
    den = None
    if readout == "cos":
        den = torch.cat([(lens.w_u[i : i + 32768] @ J).norm(dim=1) for i in range(0, lens.vocab, 32768)]).clamp_min(1e-9)
    out = []
    for a in range(0, len(Z), rows):
        z = Z[a : a + rows].to(lens.device, torch.float32)
        if readout == "cos":
            s = (z @ lens.w_u.T) / den
        else:
            s = (lens.gain * z / torch.sqrt(z.square().mean(1, keepdim=True) + RMS_EPS)) @ lens.w_u.T
        out.append(s.topk(10, dim=1).indices.cpu())
    return torch.cat(out)


def fit_layer(L_pev: torch.Tensor, cand: list[torch.Tensor], fam_of: torch.Tensor, n_fam: int, starts: list[torch.Tensor],
              steps: int = 200, lr: float = 0.05, tau: float = 0.1) -> tuple[torch.Tensor, float]:
    """Signed unit-L2 weights maximising the macro soft pass; returns (w, exact macro pass on the fit cells)."""
    P = L_pev.shape[0]
    C = max(len(c) for c in cand)
    cid = torch.stack([torch.cat([c, c[:1].repeat(C - len(c))]) for c in cand]).to(L_pev.device)

    def margins(w):
        Lw = torch.einsum("pev,e->pv", L_pev, w)
        best = Lw.gather(1, cid).max(1).values
        tenth = Lw.topk(11, dim=1).values[:, -1]  # the 11th: best >= 10th largest is not enough under ties
        # (a degenerate all-equal readout would pass); best > 11th largest is the strict top-10 rule
        spread = Lw.std(1).detach()
        return best - tenth, spread

    def macro(x):  # mean over families of the mean over their cells
        s = torch.zeros(n_fam, device=x.device).index_add_(0, fam_of, x)
        n = torch.zeros(n_fam, device=x.device).index_add_(0, fam_of, torch.ones_like(x))
        return (s / n.clamp_min(1)).mean()

    best_w, best_v = None, -1.0
    for w0 in starts:
        w = (w0 / w0.norm()).clone().to(L_pev.device).requires_grad_(True)
        opt = torch.optim.Adam([w], lr=lr)
        for step in range(steps + 1):
            wn = w / w.norm()
            m, spread = margins(wn)
            if step % 5 == 0 or step == steps:
                with torch.no_grad():
                    v = float(macro((m > 0).float()))
                if v > best_v:
                    best_v, best_w = v, wn.detach().clone()
            if step == steps:
                break
            loss = -macro(torch.sigmoid(m / (tau * spread)))
            opt.zero_grad()
            loss.backward()
            opt.step()
    return best_w, best_v


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--router", default="w8")
    ap.add_argument("--anchors", default="0,own,fam,knn")
    ap.add_argument("--experts", default=str(EXPERTS))
    ap.add_argument("--steps", type=int, default=200)
    ap.add_argument("--fit-half", choices=["", "A", "B"], default="",
                    help="stability check: fit the weights on one seeded half of the fit items only")
    ap.add_argument("--device", default="cuda")
    a = ap.parse_args()
    root = OUT / "analysis" / "LL4" / (a.router + (f"-half{a.fit_half}" if a.fit_half else ""))
    root.mkdir(parents=True, exist_ok=True)
    lens = Lens(LAYERS, a.device)
    vocab = lens.display(list(range(lens.vocab)))
    ex = {L: torch.load(Path(a.experts) / f"experts-L{L:03d}.pt", weights_only=False) for L in LAYERS}
    fams = FAMILIES
    banks = {(f, s): Bank(f, s, lens, vocab) for f in fams for s in ("fit", "val")}
    log("banks loaded")
    fit_fams = [f for f in fams if f not in MULTI_CELL]
    weights, scores = {}, {}
    for an in a.anchors.split(","):
        for L in LAYERS:
            E = ex[L][a.router]
            keep = E["count"] >= 200  # starved experts left out (degenerate fits)
            J = E["J"][keep].to(a.device, torch.float32)  # [k, d, d]
            mu, cnt = E["mu"][keep].to(a.device), E["count"][keep].float()
            k = J.shape[0]
            rows, cand, fam_of = [], [], []
            for fi, f in enumerate(fit_fams):
                b = banks[(f, "fit")]
                if L not in b.H:
                    continue
                acc = b.accepted
                for j, c in enumerate(b.cells[L]):
                    ids = acc.get(c.item, [])
                    if c.item not in b.idset or not ids:
                        continue
                    if a.fit_half and (zlib.crc32(c.item.encode()) % 2 == 0) != (a.fit_half == "A"):
                        continue
                    h = b.H[L][j].to(a.device)
                    g = {"0": 0, "fam": b.g["fam"][L][j].to(a.device), "knn": b.g["knn"][L][j].to(a.device)}.get(an)
                    X = (h - mu) if an == "own" else (h - g)[None].expand(k, -1)  # [k, d]
                    rows.append(torch.einsum("eij,ej->ei", J, X))  # T_pe
                    cand.append(torch.tensor(ids))
                    fam_of.append(fi)
            T = torch.stack(rows)  # [P, k, d]
            Lpev = torch.stack([(lens.gain * T[:, e]) @ lens.w_u.T for e in range(k)], 1)  # [P, k, V]
            starts = [cnt.clone(), torch.ones(k)] + [torch.eye(k)[e] for e in range(k)]
            w, v = fit_layer(Lpev, cand, torch.tensor(fam_of, device=a.device), len(fit_fams), starts, steps=a.steps)
            pooled_v = fit_layer(Lpev, cand, torch.tensor(fam_of, device=a.device), len(fit_fams), [cnt.clone()], steps=0)[1]
            weights[(an, L)] = w.cpu()
            log(f"{an} L{L}: fit macro per-layer pass {v:.3f} (pooled {pooled_v:.3f}); w = {[round(x, 3) for x in w.tolist()]}")
            del Lpev, T
            torch.cuda.empty_cache()
        # score: item rule over the layers, both readouts, fit and val, every family
        for split in (("val",) if a.fit_half else ("fit", "val")):
            for ro in ("cos", "rms"):
                for wname in ("fitted", "pooled"):
                    res = {}
                    for f in fams:
                        b = banks[(f, split)]
                        tops = {}
                        for L in b.layers:
                            E = ex[L][a.router]
                            keep = E["count"] >= 200
                            J = E["J"][keep].to(a.device, torch.float32)
                            mu = E["mu"][keep].to(a.device)
                            c = E["count"][keep].float().to(a.device)
                            w = weights[(an, L)].to(a.device) if wname == "fitted" else c / c.sum()
                            Jw = torch.einsum("e,eij->ij", w, J)
                            H = b.H[L].to(a.device)
                            if an == "own":
                                Z = H @ Jw.T - torch.einsum("e,ei->i", w, torch.einsum("eij,ej->ei", J, mu))
                            else:
                                g = 0 if an == "0" else b.g[an][L].to(a.device)
                                Z = (H - g) @ Jw.T
                            tops[L] = read_top10(lens, Z, Jw, ro)
                        p = b.passes(lens, tops)
                        res[f] = {"rate": b.rate(p), "items": {i: p[i] for i in b.ids}}
                    scores[f"{an}|{wname}|{split}|{ro}"] = res
                    log(an, wname, split, ro, {f: round(r["rate"], 3) for f, r in res.items()})
        torch.save({f"{k[0]}|L{k[1]}": v for k, v in weights.items()}, root / "weights.pt")
        (root / "scores.json").write_text(json.dumps(scores))
    log("LL4_DONE")


if __name__ == "__main__":
    main()
