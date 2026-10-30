"""M15 (night-3 B; diagnostic): what the data-free constant lacks (notes/iteration-anthony/mu-log.md, card M15).

``d = mu_ref - mu_0`` per family and layer, mu_0 the generic glosnone constant (``M1.pool_mean``), mu_ref the family
mean (``fam``: per cell, own group left out) or S20's target-fitted constant (``ceil``: in-sample, labelled ceiling).
``P_r d`` = d's top-r components in the eigenbasis of the cos readout gram ``A_l`` ranked by readout energy
``lam_i (q_i . d)^2`` (the subspace taken from the family's full d). Arm ``m15:<ref>:<r>`` reads M4h's transform (alias
``gcp``) minus ``P_r d`` (``r = all``: minus d). Uses family means and, for ``ceil``, fit targets: a diagnostic, read with
``evaluate.py --out out/analysis/M15/eval`` only.
"""

import torch

from jlm import OUT, centres
from jlm.centres import PARAMETRIC, Batch, CellRef, FamilyMean, apply


def energy_basis(d: torch.Tensor, layer: int, r: int) -> torch.Tensor:
    """[d, r] the eigenvectors of A_l carrying the most of ``d``'s readout energy."""
    from jlm.mu import M1

    lam, Q = M1.metric(layer, "cos")
    c = lam.float() * (d.float() @ Q).square()
    return Q[:, c.topk(r).indices]


class AddBack:
    def __init__(self, ref: str, r: str) -> None:
        self.ref, self.r = ref, r
        self.name = f"m15:{ref}:{r}"
        self.doc = f"M4h (gcp) minus the top-{r} readout components of d = {ref} - mu_0 (diagnostic; uses {ref})"
        self.n_fallback = 0

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.family = family
        self.base = centres.make("gcp")
        self.base.fit(ref, family, groups)
        self.fam = None
        if self.ref == "fam":
            self.fam = FamilyMean()
            self.fam.fit(ref, family, groups)
            self._ref_items, self._groups = ref, groups
        else:
            obj = torch.load(OUT / "analysis" / "S20" / "g" / f"{family}-const.pt", weights_only=False)
            self._ceil = {int(L): v["mu"].reshape(-1).float() for L, v in obj["layers"].items()}
        self._mu0, self._Q = {}, {}

    def mu0(self, layer: int) -> torch.Tensor:
        if layer not in self._mu0:
            from jlm.mu import M1

            self._mu0[layer] = M1.pool_mean("glosnone", self.family, layer)
        return self._mu0[layer]

    def full_d(self, layer: int) -> torch.Tensor:
        if self.ref == "ceil":
            return self._ceil[layer] - self.mu0(layer)
        rows = [it.acts[layer].float() for it in self._ref_items if layer in it.acts]
        return torch.cat(rows).mean(0) - self.mu0(layer)

    def basis(self, layer: int) -> torch.Tensor | None:
        if self.r == "all":
            return None
        if layer not in self._Q:
            self._Q[layer] = energy_basis(self.full_d(layer), layer, int(self.r))
        return self._Q[layer]

    def transform(self, batch: Batch) -> torch.Tensor:
        X = apply(self.base, batch)
        L = batch.layer
        if self.fam is not None:
            D = torch.stack([self.fam(c) for c in batch.cells]) - self.mu0(L)
        else:
            D = (self._ceil[L] - self.mu0(L)).expand_as(X)
        Q = self.basis(L)
        return X - (D if Q is None else (D @ Q) @ Q.T)

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return 0, False


def make(args: str) -> AddBack:
    ref, r = args.split(":")
    return AddBack(ref, r)


PARAMETRIC["m15"] = make
