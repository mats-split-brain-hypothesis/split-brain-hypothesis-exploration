"""Centres of instance C's studies (S9 cross-layer, S7 subspace removal)."""

import torch
from umot.capture import ItemCapture

from jlm import centres


def cap(iid: str, acts: dict[int, list[list[float]]]) -> ItemCapture:
    n = len(next(iter(acts.values())))
    return ItemCapture(id=iid, ids=[0, 1], decoded=["x", " y"], positions=list(range(-n, 0)),
                       idx=list(range(2 - n, 2)), acts={L: torch.tensor(v) for L, v in acts.items()})


ITEMS = [
    cap("a", {20: [[1.0, 0.0, 0.0]], 24: [[2.0, 1.0, 0.0]], 28: [[2.0, 1.0, 5.0]]}),
    cap("b", {20: [[0.0, 1.0, 0.0]], 24: [[0.0, 3.0, 1.0]], 28: [[1.0, 3.0, 1.0]]}),
    cap("c", {20: [[0.0, 0.0, 2.0]], 24: [[1.0, 0.0, 2.0]], 28: [[0.0, 4.0, 2.0]]}),
]


def batch(layer: int) -> centres.Batch:
    cells = centres.cell_refs(ITEMS, "multihop", layer)
    H = torch.stack([it.acts[layer][0] for it in ITEMS])
    return centres.Batch(layer, cells, H, {it.id: it for it in ITEMS})


def test_cross_layer_reads_the_update_and_falls_back_to_zero():
    c = centres.make("xl4")
    c.fit(ITEMS, "multihop")
    b = batch(24)
    assert torch.allclose(centres.apply(c, b), b.H - torch.stack([it.acts[20][0] for it in ITEMS]))
    b20 = batch(20)
    assert torch.equal(centres.apply(c, b20), b20.H) and c.n_fallback == 3


def test_cross_layer_fam_removes_the_mean_update_of_other_items():
    c = centres.make("xlf4")
    c.fit(ITEMS, "multihop")
    X = centres.apply(c, batch(28))
    # item a: (h28 - mu28) - (h24 - mu24), means over b and c
    mu28, mu24 = (ITEMS[1].acts[28][0] + ITEMS[2].acts[28][0]) / 2, (ITEMS[1].acts[24][0] + ITEMS[2].acts[24][0]) / 2
    want = (ITEMS[0].acts[28][0] - mu28) - (ITEMS[0].acts[24][0] - mu24)
    assert torch.allclose(X[0], want)


def test_cross_layer_projection_is_orthogonal_to_the_earlier_state():
    c = centres.make("xlp4")
    c.fit(ITEMS, "multihop")
    X = centres.apply(c, batch(28))
    E = torch.stack([it.acts[24][0] for it in ITEMS])
    assert torch.allclose((X * E).sum(1), torch.zeros(3), atol=1e-5)


def test_random_earlier_layer_uses_one_captured_layer_below():
    c = centres.make("xlr")
    c.fit(ITEMS, "multihop")
    b = batch(28)
    G = b.H - centres.apply(c, b)
    assert any(torch.allclose(G, torch.stack([it.acts[L][0] for it in ITEMS])) for L in (20, 24))


def test_pc_removal_excludes_own_group_and_removes_the_top_direction():
    c = centres.make("pco4")  # k above the rank of 2 other cells: everything but the mean's span is kept
    c.fit(ITEMS, "multihop")
    X = centres.apply(c, batch(20))
    others = torch.stack([ITEMS[1].acts[20][0], ITEMS[2].acts[20][0]])
    mu = others.mean(0)
    d = (others[0] - mu) / (others[0] - mu).norm()  # the only direction of variation among b, c
    x = ITEMS[0].acts[20][0] - mu
    assert torch.allclose(X[0], x - d * (d @ x), atol=1e-5)


def test_random_subspace_control_keeps_the_mean_and_dimension():
    c = centres.make("pcr4")
    c.fit(ITEMS, "multihop")
    mu, V = c._basis(20, "a")
    assert V.shape == (3, 3)  # k = 4 > d = 3: the whole space
    assert torch.allclose(mu, (ITEMS[1].acts[20][0] + ITEMS[2].acts[20][0]) / 2)


