"""Tests of the constant-mu exploration's centres (src/jlm/mu/constant_mu.py; x1-x12, notes/predictions.md)."""

import torch
from umot.capture import ItemCapture

from jlm import centres
from jlm.mu import constant_mu as cm


def cap(iid: str, toks: list[str], acts: dict[int, list[list[float]]]) -> ItemCapture:
    n = len(next(iter(acts.values())))
    return ItemCapture(
        id=iid, ids=list(range(len(toks))), decoded=toks, positions=list(range(-n, 0)),
        idx=list(range(len(toks) - n, len(toks))), acts={L: torch.tensor(v) for L, v in acts.items()},
    )


def test_parametric_names_build_the_study_centres():
    assert centres.make("genk:8").name == "genk:8" and centres.make("dict:fam:0.5").mode == "fam"


def test_pos_mean_keys_on_absolute_position_and_clamps():
    corpus = [
        cap("p", ["a", "b", "c"], {5: [[0.0, 0.0], [2.0, 0.0], [4.0, 0.0]]}),
        cap("q", ["x", "y", "z"], {5: [[0.0, 2.0], [0.0, 4.0], [0.0, 6.0]]}),
    ]
    c = cm.PosMean(min_cells=1)
    c.fit(corpus, "typo")
    read = cap("r", ["long", "er", "pro", "mpt"], {5: [[9.0, 9.0]]})  # read at index 3 > cap 2
    one, _, _ = centres.cell_refs(corpus[:1], "typo", 5)
    assert torch.allclose(c(one), torch.tensor([0.0, 2.0]))  # position 0: only q's cell (own item out)
    (far,) = centres.cell_refs([read], "typo", 5)
    assert torch.allclose(c(far), torch.tensor([2.0, 3.0]))  # clamped to position 2: mean of c, z


def carrier(word: str, k: int, vec: list[float]) -> ItemCapture:
    return cap(f"{word}::{k}", ["the", f" {word}"], {5: [vec]})


def test_concept_centre_scales_a_unit_direction(tmp_path):
    from umot import capture as ucap

    path = tmp_path / "carriers.pt"
    ucap.save([carrier("typo", 0, [3.0, 0.0]), carrier("typo", 1, [1.0, 0.0]),
               carrier("giraffe", 0, [0.0, 2.0]), carrier("violin", 0, [0.0, 4.0])], path)
    ref = [cap("r1", ["x", "y"], {5: [[5.0, 0.0]]}), cap("r2", ["x", "y"], {5: [[0.0, 5.0]]})]

    c = cm.ConceptCentre("typo", 0.5, contrast=False, plus_ref=False, carriers=path)
    c.fit(ref, "typo")
    cell = centres.cell_refs(ref, "typo", 5)[0]
    assert torch.allclose(c(cell), torch.tensor([2.5, 0.0]))  # 0.5 * mean ref norm 5 * unit [1, 0]

    cc = cm.ConceptCentre("typo", 1.0, contrast=True, plus_ref=False, carriers=path)
    cc.fit(ref, "typo")
    v = torch.tensor([2.0, -3.0])  # [2, 0] - [0, 3]
    assert torch.allclose(cc(cell), 5 * v / v.norm())

    cp = cm.ConceptCentre("typo", 0.5, contrast=False, plus_ref=True, carriers=path)
    cp.fit(ref, "typo")
    assert torch.allclose(cp(cell), torch.tensor([2.5, 0.0]) + torch.tensor([0.0, 5.0]))  # own item excluded


