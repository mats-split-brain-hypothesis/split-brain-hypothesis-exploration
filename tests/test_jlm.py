"""Offline checks of the pipeline's pieces: no model, lens or network."""

import json

import torch
from umot.capture import ItemCapture

from jlm import banks, centres, forms, geometry, score
from jlm.banks import Bank


def cap(iid: str, toks: list[str], acts: dict[int, list[list[float]]]) -> ItemCapture:
    n = len(next(iter(acts.values())))
    return ItemCapture(
        id=iid, ids=list(range(len(toks))), decoded=toks, positions=list(range(-n, 0)),
        idx=list(range(len(toks) - n, len(toks))), acts={L: torch.tensor(v) for L, v in acts.items()},
    )


ITEMS = [
    cap("a", ["x", " cat"], {5: [[1.0, 0.0]]}),
    cap("b", ["y", " dog"], {5: [[3.0, 0.0]]}),
    cap("c", ["z", " cat"], {5: [[0.0, 6.0]]}),
]


def test_family_mean_excludes_own_item():
    c = centres.make("fam")
    c.fit(ITEMS, "typo")
    cell = centres.cell_refs(ITEMS, "typo", 5)[0]  # item a
    assert torch.allclose(c(cell), torch.tensor([1.5, 3.0]))


def test_family_mean_on_other_bank_uses_all_cells():
    c = centres.make("fam")
    c.fit(ITEMS[1:], "typo")
    cell = centres.cell_refs(ITEMS[:1], "typo", 5)[0]
    assert torch.allclose(c(cell), torch.tensor([1.5, 3.0]))


def test_token_mean_falls_back_below_min_cells():
    c = centres.TokenMean(min_cells=1)
    c.fit(ITEMS, "typo")
    a, b, _ = centres.cell_refs(ITEMS, "typo", 5)
    assert torch.allclose(c(a), torch.tensor([0.0, 6.0]))  # the other " cat" cell
    assert torch.allclose(c(b), torch.tensor([0.5, 3.0]))  # no other " dog": family mean of a, c
    assert c.n_fallback == 1


def test_min_pos_view_drops_early_positions():
    from jlm import capture as jcap

    it = cap("p", ["a", "b", "c"], {5: [[1.0, 0.0], [2.0, 0.0], [3.0, 0.0]]})
    (view,) = jcap.min_pos_view([it], 1)
    assert view.idx == [1, 2] and torch.allclose(view.acts[5], torch.tensor([[2.0, 0.0], [3.0, 0.0]]))
    assert jcap.min_pos_view([it], 3) == []


def test_cellref_hides_targets():
    fields = set(centres.CellRef.__dataclass_fields__)
    assert not fields & {"target", "targets", "intermediates", "units"}


def test_strict_rule_is_whole_token():
    bank = Bank("typo", "fit", None, {}, [{"id": "a", "name": "a", "intermediates": ["February"]}])
    rows = [{"id": "a", "tokens": [" Febr", "uary"]}, {"id": "a", "tokens": [" february"]}]
    assert score.strict_items(rows[:1], bank) == {"a": False}
    assert score.strict_items(rows, bank) == {"a": True}


def test_confirmatory_flags_leak_and_unreachable():
    items = [{"id": "a", "name": "a", "intermediates": ["cat"]}, {"id": "b", "name": "b", "intermediates": ["blue whale"]},
             {"id": "c", "name": "c", "intermediates": ["dog"]}]
    bank = Bank("typo", "fit", None, {}, items)
    acc = score.accepted_ids([" cat", " dog", "x"], bank)
    conf = score.confirmatory(bank, acc, {"a": ["the", " cat"], "b": ["x"], "c": ["x"]})
    assert conf == {"a": "leak", "b": "unreachable", "c": ""}  # b: no single-word target
    gnu = Bank("typo", "fit", None, {}, [{"id": "g", "name": "g", "intermediates": ["gnu"]}])
    assert score.confirmatory(gnu, score.accepted_ids(["x"], gnu), {"g": ["x"]}) == {"g": ""}  # scored, cannot pass


