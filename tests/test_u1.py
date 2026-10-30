"""Study U1's position-matched centres (jlm.mu.u1)."""

import torch
from umot.capture import ItemCapture

from jlm import centres, context


def item(iid, toks, n_read, vals):
    """An item whose last ``n_read`` tokens are read; vals[j] is the (1-d padded to 2-d) state at read cell j."""
    T = len(toks)
    return ItemCapture(id=iid, ids=list(range(T)), decoded=toks, positions=list(range(T - n_read, T)),
                       idx=list(range(T - n_read, T)), acts={5: torch.tensor([[v, 0.0] for v in vals])})


ITEMS = [  # read spans: a, b share the sentence "x y ."; c is "z y ." with an extra leading token
    item("a", ["p", "x", " y", "."], 3, [1.0, 2.0, 3.0]),
    item("b", ["q", "x", " y", "."], 3, [5.0, 6.0, 7.0]),
    item("c", ["r", "s", "z", " y", "."], 3, [10.0, 20.0, 30.0]),
    item("d", ["t", "x", " y", "."], 3, [100.0, 200.0, 300.0]),
]


def apply(name, items, ref=None, ctx=None, groups=None):
    c = centres.make(name)
    c.fit(ref or items, "user_modeling", groups, ctx=ctx)
    cells = centres.cell_refs(items, "user_modeling", 5, groups)
    H = torch.stack([it.acts[5][cl.i] for it in items for cl in centres.cell_refs([it], "user_modeling", 5)])
    G = H - centres.apply(c, centres.Batch(5, cells, H, {it.id: it for it in items}, ctx))
    return {(cl.item, cl.i): g[0].item() for cl, g in zip(cells, G)}


def test_rel_matches_offset_from_the_span_end_and_excludes_own_item():
    g = apply("u1rel", ITEMS)
    assert abs(g[("a", 2)] - (7.0 + 30.0 + 300.0) / 3) < 1e-4  # the other items' last read cells
    assert abs(g[("c", 0)] - (1.0 + 5.0 + 100.0) / 3) < 1e-4  # first cells of a, b, d


def test_single_cell_rungs_reduce_to_the_family_mean():
    one = [item(i, ["w", t], 1, [v]) for i, t, v in [("a", " is", 1.0), ("b", " of", 2.0), ("c", " is", 6.0),
                                                    ("d", " of", 9.0)]]
    fam = apply("fam", one)
    for name in ("u1rel", "u1slot", "u1carpos"):  # carpos: < 2 same-span cells -> reltok -> tok -> fam
        assert apply(name, one) == fam, name


def test_carpos_uses_items_with_the_same_span_text():
    g = apply("u1carpos", ITEMS)
    assert g[("a", 1)] == (6.0 + 200.0) / 2  # b and d share "x y ."; c does not
    assert g[("c", 1)] == apply("u1reltok", ITEMS)[("c", 1)]  # c's sentence is unique: falls back


def test_group_members_never_centre_each_other_in_carpos():
    g = apply("u1carpos", ITEMS, groups={"a": "ab", "b": "ab", "c": "c", "d": "d"})
    assert g[("a", 1)] != (6.0 + 200.0) / 2  # only d is left (< 2 cells): fallback, not b and d


def test_relx_is_position_matched_but_token_mismatched():
    its = ITEMS + [item("e", ["u", "k", " w", "!"], 3, [1000.0, 2000.0, 3000.0])]
    g = apply("u1relx", its)
    # a's last cell is "."; same offset with another token: only e's "!" (< 3 cells) -> family mean
    fam = apply("fam", its)
    assert g[("a", 2)] == fam[("a", 2)]
    its += [item(f"f{k}", ["u", "k", " w", "?"], 3, [0.0, 0.0, float(k)]) for k in range(3)]
    g = apply("u1relx", its)
    assert g[("a", 2)] == (3000.0 + 0 + 1 + 2) / 4


def test_position_mean_reads_every_position_of_the_other_renders(tmp_path):
    rows = []
    for it in ITEMS:
        T = len(it.ids)
        acts = torch.tensor([[float(10 * t + ord(it.id[0])), 0.0] for t in range(T)]).bfloat16()
        rows.append(vars(context.CtxItem(it.id, it.ids, it.decoded, it.idx, {5: acts})))
    torch.save(rows, tmp_path / "c.pt")
    ctx = context.ContextStore(tmp_path / "c.pt")
    g = apply("u1pos", ITEMS, ctx=ctx)
    # a's last cell is at t = 3: b, c, d all have a state at t = 3
    want = sum(float(ctx.states(i, 5)[3, 0]) for i in "bcd") / 3
    assert abs(g[("a", 2)] - want) < 1e-4
    g = apply("u1tokany", ITEMS, ctx=ctx)
    want = sum(float(ctx.states(i, 5)[len(ctx.items[i].ids) - 1, 0]) for i in "bcd") / 3  # the other "." tokens
    assert abs(g[("a", 2)] - want) < 1e-4


def test_wiki_position_mean(tmp_path):
    from jlm.mu import u1

    rows = [vars(context.CtxItem(f"w{k}", [0] * 6, ["x"] * 6, [], {5: torch.full((6, 2), float(k)).bfloat16()}))
            for k in range(3)]
    torch.save(rows, tmp_path / "w.pt")
    u1._WIKI.clear()
    c = u1.WikiPosMean(tmp_path / "w.pt")
    c.fit(ITEMS, "user_modeling")
    cell = centres.cell_refs(ITEMS[:1], "user_modeling", 5)[0]
    assert c(cell).tolist() == [1.0, 1.0]
    u1._WIKI.clear()


