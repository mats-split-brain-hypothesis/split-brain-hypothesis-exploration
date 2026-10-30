"""Round-2 infrastructure (S13-S20): the pullback geometry on a toy lens, the centres that read its caches, the depth
schedule and the chat pool registration. No model, no files outside tmp_path."""

import torch
from umot.capture import ItemCapture

from jlm import centres, pullback
from jlm.mu import S13, S14, S15, clusters, schedule  # noqa: F401  (register)


class ToyLens:
    """A tiny ``jlm.lens.Lens`` stand-in: V tokens, d dims, one J per layer, cos denominators."""

    def __init__(self, V=40, d=6, layers=(5, 9), seed=0):
        g = torch.Generator().manual_seed(seed)
        self.name, self.identity, self.repo, self.device = "jlens", False, "repo", "cpu"
        self.layers = list(layers)
        self.w_u = torch.randn(V, d, generator=g)
        self.jac = {L: torch.randn(d, d, generator=g) for L in layers}
        self.denom = {L: (self.w_u @ self.jac[L]).norm(dim=1).clamp_min(1e-9) for L in layers}

    @property
    def vocab(self):
        return self.w_u.shape[0]

    def scores(self, x, layer, readout):
        z = x.float() @ self.jac[layer].T
        if readout == "cos":
            return (z @ self.w_u.T) / self.denom[layer]
        return z @ self.w_u.T


def _geo(tmp_path, monkeypatch):
    monkeypatch.setattr(pullback, "lens_key", lambda lens: "toy")
    return pullback.Geometry(ToyLens(), cache=tmp_path)


def test_pullback_reproduces_a_realisable_score_change(tmp_path, monkeypatch):
    geo = _geo(tmp_path, monkeypatch)
    lens = geo.lens
    for readout in ("cos", "rms"):
        g0 = torch.randn(1, 6)
        c = lens.scores(g0, 5, readout)  # a change that some g realises exactly
        g = geo.pullback(c, 5, readout, ridge=1e-9)
        assert geo.fit_quality(c, g, 5, readout)[0] < 1e-3
        assert torch.allclose(g, g0, atol=1e-2), (g, g0)


def test_pullback_ignores_a_constant_shift_and_caches(tmp_path, monkeypatch):
    geo = _geo(tmp_path, monkeypatch)
    c = torch.randn(2, 40)
    g1 = geo.pullback(c, 9, "cos")
    g2 = geo.pullback(c + 3.0, 9, "cos")
    assert torch.allclose(g1, g2, atol=1e-4)
    assert (tmp_path / "pb-eig-toy-cos-L009.pt").exists()
    lam, Q = geo.eig(9, "cos")
    assert lam[0] >= lam[-1] and Q.shape == (6, 6)


def test_rank_limited_pullback_and_reading_basis(tmp_path, monkeypatch):
    geo = _geo(tmp_path, monkeypatch)
    c = torch.randn(1, 40)
    g_full, g_r2 = geo.pullback(c, 5, "cos"), geo.pullback(c, 5, "cos", rank=2)
    assert geo.fit_quality(c, g_full, 5, "cos")[0] <= geo.fit_quality(c, g_r2, 5, "cos")[0] + 1e-6
    B = geo.reading_basis([0, 1, 2], 5, "cos")
    assert B.shape == (6, 3) and torch.allclose(B.T @ B, torch.eye(3), atol=1e-4)
    rows = geo.reading_rows([0, 1, 2], 5, "cos")
    assert torch.allclose(rows, (rows @ B) @ B.T, atol=1e-4)  # the rows lie in their span
    S, Vh = geo.jsvd(5)
    assert S[0] >= S[-1] and torch.allclose(Vh @ Vh.T, torch.eye(6), atol=1e-4)


def _items(n=6, d=6, layers=(5, 9), seed=0):
    g = torch.Generator().manual_seed(seed)
    return [ItemCapture(id=f"i{j}", ids=[0, 1], decoded=["x", f"t{j % 2}"], positions=[-1], idx=[1],
                        acts={L: torch.randn(1, d, generator=g) for L in layers}) for j in range(n)]


def _batch(items, L):
    cells = centres.cell_refs(items, "typo", L)
    return centres.Batch(L, cells, torch.stack([it.acts[L][0].float() for it in items]), {it.id: it for it in items})


