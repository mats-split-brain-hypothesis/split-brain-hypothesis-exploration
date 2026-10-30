"""S18 sparse centres on toy captures: the top-k and complement parts add up to fam, k = d is fam, the random control
uses k coordinates, the wikitext variants read the corpus mean."""

import torch
from umot.capture import ItemCapture

from jlm import centres
from jlm.mu import S18


def _items(n=6, d=6, layers=(5, 9), seed=0):
    g = torch.Generator().manual_seed(seed)
    return [ItemCapture(id=f"i{j}", ids=[0, 1], decoded=["x", "t"], positions=[-1], idx=[1],
                        acts={L: torch.randn(1, d, generator=g) + torch.tensor([5.0, 0, 0, -3.0, 0, 0]) for L in layers})
            for j in range(n)]


def _batch(items, L):
    cells = centres.cell_refs(items, "typo", L)
    return centres.Batch(L, cells, torch.stack([it.acts[L][0].float() for it in items]), {it.id: it for it in items})


def test_top_and_complement_add_up_to_fam():
    items = _items()
    fam = centres.make("fam")
    fam.fit(items, "typo")
    top, comp = S18.Sparse(2, "top"), S18.Sparse(2, "comp")
    top.fit(items, "typo")
    comp.fit(items, "typo")
    b = _batch(items, 5)
    g_fam = b.H - centres.apply(fam, b)
    g_top, g_comp = b.H - centres.apply(top, b), b.H - centres.apply(comp, b)
    assert torch.allclose(g_top + g_comp, g_fam, atol=1e-5)
    assert set(top.mask[5].nonzero().flatten().tolist()) == {0, 3}  # the outlier coordinates
    full = S18.Sparse(6, "top")
    full.fit(items, "typo")
    assert torch.allclose(centres.apply(full, b), centres.apply(fam, b), atol=1e-5)


def test_random_and_wiki_variants(monkeypatch):
    items = _items()
    r = S18.Sparse(3, "rand")
    r.fit(items, "typo")
    assert int(r.mask[9].sum()) == 3
    monkeypatch.setattr(S18, "_WIKI", {5: torch.arange(6.0), 9: -torch.arange(6.0)})
    w, ww = S18.Sparse(2, "wiki"), S18.Sparse(2, "wikiown")
    w.fit(items, "typo")
    ww.fit(items, "typo")
    cell = centres.cell_refs(items, "typo", 9)[0]
    assert torch.allclose(w(cell), torch.tensor([0.0, 0, 0, -3, 0, 0]))
    assert torch.allclose(ww(cell), torch.tensor([0.0, 0, 0, 0, -4, -5]))
    assert centres.make("s18ww32").name == "s18ww32"


def test_wiki_complement_and_full(monkeypatch):
    items = _items()
    monkeypatch.setattr(S18, "_WIKI", {5: torch.tensor([9.0, 1, 2, -8, 3, 0]), 9: torch.zeros(6)})
    wc, wf = S18.Sparse(2, "wikicomp"), centres.make("s18wfull")
    wc.fit(items, "typo")
    wf.fit(items, "typo")
    cell = centres.cell_refs(items, "typo", 5)[0]
    assert torch.allclose(wc(cell), torch.tensor([0.0, 1, 2, 0, 3, 0]))
    assert torch.allclose(wf(cell), torch.tensor([9.0, 1, 2, -8, 3, 0])) and wf.name == "s18wfull"


def test_chat_variants(monkeypatch):
    items = _items()
    monkeypatch.setattr(S18, "_CHAT", {5: torch.tensor([0.0, 7, 1, 0, -6, 2]), 9: torch.zeros(6)})
    c = centres.make("s18cc8")
    c.k = 2
    c.fit(items, "typo")
    cell = centres.cell_refs(items, "typo", 5)[0]
    assert torch.allclose(c(cell), torch.tensor([0.0, 0, 1, 0, 0, 2]))
    assert centres.make("s18cfull").name == "s18cfull"