def test_forms_credit_inflections_and_leak_through_them():
    items = [{"id": "a", "name": "a", "intermediates": ["swimming"]}, {"id": "b", "name": "b", "intermediates": ["cow"]},
             {"id": "c", "name": "c", "intermediates": ["tiramisu"]}]
    bank = Bank("association", "fit", None, {}, items)
    extra = {"swimming": ("swim", "swims"), "cow": ("cows",), "tiramisu": ("tiramisus",)}
    rows = [{"id": "a", "tokens": [" swims"]}, {"id": "b", "tokens": [" cows"]}, {"id": "c", "tokens": [" tira"]}]
    assert score.strict_items(rows, bank) == {"a": False, "b": False, "c": False}
    assert score.strict_items(rows, bank, extra) == {"a": True, "b": True, "c": False}
    vocab, prompts = [" swims", " cow", " cows", " tira", "x"], {"a": ["x"], "b": [" cows"], "c": ["x"]}
    strict, ext = (forms.Scorer.of(bank, vocab, prompts, e) for e in (None, extra))
    assert strict.ids == ["a", "b", "c"] and ext.ids == ["a", "c"]  # b's prompt spells an added form: a leak
    assert strict.reachable == ["b"] and ext.reachable == ["a"]  # c: no form is one token
    fields, passes = forms.arm_fields(strict, ext, rows)
    assert fields["forms"]["strict"]["value"] == 0.5 and fields["forms"]["reachable"]["value"] == 1.0
    assert fields["strict_reachable"]["value"] == 0.0 and passes["a"]


def test_forms_table_keys_are_the_items_own_forms():
    assert forms.key({"man", "boy", "male"}) == "boy|male|man"
    item = {"id": "u", "name": "u", "intermediates": ["male", "man", "boy"]}
    assert score.accepted_forms(item, {"boy|male|man": ("men",)}) == {"male", "man", "boy", "men"}


def test_number_targets_accept_their_other_spelling():
    import sys

    sys.path.insert(0, str(__import__("jlm").REPO_ROOT / "experiments"))
    from build_forms import clean, number_forms

    assert number_forms(["9"]) == ["nine"] and number_forms(["nine"]) == ["9"] and number_forms(["40"]) == ["forty"]
    assert number_forms(["9", "ten"]) == ["nine"]  # the bench's mislabelled 10 - 1: the digit's word, never "10"
    assert number_forms(["2", "two"]) == [] and number_forms(["100"]) == []
    assert clean("multihop", "9", []) == ["nine"]  # --clean keeps them
    item = {"id": "u", "name": "u", "intermediates": ["9"]}
    assert score.accepted_forms(item, {"9": ("nine",)}) == {"9", "nine"}
    assert "nine" in forms.table("multihop")["9"]


def test_specs_plan_a_dev_bank_with_the_bench_rule(tmp_path):
    path = tmp_path / "fit.json"
    path.write_text(json.dumps({"family": "typo", "items": [
        {"name": "dev-1", "prompt": "She sliced a fresh orange carot", "intermediates": ["carrot"]}]}))
    header, items = banks.load_bank(path)
    bank = Bank("typo", "fit", path, header, items)
    (spec,) = banks.specs(bank)
    bench = banks.specs(banks.load("typo", "bench"))[0]
    assert (spec.id, spec.text, spec.render, spec.positions, spec.layers) == (
        "dev-1", "She sliced a fresh orange carot", bench.render, bench.positions, bench.layers)


def test_user_modeling_judge_reads_our_bank(tmp_path, monkeypatch):
    from wsbench.evals.user_modeling import judge as um

    from jlm import judge as jj

    path = tmp_path / "val.json"
    items = [{"name": f"dev-{k}", "attr_class": "Gender", "attr": a, "messages": [], "intermediates": [a]}
             for k, a in enumerate(["male", "female"])]
    path.write_text(json.dumps({"family": "user_modeling", "items": items}))
    seen = {}

    def fake_run(args):
        seen["bank"] = um.load_bank("user_modeling")["items"]
        return "ran"

    monkeypatch.setattr(um, "run", fake_run)
    header, loaded = banks.load_bank(path)
    assert jj._run(Bank("user_modeling", "val", path, header, loaded), None) == "ran"
    assert [it["name"] for it in seen["bank"]] == ["dev-0", "dev-1"]
    assert um.load_bank("user_modeling")["items"][0]["name"] != "dev-0"  # restored to the bench's


def test_directed_modulation_judge_reads_our_bank(tmp_path, monkeypatch):
    from wsbench.evals.directed_modulation import judge as dm

    from jlm import judge as jj

    bench = dm.BANK
    seen = {}
    monkeypatch.setattr(dm, "run", lambda args: seen.setdefault("bank", dm.BANK))
    path = tmp_path / "val.json"
    jj._run(Bank("directed_modulation", "val", path, {}, []), None)
    assert seen["bank"] == path and dm.BANK == bench


