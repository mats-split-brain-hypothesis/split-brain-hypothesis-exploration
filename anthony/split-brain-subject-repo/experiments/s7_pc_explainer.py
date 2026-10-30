"""Data for the dashboard's "Removing principal components" page (dashboard/views/pca.py; studies/S7.md).

  python experiments/s7_pc_explainer.py [--device mps]

Per family, with pco16 fitted on fit exactly as the val arm is (``_basis(L, "\\0none")``: all fit read cells), at a few
layers: the fit cells' variance spectrum, every val read cell's coordinates on the top 6 PCs (with the labels the page
colours by), the share of its centred norm the top 16 remove, and each of the top 6 PCs (both signs) decoded through the
J-lens (cos readout, scaled to the mean centred norm, as experiments/s7_pcs.py does). On the one-cell families in
SPLIT_FAMILIES, also each val cell read three ways: the centred state x = h - mu (the fam readout), the removed part
V V^T x and the kept part x - V V^T x (the pco16 readout); by linearity L(x) = L(removed) + L(kept). Analysis only; writes
``out/analysis/S7/extra/explainer.json``.
"""

import argparse
import json

import torch

from jlm import OUT, banks, capture, centres
from jlm.centres import cell_refs
from jlm.lens import Lens

FAMILIES = ["typo", "association", "basic_readout", "multihop", "multilingual", "user_modeling", "directed_modulation",
            "typo_mt", "multihop_mt", "basic_readout_mt", "multilingual_mt"]
LAYERS = [36, 44, 48, 56]
N_PC, N_TOK, N_SPEC = 6, 10, 64
SPLIT_FAMILIES = {"typo", "association", "multihop", "multihop_mt", "multilingual_mt"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="mps" if torch.backends.mps.is_available() else "cpu")
    args = ap.parse_args()
    torch.set_grad_enabled(False)
    lens = Lens(LAYERS, args.device)
    res = {}
    for fam in FAMILIES:
        c = centres.make("pco16")
        fit = capture.load(banks.load(fam, "fit"))
        c.fit(fit, fam)
        bank = banks.load(fam, "val")
        items = capture.load(bank)
        meta = bank.by_id()
        by_id = {it.id: it for it in items}
        out = {"layers": {}}
        for L in LAYERS:
            mu, V = c._basis(L, "\0none")
            F = c.X[L].double() - mu.double()
            S = torch.linalg.svdvals(F)
            ev = (S**2 / (S**2).sum())[:N_SPEC]
            cells = cell_refs(items, fam, L)
            X = torch.stack([by_id[x.item].acts[L][x.i].float() for x in cells]) - mu
            Z = X @ V[:, :N_PC]
            R = (X @ V) @ V.T
            share = R.norm(dim=1) ** 2 / X.norm(dim=1) ** 2
            # the fit cells' variance along each pco16 direction (V comes from svd_lowrank, so not exactly S above)
            var = ((F.float() @ V) ** 2).sum(0) / (F**2).sum()
            P = torch.cat([V[:, :N_PC].T, -V[:, :N_PC].T]) * X.norm(dim=1).mean()
            top = lens.scores(P, L, "cos").topk(N_TOK, dim=1).indices
            dec = [lens.display(t.tolist()) for t in top]
            parts = {}
            if fam in SPLIT_FAMILIES:
                for name, Y in (("full", X), ("removed", R), ("kept", X - R)):
                    parts[name] = [lens.display(t.tolist()) for t in lens.scores(Y, L, "cos").topk(N_TOK, dim=1).indices]
            out["layers"][str(L)] = {
                "n_fit": len(F), "ev": [round(float(e), 5) for e in ev], "var16": [round(float(v), 5) for v in var],
                "decoded": {"+": dec[:N_PC], "-": dec[N_PC:]},
                "cells": [{"id": x.item, "pos": x.pos, "token": x.token, "z": [round(float(v), 2) for v in Z[j]],
                           "share": round(float(share[j]), 3), "norm": round(float(X[j].norm()), 1),
                           **({"read": {k: v[j] for k, v in parts.items()}} if parts else {})}
                          for j, x in enumerate(cells)],
            }
        out["items"] = {i: {k: m.get(k) for k in ("subfamily", "lang", "prompt", "target", "intermediates")}
                        for i, m in meta.items() if i in by_id}
        res[fam] = out
        print(fam, {L: round(sum(d["var16"]), 3) for L, d in out["layers"].items()}, flush=True)
    dest = OUT / "analysis" / "S7" / "extra" / "explainer.json"
    dest.write_text(json.dumps(res, ensure_ascii=False))
    print("wrote", dest)


if __name__ == "__main__":
    main()