def test_mean_direction_and_scaled_mean():
    p = centres.make("pmu")
    p.fit(ITEMS, "multihop")
    X = centres.apply(p, batch(20))
    u = (ITEMS[1].acts[20][0] + ITEMS[2].acts[20][0]) / 2
    assert abs(float(X[0] @ u)) < 1e-5
    h = centres.make("fam50")
    h.fit(ITEMS, "multihop")
    assert torch.allclose(h(centres.cell_refs(ITEMS, "multihop", 20)[0]), 0.5 * u)


def test_token_pc_removal_uses_the_token_mean_and_the_family_pcs():
    t = centres.make("tpco4")
    t.fit(ITEMS, "multihop")
    p = centres.make("pco4")
    p.fit(ITEMS, "multihop")
    b = batch(20)
    tok = t.tok(b.cells[0])  # fewer than 3 same-token cells: the family mean, so tpco = pco here
    assert torch.allclose(tok, p._basis(20, "a")[0])
    assert torch.allclose(centres.apply(t, b), centres.apply(p, b), atol=1e-5)


def test_source_and_other_family_means(monkeypatch):
    import jlm.mu.S6 as s6

    other = [cap("p", {20: [[4.0, 0.0, 0.0]]}), cap("q", {20: [[0.0, 0.0, 4.0]]})]

    def fake(family, groups=None):
        m = centres.FamilyMean()
        m.fit(other if family != "typo" else ITEMS, family, groups)
        return m

    monkeypatch.setattr(s6, "_fit_mean", fake)
    c = centres.make("mhfam")
    c.fit(ITEMS, "multihop_mt")
    cell = centres.cell_refs(ITEMS, "multihop_mt", 20)[0]
    assert torch.allclose(c(cell), torch.tensor([2.0, 0.0, 2.0]))  # the source's whole mean: no shared group
    o = centres.make("othfam")
    o.fit(ITEMS, "multihop")
    assert len(o.means) == 10 and torch.allclose(o(cell), (9 * torch.tensor([2.0, 0.0, 2.0]) + ITEMS[0].acts[20][0] / 3
                                                           + ITEMS[1].acts[20][0] / 3 + ITEMS[2].acts[20][0] / 3) / 10)


def test_lag_predictor_recovers_a_linear_map(tmp_path, monkeypatch):
    import jlm.mu.S3 as s3
    from jlm.context import CtxItem

    torch.manual_seed(0)
    d, n = 3, 400
    A = torch.tensor([[0.5, 0.0, 0.0], [0.0, -1.0, 0.0], [0.2, 0.0, 0.3]])
    X = torch.randn(n, d, dtype=torch.float64)
    Y = 1.0 + X @ A.double()
    Xc, Yc = X - X.mean(0), Y - Y.mean(0)
    torch.save({"n": n, "mx": X.mean(0).float(), "my": Y.mean(0).float(), "C": (Xc.T @ Xc).float(),
                "B": (Xc.T @ Yc).float()}, tmp_path / "arstats-wikitext-L020.pt")
    monkeypatch.setattr(s3, "STATS", tmp_path)
    s3._SOLVED.clear()

    class Ctx:
        items = {"a": CtxItem("a", [0, 1], ["x", " y"], [1], {20: torch.tensor([[1.0, 2.0, 3.0], [0.0, 0.0, 0.0]])})}

        def states(self, item, layer):
            return self.items[item].acts[layer]

    c = centres.make("ar1e2")
    c.fit([], "multihop")
    cells = centres.cell_refs([ITEMS[0]], "multihop", 20)
    b = centres.Batch(20, cells, torch.zeros(1, 3), {"a": ITEMS[0]}, Ctx())
    g = -centres.apply(c, b)[0]
    assert torch.allclose(g, 1.0 + torch.tensor([1.0, 2.0, 3.0]) @ A, atol=0.05)  # ridge shrinks about 1 %


def test_cross_family_pcs_come_from_other_families_only(monkeypatch):
    import jlm.mu.S7 as s7

    def fake(self, family):  # other families vary along axis 0 only
        assert family == "multihop"
        return {20: [torch.tensor([[1.0, 0.0, 0.0], [-1.0, 0.0, 0.0]])]}

    monkeypatch.setattr(s7.CrossPCRemoval, "_other_states", fake)
    c = centres.make("xpco4")
    c.fit(ITEMS, "multihop")
    X = centres.apply(c, batch(20))
    assert torch.allclose(X[:, 0], torch.zeros(3), atol=1e-5)  # axis 0 removed
    mu_a = (ITEMS[1].acts[20][0] + ITEMS[2].acts[20][0]) / 2
    assert torch.allclose(X[0, 1:], (ITEMS[0].acts[20][0] - mu_a)[1:], atol=1e-5)


