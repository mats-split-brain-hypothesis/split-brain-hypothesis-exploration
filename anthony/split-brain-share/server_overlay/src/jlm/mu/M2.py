"""M2 (round 4, night-3): projective centring, the reference's scale from the cell in the readout metric.

``m2:<mu>[:clip][:state][:rms][:ashuf][:a=<x>]`` reads ``h - alpha(h) mu`` with ``alpha = <h, mu>_A / <mu, mu>_A`` and
``A_l = J^T G J`` the readout gram (``M1.metric``; cos unless ``rms``): the regression coefficient of the cell's readout
on the reference's readout (scores with the constant-score direction removed). ``mu`` is any centre's per-cell g
(``h - apply(inner)``): ``fam``, ``glosnone`` (the data-free constant, ``m1:glosnone:inf``), ``kmx64``, ``knnxs8`` (bank
cells: labelled, comparisons only), or any other centre name. Flags: ``clip`` limits alpha to [0, 1]; ``state`` takes
the plain inner product (S4's kproj-style control); ``ashuf`` gives each cell another cell's alpha (a seeded
derangement, the control for "alpha matched to the cell"); ``a=<x>`` a fixed alpha (S14b's 0.5, fam's 1).

``m2k:<pool>:<k>[:rms]`` removes the A-metric (oblique) projection of ``h - mu_0`` onto the pool's top-k A-principal
directions: M1's readout-metric whitening at lam -> 0 on k axes, the others untouched.
"""

import torch

from jlm import centres
from jlm.centres import PARAMETRIC, Batch, CellRef, _derangement
from jlm.mu import M1

FLAGS = ("clip", "state", "rms", "cos", "ashuf")
ALIASES = {"glosnone": "m1:glosnone:inf", "mwiki": "m1:mwiki:inf", "wshort": "m1:wshort:inf", "mcut": "m1:mcut:inf",
           "nullp": "m1:nullp:inf", "uncond": "m1:uncond:inf"}


def a_inner(X: torch.Tensor, Y: torch.Tensor, layer: int, readout: str) -> torch.Tensor:
    """Row-wise ``<x, y>_A`` for X, Y [n, d] -> [n] fp64."""
    lam, Q = M1.metric(layer, readout)
    Qd = Q.to(X.device, torch.float64)
    return ((X.double() @ Qd) * (Y.double() @ Qd) * lam.to(X.device)).sum(1)


class Projective:
    def __init__(self, inner: str, *, clip: bool = False, state: bool = False, readout: str = "cos",
                 ashuf: bool = False, fixed: float | None = None, name: str | None = None, seed: int = 0) -> None:
        self.inner_name = inner
        self.inner = centres.make(ALIASES.get(inner, inner))
        self.clip, self.state, self.readout, self.ashuf, self.fixed, self.seed = clip, state, readout, ashuf, fixed, seed
        self.name = name or f"m2:{inner}"
        how = (f"fixed alpha {fixed:g}" if fixed is not None else
               f"alpha = <h, mu> / <mu, mu> in the {'state' if state else readout + ' readout'} metric"
               + (" clipped to [0, 1]" if clip else "") + ("; control: alpha from another cell" if ashuf else ""))
        self.doc = f"h - alpha mu, mu = {self.inner.doc}; {how} (M2)"
        self.needs_ctx = getattr(self.inner, "needs_ctx", False)
        self.last_alpha: dict[int, torch.Tensor] = {}

    def set_bank(self, family: str, items) -> None:
        if hasattr(self.inner, "set_bank"):
            self.inner.set_bank(family, items)

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.inner.fit(ref, family, groups, ctx)

    def alpha(self, H: torch.Tensor, G: torch.Tensor, layer: int) -> torch.Tensor:
        if self.fixed is not None:
            return torch.full((len(H),), self.fixed, dtype=torch.float64)
        if self.state:
            a = (H.double() * G.double()).sum(1) / (G.double() * G.double()).sum(1).clamp_min(1e-30)
        else:
            a = a_inner(H, G, layer, self.readout) / a_inner(G, G, layer, self.readout).clamp_min(1e-30)
        if self.clip:
            a = a.clamp(0.0, 1.0)
        if self.ashuf and len(a) > 1:
            a = a[_derangement(len(a), self.seed * 1000 + layer)]
        return a

    def transform(self, batch: Batch) -> torch.Tensor:
        G = batch.H - centres.apply(self.inner, batch)
        a = self.alpha(batch.H, G, batch.layer)
        self.last_alpha[batch.layer] = a.float()
        return (batch.H.double() - a[:, None] * G.double()).float()

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return self.inner.support(cell)


def make(args: str) -> Projective:
    parts = args.split(":")
    flags, fixed = set(), None
    while parts and (parts[-1] in FLAGS or parts[-1].startswith("a=")):
        p = parts.pop()
        if p.startswith("a="):
            fixed = float(p[2:])
        else:
            flags.add(p)
    return Projective(":".join(parts), clip="clip" in flags, state="state" in flags,
                      readout="rms" if "rms" in flags else "cos", ashuf="ashuf" in flags, fixed=fixed, name=f"m2:{args}")


def make_k(args: str) -> M1.GenericWhitening:
    """``m2k:<pool>:<k>[:rms]``: gains -1 on the top-k A-principal directions of the pool, 0 on the rest."""
    parts = args.split(":")
    pool_name, k = parts[0], int(parts[1])
    c = M1.GenericWhitening(pool_name, float("inf"), metric="rms" if "rms" in parts[2:] else "cos", name=f"m2k:{args}")
    c.doc = f"remove the A-oblique projection of h - mu_0 on the top {k} readout-metric principal directions of the {pool_name} pool (M2)"
    base_op = c.op

    def op(layer: int):
        mu, gains, left, right = base_op(layer)
        g = torch.zeros_like(gains)
        g[:k] = -1.0
        return mu, g, left, right

    c.op = op
    return c


PARAMETRIC.update({"m2": make, "m2k": make_k})
