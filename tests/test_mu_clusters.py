import torch
from umot.capture import ItemCapture

from jlm import centres
from jlm.mu import clusters


def _items(n=12, d=6, seed=0):
    g = torch.Generator().manual_seed(seed)
    out = []
    for j in range(n):
        base = torch.zeros(d)
        base[j % 3] = 5.0  # three well-separated directions
        out.append(ItemCapture(id=f"i{j}", ids=[0, 1], decoded=["x", f"t{j % 3}"], positions=[-1], idx=[1],
                               acts={5: (base + 0.1 * torch.randn(d, generator=g)).unsqueeze(0)}))
    return out


def _batch(items):
    cells = centres.cell_refs(items, "typo", 5)
    return centres.Batch(5, cells, torch.stack([it.acts[5][0].float() for it in items]), {it.id: it for it in items})


def setup_function():
    clusters._POOLS.clear()
    clusters._FITS.clear()


def test_k1_is_the_family_mean():
    items = _items()
    fam, km1 = centres.make("fam"), centres.make("km1")
    fam.fit(items, "typo")
    km1.fit(items, "typo")
    b = _batch(items)
    assert torch.allclose(centres.apply(km1, b), centres.apply(fam, b), atol=1e-5)


def test_cluster_mean_uses_own_cluster_without_own_item():
    items = _items()
    c = clusters.ClusterMean(3, "fam")
    c.fit(items, "typo")
    b = _batch(items)
    G = b.H - centres.apply(c, b)
    for j in range(len(items)):  # g is the mean of the other members of the same direction
        others = torch.stack([items[i].acts[5][0] for i in range(len(items)) if i % 3 == j % 3 and i != j]).float()
        assert torch.allclose(G[j], others.mean(0), atol=1e-5)


def test_random_control_keeps_cluster_sizes():
    items = _items()
    real, rnd = centres.make("km4"), centres.make("kmr4")
    for c in (real, rnd):
        c.fit(items, "typo")
    _, a, _ = real._layer(5)
    _, r, _ = rnd._layer(5)
    assert sorted(torch.bincount(a).tolist()) == sorted(torch.bincount(r).tolist())
    assert not torch.equal(a, r)


def test_knn_excludes_own_group():
    items = _items()
    c = clusters.NearestMean(1, "bench")
    c.pool = clusters.Pool.of_items(items, "typo")
    b = _batch(items)
    G = b.H - c.transform(b)
    assert not any(torch.allclose(G[j], b.H[j]) for j in range(len(items)))


def test_disjoint_knn_skips_neighbours_sharing_a_rare_word():
    items = _items(n=6)
    items[0].decoded = ["zebra", "t0"]
    items[3].decoded = ["zebra", "t0"]  # item 3 is item 0's nearest (same direction) and shares a rare word
    c = clusters.NearestMean(1, "bench", disjoint=True)
    c.pool = clusters.Pool.of_items(items, "typo")
    b = _batch(items)
    G = b.H - c.transform(b)
    assert not torch.allclose(G[0], b.H[3])
    plain = clusters.NearestMean(1, "bench")
    plain.pool = c.pool
    assert torch.allclose((b.H - plain.transform(b))[0], b.H[3])


def test_direction_centres_scale_and_project():
    items = _items()
    for mode in ("scale", "proj"):
        c = clusters.Direction(1, mode)
        c.inner.pool = c.pool = clusters.Pool.of_items(items, "typo")
        c.inner.key = ("test", mode)
        b = _batch(items)
        G = b.H - c.transform(b)
        if mode == "scale":
            assert torch.allclose(G.norm(dim=1), b.H.norm(dim=1), atol=1e-4)
        else:  # the residual is orthogonal to the removed direction
            R = c.transform(b)
            m = G / G.norm(dim=1, keepdim=True)
            assert torch.allclose((R * m).sum(1), torch.zeros(len(items)), atol=1e-3)


def test_cross_token_knn_skips_same_token_neighbours():
    items = _items(n=6)  # tokens t0, t1, t2 repeat with the directions
    c = clusters.NearestMean(1, "bench", cross_token=True)
    c.pool = clusters.Pool.of_items(items, "typo")
    b = _batch(items)
    G = b.H - c.transform(b)
    for j in range(len(items)):  # the chosen neighbour has another token, i.e. another direction
        nb = min(range(len(items)), key=lambda i: (G[j] - b.H[i]).norm())
        assert items[nb].decoded[1] != items[j].decoded[1]


def test_cluster_pco_with_no_components_is_the_cluster_mean():
    items = _items()
    a, b_ = clusters.ClusterPCO(3, 0), clusters.ClusterMean(3, "fam")
    b_.fit(items, "typo")
    a.pool = b_.pool
    a.key = b_.key
    b = _batch(items)
    assert torch.allclose(a.transform(b), b_.transform(b), atol=1e-4)