def test_dict_centre_modes(tmp_path):
    from umot import capture as ucap

    path = tmp_path / "carriers-dict.pt"
    ucap.save([carrier("typo", 0, [4.0, 0.0]), carrier("fact", 0, [0.0, 4.0]),
               carrier("giraffe", 0, [1.0, 1.0]), carrier("violin", 0, [1.0, 1.0]),
               carrier("glacier", 0, [1.0, 1.0])], path)
    ref = [cap("r1", ["x", "y"], {5: [[10.0, 0.0]]})]
    sents = tmp_path / "sents.pt"
    ucap.save([cap("s1", ["x", "y"], {5: [[0.0, 0.0]]})], sents)

    c = cm.DictCentre("fam", 0.5, carriers=path)
    c.fit(ref, "typo")
    cell = centres.cell_refs(ref, "typo", 5)[0]
    assert torch.allclose(c(cell), torch.tensor([5.0, 0.0]))  # 0.5 * 10 * unit typo

    d = cm.DictCentre("derang", 1.0, carriers=path)
    d.fit(ref, "multihop")
    cell_m = centres.cell_refs(ref, "multihop", 5)[0]
    assert d.word_of(cell_m) == "pet"  # the registered wrong-word map

    s = cm.DictCentre("strat", 1.0, carriers=path)
    s.set_bank("basic_readout", [{"id": "r1", "subfamily": "entity"}])
    s.fit(ref, "basic_readout")
    cell_b = centres.cell_refs(ref, "basic_readout", 5)[0]
    assert s.word_of(cell_b) == "fact"

    f = cm.DictCentre("free", 1.0, carriers=path, sents=sents)
    f.fit(ref, "typo")
    # the read state [10, 0] matches typo's contrast direction, not fact's
    (cell_f,) = centres.cell_refs(ref, "typo", 5)
    assert f.word_of(cell_f, torch.tensor([10.0, 0.0])) == "typo"
    out = centres.apply(f, centres.Batch(5, [cell_f], torch.tensor([[10.0, 0.0]]), {}))  # transform reads H
    assert torch.allclose(out[0], torch.tensor([10.0, 0.0]) - f.alpha * f.s[5] * f.v["typo"][5])
    f2 = cm.DictCentre("free", 1.0, carriers=path, sents=sents)
    f2.fit([cap("r2", ["x", "y"], {5: [[0.0, 10.0]]})], "typo")
    assert f2.word_of(centres.cell_refs([cap("r2", ["x", "y"], {5: [[0.0, 10.0]]})], "typo", 5)[0],
                      torch.tensor([0.0, 10.0])) == "fact"


def test_dict_centre_fam2_and_plus_ref(tmp_path):
    from umot import capture as ucap

    path = tmp_path / "carriers-dict.pt"
    ucap.save([carrier("association", 0, [4.0, 0.0]), carrier("giraffe", 0, [1.0, 1.0]),
               carrier("violin", 0, [1.0, 1.0]), carrier("glacier", 0, [1.0, 1.0])], path)
    ref = [cap("r1", ["x", "y"], {5: [[0.0, 10.0]]})]
    c = cm.DictCentre("fam2+", 0.5, carriers=path)
    c.fit(ref, "association")
    cell = centres.cell_refs(ref, "association", 5)[0]
    # 0.5 * norm 10 * unit [1,0]  +  ref mean with own item excluded -> error? ref has one item:
    # use a second ref item so the base mean exists for the read cell's exclusion
    ref2 = [cap("r1", ["x", "y"], {5: [[0.0, 10.0]]}), cap("r2", ["x", "y"], {5: [[0.0, 6.0]]})]
    c.fit(ref2, "association")
    cell = centres.cell_refs(ref2, "association", 5)[0]  # item r1: base = mean of r2 = [0, 6]
    assert c.word_of(cell) == "association"
    assert torch.allclose(c(cell), torch.tensor([4.0, 0.0]) + torch.tensor([0.0, 6.0]))
    assert centres.make("dict:fam2+:0.5").plus_ref and centres.make("dict:fam2:1").mode == "fam2"


