"""M5: shrinkage toward the generic constant inside the finalist (notes/iteration-anthony/mu-log.md, card M5).

S14bL's late step is ``(I - P_B)(h - 0.5 g_K)``, ``g_K`` the mean of h's 8 nearest fit cells (``knnxd8l``): a noisy
K = 8 estimate shrunk halfway toward 0. The James-Stein form shrinks it toward the data-free constant instead:

    h - g = (I - P_B)(h - w g_K - (1 - w) mu_0),   w = K / (K + kappa),

``mu_0`` = ``M1.pool_mean(<pool>, family, layer)`` (glosnone: the plain families' pooled ``glos-none`` captures; the
chat renders their own ``glos-none-<family>``: the render is visible from the prompt). Arm ``m5:<kappa>[:<pool>]``
is the late step only; the finalist form is ``sched:40:kmx64+m5:<kappa>``. ``m5:inf`` is the constant alone under the
projection (w = 0); ``m5:0`` is the full neighbour mean (w = 1).
"""

import torch

from jlm.centres import PARAMETRIC, Batch, CellRef

K = 8


class ShrinkToConstant:
    def __init__(self, kappa: float, pool: str = "glosnone", name: str = "") -> None:
        from jlm.mu import S14

        self.kappa, self.pool = kappa, pool
        self.w = 0.0 if kappa == float("inf") else K / (K + kappa)
        self.inner = S14.make(f"template:64:mean=knnxd8l:a={self.w:g}")
        self.name = name or f"m5:{kappa:g}"
        self.doc = (f"(I - P_B)(h - w g_knn8 - (1 - w) mu_0), w = {self.w:.3f} (kappa {kappa:g}), mu_0 the {pool} "
                    f"constant; B the template subspace (64)")
        self.n_fallback = 0
        self._mu: dict[int, torch.Tensor] = {}

    @property
    def needs_ctx(self) -> bool:
        return self.inner.needs_ctx

    def set_bank(self, family: str, items) -> None:
        self.inner.set_bank(family, items)

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.family = family
        self.inner.fit(ref, family, groups, ctx=ctx)

    def mu(self, layer: int) -> torch.Tensor:
        if layer not in self._mu:
            from jlm.mu import M1

            self._mu[layer] = M1.pool_mean(self.pool, self.family, layer)
        return self._mu[layer]

    def transform(self, batch: Batch) -> torch.Tensor:
        X = self.inner.transform(batch)  # (I - P_B)(h - w g_K)
        if self.w >= 1:
            return X
        B = self.inner.basis(batch.layer)
        m = self.mu(batch.layer)
        return X - (1 - self.w) * (m - (m @ B) @ B.T)

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return self.inner.support(cell)


def make(args: str) -> ShrinkToConstant:
    parts = args.split(":")
    kappa = float(parts[0])
    return ShrinkToConstant(kappa, parts[1] if len(parts) > 1 else "glosnone", name=f"m5:{args}")


PARAMETRIC["m5"] = make