def test_s13_prior_and_next_token_centres(tmp_path, monkeypatch):
    monkeypatch.setattr(pullback, "PULLBACK", tmp_path)
    monkeypatch.setattr(pullback, "prior_path", lambda prior, readout, rank: tmp_path / f"{prior}-{readout}-r{rank}.pt")
    monkeypatch.setattr(pullback, "cells_path", lambda f, s, readout, rank: tmp_path / f"nt-{f}-{s}-{readout}-r{rank}.pt")
    g5, g9 = torch.randn(6), torch.randn(6)
    torch.save({"layers": {5: g5, 9: g9}, "meta": {}}, pullback.prior_path("unigram-norobots", "cos", "full"))
    items = _items()
    c = centres.make("s13:unigram-norobots:0.5")
    c.fit(items, "typo")
    b = _batch(items, 9)
    assert torch.allclose(b.H - centres.apply(c, b), 0.5 * g9.expand(6, 6))
    cf = centres.make("s13:unigram-norobots:2:fam")
    cf.fit(items, "typo")
    fam0 = centres.make("fam")
    fam0.fit(items, "typo")
    assert torch.allclose(b.H - centres.apply(cf, b), 2 * g9.expand(6, 6) + (b.H - centres.apply(fam0, b)), atol=1e-5)
    # per-cell pullbacks for the "fit" split: the centre is the family mean of them, own item out
    P = {5: torch.randn(6, 6), 9: torch.randn(6, 6)}
    torch.save({"cells": [(it.id, 0) for it in items], "layers": P, "meta": {}}, pullback.cells_path("typo", "fit", "cos", "full"))
    nt = centres.make("s13nt")
    nt.fit(items, "typo")
    G = b.H - centres.apply(nt, b)
    for j in range(6):
        others = torch.stack([P[9][k] for k in range(6) if k != j])
        assert torch.allclose(G[j], others.mean(0), atol=1e-5)
    ntf = centres.make("s13ntf")
    ntf.fit(items, "typo")
    fam = centres.make("fam")
    fam.fit(items, "typo")
    assert torch.allclose(b.H - centres.apply(ntf, b), G + (b.H - centres.apply(fam, b)), atol=1e-5)


def test_s14_and_s15_remove_the_cached_subspace(tmp_path, monkeypatch):
    monkeypatch.setattr(pullback, "CACHE", tmp_path)
    monkeypatch.setattr(pullback, "default_key", lambda: "toy")
    monkeypatch.setattr(pullback, "tbasis_path", lambda key, readout, ts, k, L: tmp_path / f"tbasis-{key}-{readout}-{ts}-k{k}-L{L:03d}.pt")
    monkeypatch.setattr(pullback, "jsvd_path", lambda key, L: tmp_path / f"jsvd-{key}-L{L:03d}.pt")
    B = torch.linalg.qr(torch.randn(6, 2))[0]
    for L in (5, 9):
        torch.save(B, pullback.tbasis_path("toy", "cos", "template", 16, L))
        torch.save({"S": torch.arange(6, 0, -1).float(), "Vh": torch.linalg.qr(torch.randn(6, 6))[0].T}, pullback.jsvd_path("toy", L))
    items = _items()
    b = _batch(items, 5)
    t = centres.make("s14t16")
    t.fit(items, "typo")
    X = centres.apply(t, b)
    assert torch.allclose(X @ B, torch.zeros(6, 2), atol=1e-5)  # nothing left along B
    assert torch.allclose(X, b.H - (b.H @ B) @ B.T, atol=1e-5)
    tf = centres.make("s14fam16")
    tf.fit(items, "typo")
    fam = centres.make("fam")
    fam.fit(items, "typo")
    Y = centres.apply(fam, b)
    assert torch.allclose(centres.apply(tf, b), Y - (Y @ B) @ B.T, atol=1e-5)
    # S14b: alpha x another centre's g, then the subspace
    th = centres.make("s14:template:16:mean=fam:a=0.5")
    th.fit(items, "typo")
    Z = b.H - 0.5 * (b.H - Y)
    assert torch.allclose(centres.apply(th, b), Z - (Z @ B) @ B.T, atol=1e-5)
    to = centres.make("s14:template:16:o=1")  # S14o: twice the component removed, i.e. reflected
    to.fit(items, "typo")
    assert torch.allclose(centres.apply(to, b), b.H - 2 * (b.H @ B) @ B.T, atol=1e-5)
    r = centres.make("s14r16")
    r.fit(items, "typo")
    assert centres.apply(r, b).shape == (6, 6)
    s = centres.make("s15top8")  # k > d: the whole space, g = h
    s.fit(items, "typo")
    assert centres.apply(s, b).abs().max() < 1e-4
    _, Vh = pullback.load_jsvd("toy", 5)
    s2 = S15.JSubspace(2)
    s2.fit(items, "typo")
    assert torch.allclose(centres.apply(s2, b) @ Vh[:2].T, torch.zeros(6, 2), atol=1e-5)


