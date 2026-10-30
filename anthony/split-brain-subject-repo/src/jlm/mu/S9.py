"""S9 cross-layer g: the state at an earlier layer of the same cell (notes/iteration-anthony/studies/S6.md).

The residual stream is one basis at every depth, so ``h_l - h_{l-k}`` is what blocks l-k+1..l wrote at the cell:
read only the layers' update, not what was already there. Variants:

- ``xl<k>``: g = h_{l-k} (the cell's own state k layers earlier).
- ``xlf<k>``: g = h_{l-k} + mu_l - mu_{l-k} (mu the family mean, own group excluded): the update minus the family's
  mean update, i.e. ``(h_l - mu_l) - (h_{l-k} - mu_{l-k})``.
- ``xlp<k>``: g = the projection of h_l on h_{l-k} (removes the earlier state's direction, at h_l's own scale).
- ``xlr``: control, g = h at a random earlier captured layer (seeded per layer): is it this depth's update or any
  earlier state?

The read-cell captures hold the grid layers (20, 24, ..., 60) and 42. When l-k is not captured (l = 20; l = 24 for
k = 8) g falls back to 0 (the uncentred readout) at that layer; the fallback count is ``n_fallback``.
"""

import torch

from jlm.centres import CENTRES, Batch, FamilyMean

OWNER = "Anthony"  # dashboard pickers list these centres under "Anthony's centres" (catalog.owner)


def _earlier(batch: Batch, src: int) -> torch.Tensor | None:
    """[n, d] float32, the cells' states at layer ``src``, or None when any item lacks it."""
    out = []
    for c in batch.cells:
        acts = batch.items[c.item].acts
        if src not in acts:
            return None
        out.append(acts[src][c.i].float())
    return torch.stack(out)


class CrossLayer:
    def __init__(self, k: int, mode: str = "plain") -> None:
        self.k, self.mode = k, mode
        tag = {"plain": "xl", "fam": "xlf", "proj": "xlp"}[mode]
        self.name = f"{tag}{k}"
        self.doc = {
            "plain": f"the cell's own state {k} layers earlier (read the update only)",
            "fam": f"the cell's state {k} layers earlier plus the family's mean update (own group excluded)",
            "proj": f"the projection of h on the cell's own state {k} layers earlier",
        }[mode]
        self.n_fallback = 0

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.n_fallback = 0
        if self.mode == "fam":
            self.fam = FamilyMean()
            self.fam.fit(ref, family, groups)

    def transform(self, batch: Batch) -> torch.Tensor:
        E = _earlier(batch, batch.layer - self.k)
        if E is None:
            self.n_fallback += len(batch.cells)
            return batch.H.clone()
        if self.mode == "plain":
            G = E
        elif self.mode == "fam":
            from dataclasses import replace

            dmu = torch.stack([self.fam(c) - self.fam(replace(c, layer=batch.layer - self.k)) for c in batch.cells])
            G = E + dmu
        else:
            u = E / E.norm(dim=1, keepdim=True).clamp_min(1e-6)
            G = (batch.H * u).sum(1, keepdim=True) * u
        return batch.H - G

    def support(self, cell) -> tuple[int, bool]:
        return 1, False


class RandomEarlier:
    """Control: g = the cell's state at a random captured layer below l (seeded per layer)."""

    name, doc = "xlr", "control: the cell's own state at a random earlier captured layer"

    def __init__(self, seed: int = 0) -> None:
        self.seed, self.n_fallback = seed, 0

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.n_fallback = 0

    def transform(self, batch: Batch) -> torch.Tensor:
        have = sorted(set.intersection(*(set(batch.items[c.item].acts) for c in batch.cells)))
        below = [L for L in have if L < batch.layer]
        if not below:
            self.n_fallback += len(batch.cells)
            return batch.H.clone()
        g = torch.Generator().manual_seed(self.seed * 1000 + batch.layer)
        src = below[int(torch.randint(len(below), (1,), generator=g))]
        return batch.H - _earlier(batch, src)

    def support(self, cell) -> tuple[int, bool]:
        return 1, False


for _k in (4, 8):
    CENTRES[f"xl{_k}"] = lambda k=_k: CrossLayer(k)
    CENTRES[f"xlf{_k}"] = lambda k=_k: CrossLayer(k, "fam")
    CENTRES[f"xlp{_k}"] = lambda k=_k: CrossLayer(k, "proj")
CENTRES["xlr"] = RandomEarlier