def test_gen_mean_is_per_item(tmp_path, monkeypatch):
    from umot import capture as ucap

    from jlm.mu import constant_mu as cmod

    gendir = tmp_path / "captures"
    gendir.mkdir()
    ucap.save([cap("a::g0", ["x", "y"], {5: [[2.0, 0.0]]}), cap("a::g1", ["x", "y"], {5: [[4.0, 0.0]]}),
               cap("b::g0", ["x", "y"], {5: [[0.0, 8.0]]})], gendir / "gen-typo-val.pt")
    monkeypatch.setattr(cmod, "OUT", tmp_path)
    read = [cap("a", ["x", "y"], {5: [[9.0, 9.0]]}), cap("b", ["x", "y"], {5: [[9.0, 9.0]]}),
            cap("c", ["x", "y"], {5: [[9.0, 9.0]]})]
    g = cmod.GenMean()
    g.fit(read, "typo")
    cell_a, _, cell_c = centres.cell_refs(read, "typo", 5)
    assert torch.allclose(g(cell_a), torch.tensor([3.0, 0.0]))  # mean of a's two refs
    assert torch.allclose(g(cell_c), torch.tensor([1.5, 4.0])) and g.n_fallback == 1  # wide mean

    x = cmod.GenOtherMean()
    x.fit(read, "typo")
    assert torch.allclose(x(cell_a), torch.tensor([0.0, 8.0]))  # a's derangement partner is b
    f = cmod.GenFamilyMean()
    f.fit(read, "typo")
    assert torch.allclose(f(cell_a), torch.tensor([0.0, 8.0]))  # every other item's refs: only b
    assert torch.allclose(f(cell_c), torch.tensor([1.5, 4.0]))  # c has no refs: the whole pool

    k1, kall = centres.make("genk:1"), centres.make("genk:99")
    k1.fit(read, "typo")
    kall.fit(read, "typo")
    assert torch.allclose(k1(cell_a), x(cell_a)) and torch.allclose(kall(cell_a), f(cell_a))

    # references of items outside the bank being fitted on (another split's generations) are not drawn on
    g2 = cmod.GenFamilyMean()
    g2.fit(read[:1] + read[2:], "typo")  # bank {a, c}: b's references belong to another bank
    assert torch.allclose(g2(cell_c), torch.tensor([3.0, 0.0]))  # the pool is a's alone


def test_glossary_mean_and_swap(tmp_path, monkeypatch):
    from umot import capture as ucap

    from jlm.mu import constant_mu as cmod

    (tmp_path / "captures").mkdir()
    ucap.save([cap("g::0", ["x", "y"], {5: [[2.0, 0.0]]}), cap("g::1", ["x", "y"], {5: [[4.0, 2.0]]})],
              tmp_path / "captures" / "glos-desc-typo.pt")
    ucap.save([cap("g::0", ["x", "y"], {5: [[0.0, 6.0]]})], tmp_path / "captures" / "glos-desc-association.pt")
    monkeypatch.setattr(cmod, "OUT", tmp_path)
    read = [cap("a", ["x", "y"], {5: [[9.0, 9.0]]})]
    (cell,) = centres.cell_refs(read, "typo", 5)
    g = centres.make("glos:desc")
    g.fit(read, "typo")
    assert torch.allclose(g(cell), torch.tensor([3.0, 1.0]))  # the typo entry's mean
    x = centres.make("glosx:desc")
    x.fit(read, "typo")
    assert torch.allclose(x(cell), torch.tensor([0.0, 6.0]))  # typo reads use association's entry


def test_make_parses_concept_names():
    c = centres.make("cptc+:typo:0.5")
    assert (c.word, c.alpha, c.contrast, c.plus_ref) == ("typo", 0.5, True, True)
    c = centres.make("cpt:misspelling")
    assert (c.word, c.alpha, c.contrast, c.plus_ref) == ("misspelling", 1.0, False, False)
    assert centres.make("pos").name == "pos"




def test_x14_file_and_universal_glossary_means(tmp_path, monkeypatch):
    from umot import capture as ucap

    (tmp_path / "captures").mkdir()
    monkeypatch.setattr(cm, "OUT", tmp_path)
    ucap.save([cap("n::0", ["x", "y"], {5: [[2.0, 0.0]]}), cap("n::1", ["x", "y"], {5: [[4.0, 0.0]]})],
              tmp_path / "captures" / "null-typo.pt")
    ucap.save([cap("g::0", ["x", "y"], {5: [[0.0, 2.0]]})], tmp_path / "captures" / "glos-word-typo.pt")
    ucap.save([cap("g::0", ["x", "y"], {5: [[0.0, 6.0]]}), cap("g::1", ["x", "y"], {5: [[0.0, 6.0]]})],
              tmp_path / "captures" / "glos-word-association.pt")
    read = [cap("a", ["x", "y"], {5: [[9.0, 9.0]]})]
    (cell,) = centres.cell_refs(read, "typo", 5)
    f = centres.make("null")
    f.fit(read, "typo")
    assert torch.allclose(f(cell), torch.tensor([3.0, 0.0]))
    u = centres.make("glosall:word")
    u.fit(read, "typo")  # equal weight per family set, not per text: (2 + 6) / 2
    assert torch.allclose(u(cell), torch.tensor([0.0, 4.0])) and u.n == 2


