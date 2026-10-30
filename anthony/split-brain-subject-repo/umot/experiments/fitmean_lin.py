"""Linearisation diagnostic per centre: how well does μ_63 + J_l (h − μ_l) predict the final residual?

The J-lens as a first-order expansion about a centre μ: f_l(h) ≈ μ_63 + J_l (h − μ_l), with μ_63 the
same centre's mean of the final (block-63, pre-norm) residual. For each centre of ``token_local``
(``fam``, ``tok``, ``carpos``) and the J-lens fit mean ``fit`` (μ_fit,l and μ_fit,63 from
``experiments/fit_mean.py``), at every captured cell of a family with a final side capture:

    err_c  = ‖h_63 − μ_63,c − J_l (h − μ_l,c)‖      the affine prediction's error
    base_c = ‖h_63 − μ_63,c‖                         the centre alone (J term dropped)

Reported per layer: Σerr²/Σbase² (the fraction of the deviation from the centre J leaves unexplained;
the taylor screen's ``rel_err_taylor`` is its per-cell, unsquared version for ``fam``) and Σerr² /
Σ‖h_63 − μ_63,fam‖² (a common denominator, so centres compare on one scale). References: the
uncentred J_l h (expansion about 0), and the ridge OLS slope fitted on wikitext (``ols_beta.pt``)
about μ_fit. No unembedding is loaded.

  .venv/bin/python experiments/fitmean_lin.py --family directed_modulation
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "experiments"))
from token_local import build_centres, load_jacobians  # noqa: E402
from umot import capture  # noqa: E402
from umot.provenance import PINS, Provenance, write_artefact  # noqa: E402

FINAL = 63
CENTRES = ("fam", "tok", "carpos", "fit")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--family", default="directed_modulation")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "out" / "fitmean")
    args = ap.parse_args()
    items = capture.load(REPO_ROOT / "out" / "captures" / f"{args.family}.pt")
    fin = {it.id: it for it in capture.load(REPO_ROOT / "out" / "captures" / f"{args.family}-final.pt")}
    for it in items:
        assert fin[it.id].idx == it.idx, f"{it.id}: side capture cells differ"
        it.acts[FINAL] = fin[it.id].acts[FINAL]
    centres = build_centres(items, args.family)
    assert "fit" in centres, "out/fitmean/mu.pt missing"
    beta = torch.load(args.out / "ols_beta.pt", map_location="cpu")["beta"]
    layers = sorted({L for it in items for L in it.acts} - {FINAL})
    jac = load_jacobians(layers)

    # Per centre, the stacked (h_63 − μ_63,c) over every cell, and the cell order.
    cells = [(it, i) for it in items for i in range(len(it.positions))]
    y = torch.stack([it.acts[FINAL][i].float() for it, i in cells]).double()
    mu63 = {c: torch.stack([centres[c](it, FINAL, i) for it, i in cells]).double() for c in CENTRES}
    ref = ((y - mu63["fam"]) ** 2).sum()
    rows = []
    for L in layers:
        J = jac[L].double()
        h = torch.stack([it.acts[L][i].float() for it, i in cells]).double()
        row = {"layer": L, "n_cells": len(cells)}
        for c in CENTRES:
            mu = torch.stack([centres[c](it, L, i) for it, i in cells]).double()
            dev = y - mu63[c]
            err = dev - (h - mu) @ J.T
            row[f"unexpl_{c}"] = float((err**2).sum() / (dev**2).sum())
            row[f"err_vs_fam_{c}"] = float((err**2).sum() / ref)
            row[f"base_vs_fam_{c}"] = float((dev**2).sum() / ref)
            if c == "fit":
                errb = dev - (h - mu) @ beta[L].double().T
                row["unexpl_fit_ols"] = float((errb**2).sum() / (dev**2).sum())
                row["err_vs_fam_fit_ols"] = float((errb**2).sum() / ref)
        row["err_vs_fam_plain"] = float(((y - h @ J.T) ** 2).sum() / ref)
        rows.append(row)
        print(f"L{L:2d}  J leaves unexplained (of each centre's own deviation): "
              + "  ".join(f"{c} {row[f'unexpl_{c}']:.3f}" for c in CENTRES)
              + f"  fit+OLS {row['unexpl_fit_ols']:.3f}"
              + "  | error / fam deviation: "
              + "  ".join(f"{c} {row[f'err_vs_fam_{c}']:.3f}" for c in CENTRES)
              + f"  fit+OLS {row['err_vs_fam_fit_ols']:.3f}  plain J h {row['err_vs_fam_plain']:.3f}", flush=True)
    prov = Provenance(model="Qwen/Qwen3.6-27B", model_revision=PINS["Qwen/Qwen3.6-27B"], reader="neuronpedia/jacobian-lens",
                      reader_revision=PINS["neuronpedia/jacobian-lens"], dataset=f"wsbench/{args.family} (+ -final side capture)",
                      seed=0, extra={"centres": CENTRES, "fit_mean": "out/fitmean/mu.pt", "ols": "out/fitmean/ols_beta.pt"})
    write_artefact(args.out / f"lin-{args.family}.json", prov, {"rows": rows})


if __name__ == "__main__":
    main()
