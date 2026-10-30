"""S15 mu from J's own geometry: remove h's component in the top-k right singular subspace of ``J_l`` (the input
directions the lens amplifies most) (notes/iteration-anthony/mu-log.md, card S15).

The SVDs are cached by ``experiments/precompute_pullback.py --jsvd`` (``out/lens/jsvd-<pin>-L.pt``); the diagnostic
half of the card (where fam, tok and h sit in J's spectrum) is ``experiments/s15_spectrum.py``.

- ``s15top<k>``: ``g = V_k V_k^T h`` (no reference cells).
- ``s15famtop<k>``: ``g = mu_fam + V_k V_k^T (h - mu_fam)``.
- ``s15r<k>``: control, a random k-dim subspace alone (``pcr<k>`` from S7 is the fam + random control).
"""

import torch

from jlm import pullback
from jlm.centres import CENTRES, Batch, CellRef, FamilyMean

OWNER = "Anthony"
CANDIDATES = ()


class JSubspace:
    def __init__(self, k: int, with_fam: bool = False, random: bool = False, seed: int = 0, name: str | None = None) -> None:
        self.k, self.with_fam, self.random, self.seed = k, with_fam, random, seed
        self.name = name or f"s15{'fam' if with_fam else ''}{'r' if random else 'top'}{k}"
        what = f"a random {k}-dim subspace" if random else f"J's top {k} right singular directions"
        self.doc = ("family mean plus " if with_fam else "") + f"h's component in {what} removed"
        self.n_fallback = 0
        self.key = pullback.default_key()

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.fam = None
        if self.with_fam:
            self.fam = FamilyMean()
            self.fam.fit(ref, family, groups)
        self.d = next(iter(ref[0].acts.values())).shape[1]
        self._basis: dict[int, torch.Tensor] = {}

    def basis(self, layer: int) -> torch.Tensor:
        if layer not in self._basis:
            if self.random:
                g = torch.Generator().manual_seed(self.seed * 1000 + layer)
                self._basis[layer] = torch.linalg.qr(torch.randn(self.d, self.k, generator=g))[0]
            else:
                _, Vh = pullback.load_jsvd(self.key, layer)
                self._basis[layer] = Vh[: self.k].T.float().contiguous()
        return self._basis[layer]

    def transform(self, batch: Batch) -> torch.Tensor:
        B = self.basis(batch.layer)
        X = batch.H if self.fam is None else batch.H - torch.stack([self.fam(c) for c in batch.cells])
        return X - (X @ B) @ B.T

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return self.fam.support(cell) if self.fam is not None else (0, False)


for _k in (8, 32, 128):
    CENTRES[f"s15top{_k}"] = lambda k=_k: JSubspace(k)
    CENTRES[f"s15famtop{_k}"] = lambda k=_k: JSubspace(k, with_fam=True)
    CENTRES[f"s15r{_k}"] = lambda k=_k: JSubspace(k, random=True)