def test_schedule_switches_centres_by_layer():
    items = _items()
    sch = centres.make("sched:6:fam+zero")
    sch.fit(items, "typo")
    fam = centres.make("fam")
    fam.fit(items, "typo")
    assert torch.allclose(centres.apply(sch, _batch(items, 5)), centres.apply(fam, _batch(items, 5)))
    assert torch.allclose(centres.apply(sch, _batch(items, 9)), _batch(items, 9).H)
    assert sch.support(centres.cell_refs(items, "typo", 9)[0]) == (0, False)
    assert sch.name == "sched:6:fam+zero"


def test_chat_pool_centres_are_registered():
    for name in ("kmch8", "kmchr8", "knnch8"):
        c = centres.make(name)
        assert c.name == name and "chat" in c.doc


def test_s14n_subsampled_cluster_pool(monkeypatch):
    from jlm.mu import S14 as S14mod
    from jlm.mu import clusters

    X = {5: torch.randn(40, 6)}
    groups = [f"g{j // 2}" for j in range(40)]  # 20 groups of 2 rows
    full = clusters.Pool(X, groups, ["typo"] * 40, ["x"] * 40)
    monkeypatch.setattr(clusters, "_POOLS", {("bench",): full})
    c = centres.make("kmxn:4:0.25:1")
    c.fit([], "typo")
    p = c.inner.pool
    assert len(set(p.groups)) == 5 and len(p.groups) == 10  # 25 % of the groups, both rows of each
    assert set(p.groups) <= set(groups)
    c2 = S14mod.make_n("4:0.25:2")  # also registered by name, e.g. kmx64n25d2
    c2.fit([], "typo")
    assert set(c2.inner.pool.groups) != set(p.groups)  # another draw, other groups


def test_s14_prompt_language_codes():
    from jlm.mu import S14 as S14mod

    S14mod._LANG.clear()
    S14mod._LANG.update({"a": "fr", "b": "en"})  # as prompt_language stores them (codes)
    assert S14mod.prompt_language("a") == "fr" and S14mod.prompt_language("zzz") == "en"
    assert S14mod._CODE["french"] == "fr" and S14mod._CODE["turkish"] == "tr"
    S14mod._LANG.clear()


def test_s14_detect_language_from_text():
    from jlm.mu import S14 as S14mod

    assert S14mod.detect_language("Столица Франции это") == "cyr"
    assert S14mod.detect_language("The capital of France is") == "en"
    assert S14mod.detect_language("Le contraire de « fort » est le mot que") == "fr"
    assert S14mod.detect_language("A cor do céu em um dia de verão não é") == "pt"


def test_s14_language_lists_kept_apart(monkeypatch):
    """A detected-language arm and a bank-field arm in one process must not share the pool's language list."""
    from types import SimpleNamespace

    from jlm.mu import S14 as S14mod

    pool = SimpleNamespace(groups=["g"] * 2)
    field_cls = S14mod._other_language_class()
    det_cls = S14mod._detected_language_class()
    for cls, lang in ((det_cls, "xx"), (field_cls, "yy")):
        c = object.__new__(cls)
        c.pool = pool
        monkeypatch.setattr(cls, "cell_language", lambda self, item_id, lang=lang: lang)
        attr = f"langs_{c.lang_source}"
        setattr(pool, attr, [c.cell_language("i")] * 2)
    assert pool.langs_detected == ["xx", "xx"] and pool.langs_field == ["yy", "yy"]
    assert field_cls.lang_source == "field" and det_cls.lang_source == "detected"