def test_x14_corpus_pc_removal_and_massive_dims(monkeypatch):
    X = torch.zeros(64, 3)
    X[:, 0] = torch.linspace(-5, 5, 64)  # the corpus varies along dimension 0 only
    X[:, 2] = 7.0  # and carries a large constant on dimension 2
    monkeypatch.setattr(cm, "_corpus_sample", lambda *a, **k: {5: X})
    b = centres.Batch(5, [], torch.tensor([[3.0, 1.0, 9.0]]), {})
    pc = centres.make("pcw:1")
    pc.fit([], "typo")
    out = pc.transform(b)[0]  # mean (0, 0, 7) removed, then the dimension-0 direction projected out
    assert torch.allclose(out, torch.tensor([0.0, 1.0, 2.0]), atol=1e-4)
    keep, zero = centres.make("massive:1"), centres.make("massivez:1")
    keep.fit([], "typo")
    zero.fit([], "typo")
    assert torch.allclose(keep.transform(b)[0], torch.tensor([3.0, 1.0, 7.0]))  # dimension 2 set to its corpus mean
    assert torch.allclose(zero.transform(b)[0], torch.tensor([3.0, 1.0, 0.0]))  # or removed


def test_x17_token_matched_synthetic_mean(tmp_path, monkeypatch):
    from umot import capture as ucap

    (tmp_path / "captures").mkdir()
    monkeypatch.setattr(cm, "OUT", tmp_path)

    def gen(iid, tok, v):  # one written reference whose read token is ``tok``
        it = cap(iid, ["x", tok], {5: [v]})
        return it

    ucap.save([gen("b::g0", "team", [0.0, 3.0]), gen("b::g1", "team", [0.0, 5.0]), gen("c::g0", "team", [0.0, 7.0]),
               gen("b::g2", "the", [9.0, 0.0])], tmp_path / "captures" / "gen-directed_modulation-val.pt")
    read = [cap("a", ["x", "team"], {5: [[1.0, 1.0]]}), cap("b", ["x", "team"], {5: [[1.0, 1.0]]}),
            cap("c", ["x", "sat"], {5: [[1.0, 1.0]]})]
    g = centres.make("gentok")
    g.fit(read, "directed_modulation")
    cell_a, cell_b, cell_c = centres.cell_refs(read, "directed_modulation", 5)
    assert torch.allclose(g(cell_a), torch.tensor([0.0, 5.0]))  # a: every 'team' reference of b and c: (3+5+7)/3
    # b: its own 'team' references are left out, leaving one (c's): below 3 cells, so the pooled synthetic mean
    assert torch.allclose(g(cell_b), cm.GenFamilyMean.lookup(g, cell_b))
    assert torch.allclose(g(cell_c), cm.GenFamilyMean.lookup(g, cell_c))  # no 'sat' references: pooled


def test_x20_lens_fit_mean_is_one_constant_per_layer(tmp_path, monkeypatch):
    (tmp_path / "captures").mkdir()
    monkeypatch.setattr(cm, "OUT", tmp_path)
    torch.save({"mean": {5: torch.tensor([1.0, -1.0]).double()}, "n_prompts": 2, "n_cells": 9}, tmp_path / "captures" / "fitmu.pt")
    c = centres.make("fitmu")
    c.fit([], "directed_modulation")  # no reference needed: the same vector for every family and cell
    for read in ([cap("a", ["x", "y"], {5: [[9.0, 9.0]]})], [cap("b", ["p"], {5: [[0.0, 3.0]]})]):
        (cell,) = centres.cell_refs(read, "typo", 5)
        assert torch.equal(c(cell), torch.tensor([1.0, -1.0])) and c.support(cell) == (0, False)


class _Ctx:
    """A stand-in context store: every position's state per item at one layer."""

    def __init__(self, states: dict[str, list[list[float]]], idx: dict[str, list[int]], layer: int = 5):
        from types import SimpleNamespace

        self.layer = layer
        self._s = {i: torch.tensor(v) for i, v in states.items()}
        self.items = {i: SimpleNamespace(idx=idx[i], acts={layer: self._s[i]}) for i in states}

    def states(self, item, layer):
        return self._s[item]