def test_group_members_never_centre_each_other():
    twins = [cap("p-pos", ["x", " a"], {5: [[1.0, 0.0]]}), cap("p-neg", ["x", " a"], {5: [[3.0, 0.0]]}),
             cap("q", ["x", " a"], {5: [[0.0, 6.0]]})]
    groups = {"p-pos": "p", "p-neg": "p", "q": "q"}
    c = centres.make("fam")
    c.fit(twins, "directed_modulation", groups)
    cell = centres.cell_refs(twins, "directed_modulation", 5, groups)[0]  # p-pos: its twin p-neg is excluded too
    assert torch.allclose(c(cell), torch.tensor([0.0, 6.0]))


def test_multi_token_judge_reads_our_bank(tmp_path, monkeypatch):
    from wsbench.multitoken import family as mt

    from jlm import judge as jj

    path = tmp_path / "val.json"
    path.write_text(json.dumps({"family": "typo_mt", "items": [{"name": "dev-0"}]}))
    seen = {}
    monkeypatch.setattr(mt, "run_family", lambda args, name: seen.setdefault("items", mt.load_bank("ignored")[1]))
    jj._run(Bank("typo_mt", "val", path, {}, []), None)
    assert [it["name"] for it in seen["items"]] == ["dev-0"]
    assert mt.load_bank.__module__ == "wsbench.banks"  # restored


def test_piece_proxy_needs_every_required_unit_at_one_layer():
    from jlm.mtproxy import Unit, item_passes

    units = {"x": [Unit("concept", True, frozenset({" sand"}), frozenset({1})),
                   Unit("language", True, frozenset({" Arabic"}), frozenset({2})),
                   Unit("target", False, frozenset({" Paris"}), frozenset({3}))]}
    split = [{"id": "x", "layer": 20, "tokens": [" sand"]}, {"id": "x", "layer": 24, "tokens": [" Arabic", " Paris"]}]
    assert item_passes(split, units) == {"x": False}  # the two required units hit at different layers
    assert item_passes([{"id": "x", "layer": 20, "tokens": [" Arabic", " sand"]}], units) == {"x": True}


def test_support_counts_the_cells_behind_mu():
    c = centres.make("tok")  # min 3 cells: every cell here falls back to the family mean
    c.fit(ITEMS, "typo")
    a, b, _ = centres.cell_refs(ITEMS, "typo", 5)
    assert c.support(a) == (2, True)  # family mean without item a
    f = centres.make("fam")
    f.fit(ITEMS, "typo")
    assert f.support(b) == (2, False)
    assert centres.make("zero").support(a) == (0, False)


def test_cell_stats_match_the_centred_vector():
    c = centres.make("fam")
    c.fit(ITEMS, "typo")
    rows = geometry.cell_stats(geometry.Fitted("typo", ITEMS, c, {}))
    a = rows[0]  # h = (1, 0), mu = (1.5, 3)
    assert abs(a["norm_x"] - (0.25 + 9) ** 0.5) < 1e-5 and abs(a["norm_mu"] - (1.5**2 + 9) ** 0.5) < 1e-5
    assert abs(a["cos"] - 1.5 / (1.5**2 + 9) ** 0.5) < 1e-5 and a["support"] == 2


def test_uncentred_pca_keeps_the_origin():
    X = torch.tensor([[10.0, 1.0], [10.0, -1.0], [10.0, 0.0]])
    basis, origin, share = geometry.pca(X, k=2, centred=False)
    assert torch.equal(origin, torch.zeros(2)) and abs(abs(basis[0, 0].item()) - 1) < 1e-5 and share[0] > 0.9
    basis, origin, share = geometry.pca(X, k=1)
    assert torch.allclose(origin, torch.tensor([10.0, 0.0])) and abs(abs(basis[0, 1].item()) - 1) < 1e-5
    assert torch.allclose(geometry.project(X, basis, origin).abs().squeeze(), torch.tensor([1.0, 1.0, 0.0]))


def _batch(items, layer=5):
    cells = centres.cell_refs(items, "typo", layer)
    H = torch.stack([it.acts[layer][c.i].float() for c, it in zip(cells, items, strict=True)])
    return centres.Batch(layer, cells, H, {it.id: it for it in items})


def test_apply_matches_per_cell_centre():
    c = centres.make("fam")
    c.fit(ITEMS, "typo")
    b = _batch(ITEMS)
    assert torch.allclose(centres.apply(c, b), b.H - torch.stack([c(x) for x in b.cells]))


def test_shuffled_control_gives_every_cell_another_cells_g():
    c = centres.make("shuf.tok")
    c.fit(ITEMS, "typo")
    b = _batch(ITEMS)
    G = b.H - centres.apply(c.inner, b)
    Gs = b.H - centres.apply(c, b)
    perm = centres._derangement(3, 5)
    assert (perm != torch.arange(3)).all() and sorted(perm.tolist()) == [0, 1, 2]
    assert torch.allclose(Gs, G[perm])


