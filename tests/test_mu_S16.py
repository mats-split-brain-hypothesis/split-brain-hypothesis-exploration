"""S16 form-blind kNN on a toy pool: with the full space it is knnx, neighbours exclude the own group, and the form
subspace changes which neighbours are picked."""

import torch
from umot.capture import ItemCapture

from jlm import centres
from jlm.mu import S16, clusters


def _setup(monkeypatch, n=12, d=8):
    g = torch.Generator().manual_seed(0)
    items = [ItemCapture(id=f"i{j}", ids=[0, 1], decoded=["x", f"t{j}"], positions=[-1], idx=[1],
                         acts={5: torch.randn(1, d, generator=g)}) for j in range(n)]
    pool = clusters.Pool.of_items(items, "typo")
    monkeypatch.setitem(clusters._POOLS, ("bench",), pool)
    monkeypatch.setattr(S16, "_SPACES", {})
    cells = centres.cell_refs(items, "typo", 5)
    batch = centres.Batch(5, cells, torch.cat([it.acts[5] for it in items]).float(), {it.id: it for it in items})
    return items, batch


def test_full_space_is_knnx_and_own_group_is_excluded(monkeypatch):
    items, batch = _setup(monkeypatch)
    knn = centres.make("knnx4")
    knn.fit(items, "typo")
    form = S16.FormNearest(4, "pc", dim=8)  # all 8 directions: the projection is a rotation, cosines unchanged
    form.fit(items, "typo")
    nb = form._neighbours(batch)
    assert torch.equal(nb.sort(1).values, knn._neighbours(batch).sort(1).values)
    assert all(j not in nb[j].tolist() for j in range(len(items)))
    assert torch.allclose(centres.apply(form, batch), centres.apply(knn, batch), atol=1e-5)


def test_form_subspace_changes_the_neighbours(monkeypatch):
    items, batch = _setup(monkeypatch)
    a, b = S16.FormNearest(4, "pc", dim=2), S16.FormNearest(4, "rand", dim=2)
    a.fit(items, "typo")
    b.fit(items, "typo")
    assert not torch.equal(a._neighbours(batch).sort(1).values, b._neighbours(batch).sort(1).values)
    assert centres.make("s16pcd8").name == "s16pcd8" and centres.make("s16tb8").name == "s16tb8"


def test_outlier_free_distance(monkeypatch):
    items, batch = _setup(monkeypatch)
    knn = centres.make("knnx4")
    knn.fit(items, "typo")
    xo0 = S16.FormNearest(4, "full")  # no coordinate dropped: knnx exactly
    xo0.fit(items, "typo")
    assert torch.equal(xo0._neighbours(batch).sort(1).values, knn._neighbours(batch).sort(1).values)
    xo = S16.FormNearest(4, "full", drop_outliers=2)
    xo.fit(items, "typo")
    assert int(xo.keep(5).sum()) == 6 and xo.name == "s16xo4"
    assert centres.make("s16xopc8").name == "s16xopc8"


def test_other_carrier_excludes_same_tail(monkeypatch):
    items, batch = _setup(monkeypatch)
    c = S16.OtherCarrier(4)
    c.pool = clusters._POOLS[("bench",)]
    # every pool row but row 3 shares the cells' tail -> only row 3 can be picked (besides nothing), for cell 0
    c.pool.carriers = [(None, ("x", "zz"))] * len(items)
    c.pool.carriers[3] = (None, ("other",))
    c.k = 1
    monkeypatch.setattr(S16, "_carrier_of", lambda f, i: None)
    batch.items[items[0].id].decoded[:] = ["x", "zz"]
    nb = c._neighbours(centres.Batch(5, batch.cells[:1], batch.H[:1], batch.items))
    assert nb.tolist() == [[3]]


def test_with_ref_pool_adds_the_reference_cells(monkeypatch):
    items, batch = _setup(monkeypatch)
    monkeypatch.setattr(S16, "_bench_carriers", lambda p: [(None, ("b",))] * len(p.groups))
    monkeypatch.setattr(S16, "_carrier_of", lambda f, i: "same" if i in ("i0", "i5") else None)
    c = centres.make("knnxsm8")
    c.fit(items[:6], "typo", {it.id: it.id for it in items})
    assert len(c.pool.groups) == len(items) + 6 and len(c.pool.carriers) == len(items) + 6
    c.k = 3
    nb = c._neighbours(centres.Batch(5, batch.cells[:1], batch.H[:1], batch.items))  # cell i0: carrier "same"
    rows = nb[0].tolist()
    assert all(c.pool.groups[r] != "i0" for r in rows)
    assert not any(c.pool.carriers[r][0] == "same" for r in rows)