def test_x23_sentence_mean_leaves_out_position_zero_and_optionally_the_read_cell():
    read = [cap("a", ["<s>", "x", "y", "z"], {5: [[9.0, 0.0]]})]  # read at index 3
    ctx = _Ctx({"a": [[100.0, 100.0], [2.0, 0.0], [4.0, 0.0], [9.0, 0.0]]}, {"a": [3]})
    (cell,) = centres.cell_refs(read, "typo", 5)
    batch = centres.Batch(5, [cell], torch.tensor([[9.0, 0.0]]), {"a": read[0]}, ctx)
    s, sx = centres.make("sent:1"), centres.make("sentx:0.5")
    assert torch.allclose(s.transform(batch), torch.tensor([[9.0 - 5.0, 0.0]]))  # mean of 2, 4, 9
    assert torch.allclose(sx.transform(batch), torch.tensor([[9.0 - 1.5, 0.0]]))  # 0.5 x mean of 2, 4


def test_x23_one_word_mean_per_item(tmp_path, monkeypatch):
    import json

    from umot import capture as ucap

    (tmp_path / "captures").mkdir()
    monkeypatch.setattr(cm, "OUT", tmp_path)
    monkeypatch.setattr(cm, "X23_WORDS", tmp_path / "captures" / "x23-words.json")
    cm.X23_WORDS.write_text(json.dumps({"ctx": {"a": "spelling", "b": "recall", "c": "unseen"}, "topic": {}}))
    ucap.save([cap("spelling::0", ["x", "y"], {5: [[2.0, 0.0]]}), cap("spelling::1", ["x", "y"], {5: [[4.0, 0.0]]}),
               cap("recall::0", ["x", "y"], {5: [[0.0, 6.0]]})], tmp_path / "captures" / "x23-ctx-plain.pt")
    c = centres.make("word:ctx")
    c.fit([], "typo")
    read = [cap(i, ["x", "y"], {5: [[1.0, 1.0]]}) for i in "abc"]
    a, b, u = centres.cell_refs(read, "typo", 5)
    assert torch.allclose(c(a), torch.tensor([3.0, 0.0])) and torch.allclose(c(b), torch.tensor([0.0, 6.0]))
    assert torch.equal(c(u), torch.zeros(2)) and c.n_fallback == 1 and c.support(u) == (0, True)


def test_x23_neighbours_keyed_by_context_never_the_read_item(monkeypatch):
    from types import SimpleNamespace

    from jlm import banks, capture, context

    monkeypatch.setattr(cm, "ALL_FAMILIES", ("typo", "association"))
    fit = {  # item -> (context states, read-cell state); keys = mean of positions 1 .. t-1 (t = 2: position 1 only)
        "typo": {"t1": ([[0, 0], [1, 0], [5, 5]], [10.0, 0.0]), "t2": ([[0, 0], [1, 0.1], [5, 5]], [20.0, 0.0])},
        "association": {"a1": ([[0, 0], [0, 1], [5, 5]], [0.0, 30.0])},
    }
    monkeypatch.setattr(banks, "load", lambda f, s: SimpleNamespace(family=f, items=[{"id": i} for i in fit[f]]))
    monkeypatch.setattr(capture, "load", lambda b: [cap(i, ["x", "y", "z"], {5: [v[1]]}) for i, v in fit[b.family].items()])
    monkeypatch.setattr(context.ContextStore, "of", classmethod(
        lambda cls, b: _Ctx({i: v[0] for i, v in fit[b.family].items()}, {i: [2] for i in fit[b.family]})))
    c = centres.make("sentnn:1:all")
    c.fit([], "typo")
    read = [cap("t1", ["x", "y", "z"], {5: [[7.0, 7.0]]})]
    (cell,) = centres.cell_refs(read, "typo", 5)
    ctx = _Ctx({"t1": fit["typo"]["t1"][0]}, {"t1": [2]})
    out = c.transform(centres.Batch(5, [cell], torch.tensor([[7.0, 7.0]]), {"t1": read[0]}, ctx))
    assert torch.allclose(out, torch.tensor([[7.0 - 20.0, 7.0]]))  # nearest key is t1 itself (excluded), then t2
    o = centres.make("sentnn:1:others")
    o.fit([], "typo")
    out = o.transform(centres.Batch(5, [cell], torch.tensor([[7.0, 7.0]]), {"t1": read[0]}, ctx))
    assert torch.allclose(out, torch.tensor([[7.0, 7.0 - 30.0]]))  # only the other family's cell
