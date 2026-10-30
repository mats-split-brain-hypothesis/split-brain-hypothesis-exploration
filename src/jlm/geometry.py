"""Geometry of the centred states ``h - mu``: how much of ``||h||`` a centre leaves, how ``mu`` sits against
``h``, and the cloud of read vectors in a few principal directions. Needs only the captures (no lens), and
builds ``mu`` with ``jlm.centres`` over the same cells and groups as ``jlm.read``, so the vectors are the ones
the evaluated arm read.
"""

from dataclasses import dataclass

import torch
from umot.capture import ItemCapture

from jlm import banks, capture, centres
from jlm.centres import CellRef


def groups_of(*bs: banks.Bank) -> dict[str, str]:
    """Item -> group, as experiments/evaluate.py builds it (DM twins share their pair id)."""
    return {it["id"]: it.get("pair_id") or it["id"] for b in bs for it in b.items}


@dataclass
class Fitted:
    """One arm's centre fitted on its reference set, ready to give ``mu`` at the read bank's cells."""

    family: str
    items: list[ItemCapture]
    centre: centres.Centre
    groups: dict[str, str]

    @property
    def layers(self) -> list[int]:
        return sorted({L for it in self.items for L in it.acts})

    def layer(self, layer: int) -> tuple[list[CellRef], torch.Tensor, torch.Tensor]:
        """(cells, H [n, d], MU [n, d]) at one layer, float32, in jlm.read's cell order."""
        cells = centres.cell_refs([it for it in self.items if layer in it.acts], self.family, layer, self.groups)
        by_id = {it.id: it for it in self.items}
        H = torch.stack([by_id[c.item].acts[layer][c.i].float() for c in cells])
        MU = H - centres.apply(self.centre, centres.Batch(layer, cells, H, by_id))
        return cells, H, MU


def fit(family: str, split: str, centre: str, ref: str) -> Fitted:
    """The centre of arm ``centre@ref`` on bank ``family/split`` (ref "self": leave-one-group-out on the bank)."""
    bank = banks.load(family, split)
    items = capture.load(bank)
    ref_items, added, _ = capture.load_refs(bank, ref, items)
    groups = groups_of(bank) | added
    c = centres.make(centre)
    if hasattr(c, "set_bank"):  # stratum metadata, as experiments/evaluate.py gives it
        c.set_bank(family, bank.items)
    c.fit(ref_items, family, groups)
    return Fitted(family, items, c, groups)


def cell_stats(f: Fitted) -> list[dict]:
    """One row per (item, layer, read position): ||h||, ||mu||, ||h - mu||, cos(h, mu), and the
    reference cells behind mu (with whether the centre fell back to its fallback)."""
    rows = []
    for layer in f.layers:
        cells, H, MU = f.layer(layer)
        nh, nm, nx = H.norm(dim=1), MU.norm(dim=1), (H - MU).norm(dim=1)
        cos = (H * MU).sum(1) / (nh * nm).clamp_min(1e-12)
        for c, a, b, x, k in zip(cells, nh.tolist(), nm.tolist(), nx.tolist(), cos.tolist(), strict=True):
            n, fell = f.centre.support(c)
            rows.append({"id": c.item, "layer": layer, "pos": c.pos, "token": c.token, "norm_h": a, "norm_mu": b,
                         "norm_x": x, "cos": k if b > 0 else 0.0, "support": n, "fallback": fell})
    return rows


def pca(X: torch.Tensor, k: int = 3, centred: bool = True) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """(basis [k, d], origin [d], share [k]) of the rows of ``X``. ``centred=False`` keeps the origin at 0, so
    a common offset left in the cloud shows as its first direction; share is then of ``sum ||x||^2``."""
    X = X.double()
    origin = X.mean(0) if centred else torch.zeros(X.shape[1], dtype=X.dtype)
    _, S, Vh = torch.linalg.svd(X - origin, full_matrices=False)
    k = min(k, Vh.shape[0])
    return Vh[:k].float(), origin.float(), (S[:k] ** 2 / (S**2).sum()).float()


def project(Y: torch.Tensor, basis: torch.Tensor, origin: torch.Tensor) -> torch.Tensor:
    return (Y.float() - origin) @ basis.T
