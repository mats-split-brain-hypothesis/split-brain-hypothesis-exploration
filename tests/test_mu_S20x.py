"""S20x transfer centre on toy captures: fam plus alpha times the stored correction; the random control keeps its norm."""

import torch
from umot.capture import ItemCapture

from jlm import centres
from jlm.mu import S20x


def test_transfer_adds_scaled_dbar(monkeypatch):
    g = torch.Generator().manual_seed(0)
    items = [ItemCapture(id=f"i{j}", ids=[0, 1], decoded=["x", "t"], positions=[-1], idx=[1],
                         acts={5: torch.randn(1, 4, generator=g)}) for j in range(5)]
    d = torch.tensor([1.0, -2.0, 0.0, 3.0])
    monkeypatch.setattr(S20x, "_DBAR", {"typo": {5: d}})
    fam = centres.make("fam")
    fam.fit(items, "typo")
    c, r = centres.make("s20x:2"), centres.make("s20xr:2")
    c.fit(items, "typo")
    r.fit(items, "typo")
    cell = centres.cell_refs(items, "typo", 5)[0]
    assert torch.allclose(c(cell), fam(cell) + 2 * d)
    assert torch.isclose((r(cell) - fam(cell)).norm(), 2 * d.norm())
    assert c.name == "s20x:2" and r.name == "s20xr:2"


def test_on_top_adds_the_correction_to_any_centre(monkeypatch):
    g = torch.Generator().manual_seed(1)
    items = [ItemCapture(id=f"i{j}", ids=[0, 1], decoded=["x", "t"], positions=[-1], idx=[1],
                         acts={5: torch.randn(1, 4, generator=g)}) for j in range(4)]
    d = torch.tensor([1.0, 0.0, -1.0, 2.0])
    monkeypatch.setattr(S20x, "_DBAR", {"typo|twin": {5: d}})
    on, fam = centres.make("s20xon:2:fam"), centres.make("fam")
    on.fit(items, "typo")
    fam.fit(items, "typo")
    cells = centres.cell_refs(items, "typo", 5)
    b = centres.Batch(5, cells, torch.cat([it.acts[5] for it in items]).float(), {it.id: it for it in items})
    assert torch.allclose(centres.apply(on, b), centres.apply(fam, b) - 2 * d)
    assert centres.make("sched:40:s20xt:1+s20xon:1:fam").name == "sched:40:s20xt:1+s20xon:1:fam"


def test_single_source_skips_own_family_and_twin(monkeypatch):
    g = torch.Generator().manual_seed(2)
    items = [ItemCapture(id=f"i{j}", ids=[0, 1], decoded=["x", "t"], positions=[-1], idx=[1],
                         acts={5: torch.randn(1, 4, generator=g)}) for j in range(4)]
    d = torch.tensor([1.0, 1.0, 0.0, 0.0])
    monkeypatch.setattr(S20x, "_DBAR", {"d": {"association": {5: d}, "typo_mt": {5: d}}})
    fam = centres.make("fam")
    fam.fit(items, "typo")
    cell = centres.cell_refs(items, "typo", 5)[0]
    a, t = centres.make("s20x1:association:1"), centres.make("s20x1:typo_mt:1")
    a.fit(items, "typo")
    t.fit(items, "typo")
    assert torch.allclose(a(cell), fam(cell) + d)
    assert torch.allclose(t(cell), fam(cell))  # the twin's correction is never used


def test_rms_table_is_separate(monkeypatch):
    g = torch.Generator().manual_seed(3)
    items = [ItemCapture(id=f"i{j}", ids=[0, 1], decoded=["x", "t"], positions=[-1], idx=[1],
                         acts={5: torch.randn(1, 4, generator=g)}) for j in range(3)]
    monkeypatch.setattr(S20x, "_DBAR", {"typo|twin": {5: torch.ones(4)}})
    monkeypatch.setattr(S20x, "_DBAR_RMS", {"typo|twin": {5: 2 * torch.ones(4)}})
    fam, c, o = centres.make("fam"), centres.make("s20xtrms:1"), centres.make("s20xonrms:1:fam")
    for x in (fam, c, o):
        x.fit(items, "typo")
    cell = centres.cell_refs(items, "typo", 5)[0]
    assert torch.allclose(c(cell), fam(cell) + 2) and c.name == "s20xtrms:1"
    assert o.name == "s20xonrms:1:fam"


def test_k_sources_average(monkeypatch):
    g = torch.Generator().manual_seed(4)
    items = [ItemCapture(id=f"i{j}", ids=[0, 1], decoded=["x", "t"], positions=[-1], idx=[1],
                         acts={5: torch.randn(1, 2, generator=g)}) for j in range(3)]
    d = {"a": {5: torch.tensor([1.0, 0])}, "b": {5: torch.tensor([0.0, 1])}, "typo_mt": {5: torch.tensor([9.0, 9])},
         "typo": {5: torch.tensor([7.0, 7])}}
    monkeypatch.setattr(S20x, "_DBAR", {"d": d, "typo|twin": {5: torch.zeros(2)}})
    fam = centres.make("fam")
    fam.fit(items, "typo")
    c2, c1 = centres.make("s20xk:9:0:1"), centres.make("s20xk:1:0:1")
    c2.fit(items, "typo")
    c1.fit(items, "typo")
    cell = centres.cell_refs(items, "typo", 5)[0]
    assert c2.drawn() == ["a", "b"]  # own family and twin never drawn; k above the pool takes all
    assert torch.allclose(c2(cell), fam(cell) + torch.tensor([0.5, 0.5]))
    assert len(c1.drawn()) == 1 and c1.drawn()[0] in ("a", "b")
