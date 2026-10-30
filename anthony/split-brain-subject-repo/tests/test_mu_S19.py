"""S19 learned g: the centre picks the fold model for fit groups and the full model otherwise; the fitter pushes a
cell's token set out of the top 10 on a toy readout. No model, no files outside tmp_path."""

import sys
from argparse import Namespace
from pathlib import Path

import torch

from jlm.centres import Batch, CellRef
from jlm.mu import S19

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
import s19_fit  # noqa: E402


def _cell(item, group, family="typo", layer=5):
    return CellRef(item, group, family, layer, 0, 0, "x", ())


def test_centre_fold_vs_full(tmp_path, monkeypatch):
    monkeypatch.setattr(S19, "ROOT", tmp_path)
    d = 4
    full = {"b": torch.ones(d), "U": None, "V": None}
    fold0 = {"b": 2 * torch.ones(d), "U": torch.eye(d)[:, :1], "V": torch.eye(d)[:, :1]}
    torch.save({"meta": {}, "fold_of": {"typo/g1": 0}, "layers": {5: {"full": full, 0: fold0}}}, tmp_path / "s19x.pt")
    c = S19.Learned("s19x")
    c.fit(None, "typo")
    H = torch.arange(8, dtype=torch.float32).reshape(2, d)
    out = c.transform(Batch(5, [_cell("a", "g1"), _cell("b", "val-item")], H, {}))
    assert torch.allclose(out[1], H[1] - 1)  # unseen group: the full model
    want = H[0] - 2 - torch.tensor([H[0, 0], 0, 0, 0])  # fold model: b plus the rank-1 projection on e0
    assert torch.allclose(out[0], want)


def test_fit_pushes_set_out_of_top10():
    g = torch.Generator().manual_seed(0)
    V, d, n = 60, 8, 64
    W = torch.randn(V, d, generator=g)
    shared = W[3] * 3  # every cell scores token 3 at the top
    H = torch.randn(n, d, generator=g) + shared
    prompt = [[3] for _ in range(n)]
    nxt = [[] for _ in range(n)]
    args = Namespace(rank=0, tied=False, seed=0, lr=0.05, steps=200, batch=32, terms="prompt,next", lam=0.0)
    m = s19_fit.fit_one(W, H, list(range(n)), prompt, nxt, args, tau=0.1, h2=H.square().sum(1).mean().item())
    before = ((H @ W.T).topk(10, dim=1).indices == 3).any(1).float().mean()
    after = (((H - m["b"]) @ W.T).topk(10, dim=1).indices == 3).any(1).float().mean()
    assert before > 0.9 and after < 0.2


def test_ceiling_centre(tmp_path, monkeypatch):
    from jlm.mu import S20

    monkeypatch.setattr(S20, "GDIR", tmp_path)
    d = 3
    torch.save({"layers": {5: {"mu": torch.stack([torch.zeros(d), torch.ones(d)]), "V": None, "tok_key": {"x": 1}}}},
               tmp_path / "typo-tok.pt")
    c = S20.Ceiling("tok")
    c.fit(None, "typo")
    H = torch.ones(2, d)
    cells = [_cell("a", "a"), CellRef("b", "b", "typo", 5, 0, 0, "y", ())]
    out = c.transform(Batch(5, cells, H, {}))
    assert torch.allclose(out[0], torch.zeros(d)) and torch.allclose(out[1], torch.ones(d))


def test_tied_fit_is_a_projection():
    g = torch.Generator().manual_seed(1)
    V, d, n = 40, 6, 32
    W = torch.randn(V, d, generator=g)
    H = torch.randn(n, d, generator=g)
    args = Namespace(rank=2, tied=True, seed=0, lr=0.05, steps=20, batch=16, terms="prompt,next", lam=0.0)
    m = s19_fit.fit_one(W, H, list(range(n)), [[1]] * n, [[]] * n, args, tau=0.1, h2=1.0)
    Q = m["U"]
    assert torch.allclose(Q.T @ Q, torch.eye(2), atol=1e-5) and m["U"] is m["V"]


def test_readfreq_centre(tmp_path, monkeypatch):
    from umot.capture import ItemCapture

    from jlm.mu import S20

    monkeypatch.setattr(S20, "OUT", tmp_path)
    (tmp_path / "priors" / "S20b").mkdir(parents=True)
    d = 3
    torch.save({"layers": {5: {"typo": torch.ones(d), "all": 2 * torch.ones(d)}}}, tmp_path / "priors" / "S20b" / "readfreq-k50.pt")
    items = [ItemCapture(f"i{j}", [1], ["x"], [0], [0], {5: torch.full((1, d), float(j))}) for j in range(3)]
    c = S20.ReadFreq(50, 0.5)
    c.fit(items, "typo")
    mu = c(CellRef("i0", "i0", "typo", 5, 0, 0, "x", ("x",)))
    assert torch.allclose(mu, torch.full((d,), 1.5 + 0.5))  # fam of the other two items (1, 2) + 0.5 x prior
    c.fit(items, "other_family")
    assert torch.allclose(c.g[5], 2 * torch.ones(d))  # unknown family: the pooled prior


def test_universal_centre(tmp_path, monkeypatch):
    from jlm.mu import S20

    monkeypatch.setattr(S20, "OUT", tmp_path)
    (tmp_path / "priors" / "S20u").mkdir(parents=True)
    d = 2
    torch.save({"layers": {5: {"init": torch.zeros(d), "all": torch.ones(d), "typo": 3 * torch.ones(d)}}},
               tmp_path / "priors" / "S20u" / "g.pt")
    c = S20.Universal("lofo")
    c.fit(None, "typo")
    assert torch.allclose(c(_cell("a", "a")), 3 * torch.ones(d))
    c.fit(None, "unknown")
    assert torch.allclose(c.g[5], torch.ones(d))


def test_famrand_keeps_norm_of_change():
    from umot.capture import ItemCapture

    from jlm.centres import Batch as B, CellRef as C, FamilyMean
    from jlm.mu import S20

    d = 4
    items = [ItemCapture(f"i{j}", [1], ["x"], [0], [0], {5: torch.full((1, d), float(j))}) for j in range(3)]
    c = S20.FamRand(0, "zero")  # inner = zero: change from fam = -fam, so ||g - fam|| = ||fam||
    c.fit(items, "typo")
    cells = [C("i0", "i0", "typo", 5, 0, 0, "x", ("x",))]
    H = items[0].acts[5].float()
    out = c.transform(B(5, cells, H, {it.id: it for it in items}))
    fam = FamilyMean(); fam.fit(items, "typo")
    g = H - out
    assert torch.allclose((g[0] - fam(cells[0])).norm(), fam(cells[0]).norm(), atol=1e-5)
