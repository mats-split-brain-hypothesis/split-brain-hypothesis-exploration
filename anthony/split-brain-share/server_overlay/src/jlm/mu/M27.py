"""M27 (night-3 B): h-dependence from generic cells only (notes/iteration-anthony/mu-log.md, card M27).

``g_K(h)`` = the mean of the K nearest (cosine) generic cells to h at the layer, over every generic pool pooled (A's
``M1.pool``: glosnone, mwiki, wshort, mcut, nullp, uncond; the chat renders get their own files only), duplicates
removed. Aliases (names without ':', for S14's ``mean=``): ``gknn<K>`` (K in 8, 32, 128), ``gknnsoft`` (softmax of cosine /
0.05 over the top 128), ``gknnr<K>`` (K random generic cells per cell: the control). The arm is
``s14:chatpunct:128:mean=gknn<K>:a=1`` = (I - P_C128)(h - g_K(h)), the M23 default's form with the kNN mean as the base.
"""

import torch

from jlm.centres import CENTRES, Batch, CellRef

POOLS = ("glosnone", "mwiki", "wshort", "mcut", "nullp", "uncond")
_ROWS: dict = {}


def generic_rows(family: str, layer: int) -> torch.Tensor:
    from jlm.mu import M1

    key = (M1.render(family), layer)
    if key not in _ROWS:
        X = torch.cat([M1.pool(p, family, layer) for p in POOLS]).float()
        _ROWS[key] = torch.unique(X, dim=0)
    return _ROWS[key]


class GenericKNN:
    def __init__(self, k: int, soft: bool = False, rand: bool = False, tau: float = 0.05) -> None:
        self.k, self.soft, self.rand, self.tau = k, soft, rand, tau
        self.name = f"gknn{'soft' if soft else ('r' if rand else '')}{k}"
        self.doc = (f"mean of {k} {'random' if rand else 'nearest (cosine)'} generic cells (all generic pools)"
                    + (f", softmax weights at tau {tau}" if soft else ""))
        self.n_fallback = 0

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.family = family

    def transform(self, batch: Batch) -> torch.Tensor:
        P = generic_rows(self.family, batch.layer)
        k = min(self.k, len(P))
        if self.rand:
            g = torch.Generator().manual_seed(batch.layer)
            idx = torch.stack([torch.randperm(len(P), generator=g)[:k] for _ in range(len(batch.H))])
            return batch.H - P[idx].mean(1)
        sim = torch.nn.functional.normalize(batch.H.float(), dim=1) @ torch.nn.functional.normalize(P, dim=1).T
        v, idx = sim.topk(k, dim=1)
        if self.soft:
            w = torch.softmax(v / self.tau, dim=1)
            return batch.H - (w[:, :, None] * P[idx]).sum(1)
        return batch.H - P[idx].mean(1)

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return self.k, False


for _k in (8, 32, 128):
    CENTRES[f"gknn{_k}"] = lambda k=_k: GenericKNN(k)
    CENTRES[f"gknnr{_k}"] = lambda k=_k: GenericKNN(k, rand=True)
CENTRES["gknnsoft"] = lambda: GenericKNN(128, soft=True)