def test_random_control_keeps_g_norm():
    c = centres.make("rand.fam")
    c.fit(ITEMS, "typo")
    b = _batch(ITEMS)
    G = b.H - centres.apply(c.inner, b)
    R = b.H - centres.apply(c, b)
    assert torch.allclose(R.norm(dim=1), G.norm(dim=1), atol=1e-5)
    assert not torch.allclose(R, G)


def test_prompt_forms_drop_template_tokens_and_mask_every_variant():
    from jlm import controls

    decoded = {"a": ["<|im_start|>", "user", " Paris", " is"], "b": ["<|im_start|>", "user", " Rome", " is"],
               "c": ["<|im_start|>", "user", " cat"]}
    forms = controls.prompt_forms(decoded)
    assert forms["a"] == {"paris"} and forms["c"] == {"cat"}  # "is", "user" are in >= half the renders
    ids = controls.mask_ids(forms, ["Paris", " paris", " Paris", "Par", " cat"])
    assert ids["a"] == [0, 1, 2] and ids["c"] == [4]
    assert controls.echo({"tokens": [" Paris", " France"]}, forms["a"]) == 0.5


def test_context_store_round_trip(tmp_path):
    from jlm import context

    rows = [context.CtxItem("a", [1, 2, 3], ["x", "y", "z"], [2], {5: torch.arange(6.0).reshape(3, 2).bfloat16()})]
    path = tmp_path / "ctx.pt"
    torch.save([vars(r) for r in rows], path)
    s = context.ContextStore(path)
    assert s.layers() == [5] and s.at("a", 5, 0).tolist() == [4.0, 5.0] and s.states("a", 5).shape == (3, 2)


def test_context_centre_reads_the_items_own_previous_positions(tmp_path):
    from jlm import context

    acts = torch.arange(10.0).reshape(5, 2)  # 5 positions, d = 2
    it = ItemCapture(id="a", ids=[0, 1, 2, 3, 4], decoded=list("abcde"), positions=[-1], idx=[4], acts={5: acts[4:]})
    torch.save([vars(context.CtxItem("a", it.ids, it.decoded, [4], {5: acts.bfloat16()}))], tmp_path / "c.pt")
    c = centres.make("prev4")
    c.fit([it], "typo")
    cells = centres.cell_refs([it], "typo", 5)
    b = centres.Batch(5, cells, it.acts[5].float(), {"a": it}, context.ContextStore(tmp_path / "c.pt"))
    assert torch.allclose(centres.apply(c, b), acts[4] - acts[0:4].mean(0))


