"""S22: the item-free fill pool's nearest-cell mean and pool mean."""

import torch

from jlm import centres
from jlm.centres import Batch, CellRef
from jlm.mu import S22


def test_s22_nearest_and_pool_mean(monkeypatch):
    X = torch.tensor([[1.0, 0.0], [0.9, 0.1], [0.0, 1.0], [0.1, 0.9]])
    monkeypatch.setattr(S22, "_POOL", {5: X})
    c = S22.NeutralNearest(2)
    c.fit([], "typo")
    H = torch.tensor([[2.0, 0.1], [0.1, 3.0]])
    cells = [CellRef("a", "a", "typo", 5, 0, 0, "x", ()), CellRef("b", "b", "typo", 5, 0, 0, "y", ())]
    b = Batch(5, cells, H, {})
    out = c.transform(b)
    assert torch.allclose(out[0], H[0] - X[:2].mean(0))
    assert torch.allclose(out[1], H[1] - X[2:].mean(0))
    pm = centres.make("s22pm")
    pm.fit([], "typo")
    assert torch.allclose(pm.transform(b), H - X.mean(0))
