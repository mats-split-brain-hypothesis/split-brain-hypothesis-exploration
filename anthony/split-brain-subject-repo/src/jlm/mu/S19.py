"""S19 learned g with the controls as the loss (notes/iteration-anthony/mu-log.md, card S19; studies/S19.md).

Per layer ``g(h) = U V^T h + b`` (rank r; r = 0 is a learned constant ``b``), fitted by ``experiments/s19_fit.py`` on the
pooled fit read cells of every family to push out of the readout's top 10 (i) the cell's own prompt-content tokens and
(ii) the model's own next-token top 10 at the cell, plus ``lambda ||g||^2``. No targets anywhere in the loss.

The fitter writes ``out/priors/S19/<name>.pt``: per layer one model fitted on every fit group (``full``) and one per
fold of a K-fold split by group; ``fold_of`` maps each fit group to its fold. A cell whose group is in ``fold_of`` (a
fit item read on fit, ``@self``) is read with the model that never saw its group; any other cell (val, bench) with the
full model. The reference bank passed to ``fit`` is ignored: the fit pool is the training set.

Arms (each a file of the same name): ``s19b`` (rank 0), ``s19r4``, ``s19r16``; controls ``s19r16sh`` (prompt sets
shuffled across items), ``s19r16p`` / ``s19r16n`` (prompt term only / next-token term only). Any ``s19<tag>`` with a
file under ``out/priors/S19`` resolves through ``s19:<tag>``.
"""

from pathlib import Path

import torch

from jlm import OUT
from jlm.centres import CENTRES, PARAMETRIC, Batch

OWNER = "Anthony"
CANDIDATES = ()
ROOT = OUT / "priors" / "S19"


def path_of(name: str) -> Path:
    return ROOT / f"{name}.pt"


class Learned:
    """``h - g = h - b - U (V^T h)``, the fold model for fit groups, the full model otherwise."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.doc = f"learned g = U V^T h + b ({name}; experiments/s19_fit.py): no targets, prompt + next-token loss"
        self.n_fallback = 0

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        obj = torch.load(path_of(self.name), map_location="cpu")
        self.meta, self.fold_of = obj["meta"], obj["fold_of"]
        self.models = {int(L): m for L, m in obj["layers"].items()}

    def _model(self, layer: int, group: str, family: str):
        ms = self.models[layer]
        k = self.fold_of.get(f"{family}/{group}")
        return ms["full"] if k is None else ms[k]

    def transform(self, batch: Batch) -> torch.Tensor:
        if batch.layer not in self.models:
            raise KeyError(f"{self.name}: no model at layer {batch.layer} (have {sorted(self.models)})")
        out = torch.empty_like(batch.H)
        keys = [self._model(batch.layer, c.group, c.family) for c in batch.cells]
        for m in {id(k): k for k in keys}.values():
            rows = torch.tensor([j for j, k in enumerate(keys) if k is m])
            H = batch.H[rows]
            g = m["b"].float().expand_as(H)
            if m.get("U") is not None:
                g = g + (H @ m["V"].float()) @ m["U"].float().T
            out[rows] = H - g
        return out

    def support(self, cell) -> tuple[int, bool]:
        return 0, False


def make(tag: str) -> Learned:
    return Learned(f"s19{tag}")


PARAMETRIC["s19"] = make
for _n in ("s19b", "s19r4", "s19r16", "s19r16sh", "s19r16p", "s19r16n", "s19bsh"):
    CENTRES[_n] = lambda _n=_n: Learned(_n)