def test_bank_lock_serialises_and_breaks_stale_locks(tmp_path):
    import os
    import sys
    import threading
    import time

    sys.path.insert(0, str(__import__("jlm").REPO_ROOT / "experiments"))
    from evaluate import bank_lock

    inside, worst = [0], [0]

    def work():
        with bank_lock(tmp_path):
            inside[0] += 1
            worst[0] = max(worst[0], inside[0])
            time.sleep(0.05)
            inside[0] -= 1

    ts = [threading.Thread(target=work) for _ in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert worst[0] == 1 and not (tmp_path / ".summary.lock").exists()
    (tmp_path / ".summary.lock").mkdir()
    os.utime(tmp_path / ".summary.lock", (0, 0))  # left by a dead process long ago
    with bank_lock(tmp_path, stale_s=60):
        pass


def test_arm_names_with_colons_parse_as_centres_not_lenses():
    import sys

    sys.path.insert(0, str(__import__("jlm").REPO_ROOT / "experiments"))
    sys.path.insert(0, str(__import__("jlm").REPO_ROOT / "dashboard"))
    import catalog
    from evaluate import parse_arm, slug

    for name, centre, ref, lens in [("genk:8@self|rms", "genk:8", "self", "jlens"),
                                    ("dict:fam:0.5@fit|rms", "dict:fam:0.5", "fit", "jlens"),
                                    ("jpp:zero|cos", "zero", "self", "jpp"),
                                    ("jpp:glos:word@self|rms", "glos:word", "self", "jpp")]:
        a = parse_arm(name)
        assert (a.centre, a.ref, a.lens) == (centre, ref, lens)
        c = catalog.parse(catalog.from_dir(slug(a)))
        assert (c.centre, c.lens) == (centre, lens)


def test_parametric_names_reach_their_factory(monkeypatch):
    class Scaled(centres.Zero):
        def __init__(self, k: int) -> None:
            self.k, self.name = k, f"scaled:{k}"

    monkeypatch.setitem(centres.PARAMETRIC, "scaled", lambda rest: Scaled(int(rest)))
    assert centres.make("scaled:8").k == 8  # not a CENTRES key: the head's factory gets the arguments
    assert centres.make("shuf.scaled:3").inner.k == 3  # control prefixes wrap parametric centres too
    assert centres.make("fam").name == "fam"


def test_logit_lens_reads_the_state_without_a_map():
    from jlm import lens as jl

    lz = jl.Lens.__new__(jl.Lens)  # no downloads: a 3-token vocabulary over a 2-d state
    lz.name, lz.identity, lz.device, lz.layers, lz.jac = "logit", True, "cpu", [5], {}
    lz.w_u = torch.tensor([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
    lz.gain = torch.ones(2)
    lz.denom = {5: lz.w_u.norm(dim=1)}
    x = torch.tensor([[3.0, 4.0]])
    assert torch.allclose(lz.scores(x, 5, "cos"), (x @ lz.w_u.T) / lz.w_u.norm(dim=1))
    z = x / torch.sqrt(x.square().mean(dim=1, keepdim=True) + jl.RMS_EPS)
    assert torch.allclose(lz.scores(x, 5, "rms"), z @ lz.w_u.T)
    assert "logit" in jl.LENSES and "logit" in jl.IDENTITY


def test_a_local_map_reads_like_a_released_one(tmp_path, monkeypatch):
    from jlm import lens as jl

    J = {5: torch.tensor([[0.0, 1.0], [1.0, 0.0]])}
    torch.save({"J": J}, tmp_path / "swap.pt")
    found = jl.local_maps(tmp_path)
    assert found == {"swap": (None, str(tmp_path / "swap.pt"))}
    monkeypatch.setitem(jl.LENSES, "swap", found["swap"])
    assert torch.equal(jl.load_maps("swap", [5])[5], J[5])
    what, rev = jl.reader("swap")
    assert what.endswith("swap.pt") and rev.startswith("sha256:") and len(rev) == 23
    assert jl.reader("jlens") == (f"{jl.LENS_REPO}/{jl.LENS_FILE}", jl.PINS[jl.LENS_REPO])


def test_forms_sidecar_refills_a_summary_an_older_branch_stripped(tmp_path):
    full = {"scored_ids": ["a", "b"], "forms": {"n_scored": 2}, "n_reachable": 1,
            "arms": {"zero|rms": {"strict": 1, "forms": {"strict": 0.5}, "strict_reachable": {"value": 1.0}},
                     "fam@fit|rms": {"strict": 2, "forms": {"strict": 0.75}}},
            "diffs_forms": {"fam@fit|rms - zero|rms": {"diff": 0.25}}}
    forms.write_sidecar(tmp_path, full)
    stripped = {"scored_ids": ["a", "b"], "arms": {"zero|rms": {"strict": 1}, "fam@fit|rms": {"strict": 2},
                                                   "new@fit|rms": {"strict": 3}}}
    r = forms.fill_from_sidecar(tmp_path, stripped)
    assert r["forms"] == {"n_scored": 2} and r["n_reachable"] == 1
    assert r["arms"]["zero|rms"]["forms"] == {"strict": 0.5} and r["arms"]["zero|rms"]["strict_reachable"] == {"value": 1.0}
    assert "forms" not in r["arms"]["new@fit|rms"]  # read after the sidecar: none until a rescore
    assert list(r["diffs_forms"]) == ["fam@fit|rms - zero|rms"]
    forms.write_sidecar(tmp_path, {**r, "arms": {"zero|rms": r["arms"]["zero|rms"]}})  # a later run on one arm
    assert set(json.loads((tmp_path / forms.SIDECAR).read_text())["arms"]) == {"zero|rms", "fam@fit|rms"}  # kept
    other = {"scored_ids": ["a", "c"], "arms": {"zero|rms": {"strict": 1}}}
    assert "forms" not in forms.fill_from_sidecar(tmp_path, other)  # the bank changed: not filled


def test_held_out_split_paths():
    from jlm import banks

    assert banks.path_of("typo", "val2") == banks.DEV_ROOT / "typo" / "val2.json"
    assert "val2" not in banks.SPLITS  # loops over SPLITS must not meet a split most families lack
    import pytest

    with pytest.raises(ValueError):
        banks.path_of("typo", "val9")


def test_not_pooled_families_stay_out_of_pools():
    from jlm import banks

    fams = banks.dev_families()
    assert "typo" in fams and not set(fams) & set(banks.NOT_POOLED)  # poetry (J++ items) never joins fitall & co.
    if banks.path_of("poetry", "val").exists():
        assert {it["source"] for it in banks.load("poetry", "val").items} == {"jpp"}