def test_s8_dial_ends_are_rel_and_raw_reltok():
    rel, lam0, lam100 = apply("u1rel", ITEMS), apply("s8lam0", ITEMS), apply("s8lam100", ITEMS)
    assert lam0 == rel
    # a's middle cell " y" at offset 1: same offset, same token in b, c, d (c's " y" is also at offset 1)
    assert abs(lam100[("a", 1)] - (6.0 + 20.0 + 200.0) / 3) < 1e-4
    half = apply("s8lam50", ITEMS)
    assert abs(half[("a", 1)] - (rel[("a", 1)] + lam100[("a", 1)]) / 2) < 1e-4


def test_s8_empirical_bayes_shrinks_sparse_keys_toward_position():
    its = ITEMS + [item("e", ["u", "k", " w", "!"], 3, [1000.0, 2000.0, 3000.0])]
    eb = apply("s8eb3", its)
    rel, raw = apply("u1rel", its), apply("s8lam100", its)
    # e's "!" has no same-offset same-token cell: the position mean
    assert eb[("e", 2)] == rel[("e", 2)]
    # a's "." has 3 (b, c, d): weight 3 / (3 + 3)
    assert abs(eb[("a", 2)] - (0.5 * rel[("a", 2)] + 0.5 * raw[("a", 2)])) < 1e-3


def test_token_mean_from_other_sentences_only():
    its = ITEMS + [item(f"o{k}", ["v", "k", " y", "."], 3, [0.0, float(k), 0.0]) for k in range(3)]
    g = apply("u1tokxs", its)
    # a's " y": same token in b, d (same sentence "x y ." -> excluded), c ("z y .") and o0-o2 ("k y .") -> 4 cells
    assert abs(g[("a", 1)] - (20.0 + 0 + 1 + 2) / 4) < 1e-4
    # c's " y" (sentence "z y ."): a, b, d, o0-o2 all differ from c's sentence -> 6 cells
    assert abs(g[("c", 1)] - (2.0 + 6.0 + 200.0 + 0 + 1 + 2) / 6) < 1e-4
    rel = apply("u1rel", ITEMS)
    assert apply("u1tokxs", ITEMS)[("a", 1)] == rel[("a", 1)]  # only c is another sentence (< 3): u1rel


def test_token_mean_from_other_sentences_is_tok_on_single_cell_items():
    one = [item(i, [p, t], 1, [v]) for i, p, t, v in [("a", "w", " is", 1.0), ("b", "x", " is", 2.0),
                                                     ("c", "y", " is", 6.0), ("d", "z", " is", 9.0)]]
    assert apply("u1tokxs", one) == apply("tok", one)


def test_s8_knn_takes_the_nearest_same_offset_cells():
    its = [ItemCapture(id=i, ids=[0, 1], decoded=["p", t], positions=[1], idx=[1], acts={5: torch.tensor([v])})
           for i, t, v in [("a", "x", [1.0, 0.0]), ("b", "y", [0.9, 0.1]), ("c", "z", [0.0, 1.0]), ("d", "w", [1.0, 0.05])]]
    g = apply("s8knn4", its)  # k larger than the pool: every other cell (= u1rel = fam here)
    assert abs(g[("a", 0)] - (0.9 + 0.0 + 1.0) / 3) < 1e-5
    c = centres.make("s8knn4")
    c.k = 2
    c.fit(its, "typo")
    cells = centres.cell_refs(its, "typo", 5)
    H = torch.stack([it.acts[5][0] for it in its])
    G = H - c.transform(centres.Batch(5, cells, H, {it.id: it for it in its}))
    assert torch.allclose(G[0], (its[1].acts[5][0] + its[3].acts[5][0]) / 2)  # a's two nearest: b and d


def test_endcar_is_carpos_at_the_last_cell_and_rel_elsewhere():
    end, car, rel = apply("u1endcar", ITEMS), apply("u1carpos", ITEMS), apply("u1rel", ITEMS)
    assert end[("a", 2)] == car[("a", 2)] and end[("a", 1)] == rel[("a", 1)] and end[("a", 0)] == rel[("a", 0)]


def test_n_scaling_uses_only_n_reference_groups():
    c = centres.make("u1rel4")
    c.n_groups = 2
    c.fit(ITEMS, "user_modeling")
    assert len({k[-1] for k in c.own}) == 2  # own-group sums exist only for the 2 kept groups


def test_s5_word_direction_moves_g_along_the_unit_word_direction(tmp_path):
    from jlm.mu import s5

    rows = []
    for w, v in [("typo", [3.0, 0.0]), ("misspelling", [3.0, 0.0])] + [(n, [1.0, 0.0]) for n in s5.NEUTRAL]:
        for k in range(3):
            rows.append(vars(context.CtxItem(f"{w}|{k}", [0, 1], ["a", w], [], {5: torch.tensor([[0.0, 0.0], v]).bfloat16()})))
    torch.save(rows, tmp_path / "w.pt")
    s5.word_states.cache_clear()
    c = s5.WordDirection("cat", "p30", tmp_path / "w.pt")
    one = [item(i, ["w", t], 1, [v]) for i, t, v in [("a", "x", 0.0), ("b", "y", 2.0)]]
    for it in one:
        it.acts = {5: torch.tensor([[it.acts[5][0][0].item(), 1.0]])}
    c.fit(one, "typo")
    cells = centres.cell_refs(one, "typo", 5)
    H = torch.stack([it.acts[5][0] for it in one])
    G = H - c.transform(centres.Batch(5, cells, H, {it.id: it for it in one}))
    fam = torch.tensor([2.0, 1.0])  # a's family mean = b's state
    r = (H[0] - fam).norm()
    assert torch.allclose(G[0], fam + 0.30 * r * torch.tensor([1.0, 0.0]))
    s5.word_states.cache_clear()