def test_prediction_deflation_removes_the_centred_final_state_direction():
    from jlm.context import FINAL_LAYER

    class Ctx:
        fin = {"a": [0.0, 0.0, 3.0], "b": [0.0, 1.0, 0.0], "c": [0.0, 1.0, 0.0]}

        def at(self, item, layer, i):
            assert layer == FINAL_LAYER
            return torch.tensor(self.fin[item])

    c = centres.make("pdf")
    c.fit(ITEMS, "multihop", ctx=Ctx())
    b = batch(20)
    b.ctx = Ctx()
    X = centres.apply(c, b)
    u = torch.tensor([0.0, -1.0, 3.0]) / torch.tensor([0.0, -1.0, 3.0]).norm()  # a's final state minus b, c's mean
    assert abs(float(X[0] @ u)) < 1e-5
    mu_a = (ITEMS[1].acts[20][0] + ITEMS[2].acts[20][0]) / 2
    x = ITEMS[0].acts[20][0] - mu_a
    assert torch.allclose(X[0], x - (x @ u) * u, atol=1e-5)


def test_same_and_other_language_means(monkeypatch):
    import jlm.mu.S10 as s10

    other = [cap("d", {20: [[0.0, 2.0, 0.0]]}), cap("e", {20: [[0.0, 4.0, 0.0]]}), cap("f", {20: [[8.0, 0.0, 0.0]]})]
    langs = {"a": "x", "b": "x", "c": "y", "d": "x", "e": "x", "f": "y"}
    monkeypatch.setattr(s10, "lang_of", lambda family, item: langs[item])
    s = centres.make("samelang")
    s.min_cells = 1
    s.fit(other, "multilingual_mt")
    cell = centres.cell_refs(ITEMS, "multilingual_mt", 20)[0]  # item a, lang x
    assert torch.allclose(s(cell), torch.tensor([0.0, 3.0, 0.0]))
    o = centres.make("otherlang")
    o.fit(other, "multilingual_mt")
    o.same.min_cells = 1
    assert torch.allclose(o(cell), torch.tensor([8.0, 0.0, 0.0]))


def test_other_family_token_mean_pools_other_families_only(monkeypatch):
    import jlm.mu.S12 as s12

    sums = {"multihop": {(20, " y"): [torch.tensor([9.0, 9.0, 9.0], dtype=torch.float64), 3]},
            "typo": {(20, " y"): [torch.tensor([3.0, 0.0, 0.0], dtype=torch.float64), 3]},
            "association": {(20, " z"): [torch.tensor([1.0, 1.0, 1.0], dtype=torch.float64), 5]}}
    monkeypatch.setattr(s12, "source_sums", lambda layers: sums)
    c = centres.make("xtok")
    c.fit(ITEMS, "multihop")
    cell = centres.cell_refs(ITEMS, "multihop", 20)[0]  # token " y"
    assert torch.allclose(c(cell), torch.tensor([1.0, 0.0, 0.0]))  # typo's cells only: own family excluded
    c.min_cells = 4
    c._memo.clear()
    assert torch.allclose(c(cell), c.fam(cell)) and c.n_fallback == 1


def test_neutral_mean_uses_the_fills_and_falls_back_to_fam(monkeypatch):
    import jlm.mu.S2 as s2

    monkeypatch.setattr(s2, "fill_states", lambda family, cond: {20: torch.tensor([5.0, 5.0, 5.0])}
                        if (family, cond) == ("multihop_mt", "neutral") else None)
    c = centres.make("neu")
    c.fit(ITEMS, "multihop_mt")
    cell = centres.cell_refs(ITEMS, "multihop_mt", 20)[0]
    assert torch.allclose(c(cell), torch.tensor([5.0, 5.0, 5.0]))
    m = centres.make("neuc")
    m.fit(ITEMS, "multihop_mt")
    assert torch.allclose(m(cell), m.fam(cell)) and m.n_fallback == 1
