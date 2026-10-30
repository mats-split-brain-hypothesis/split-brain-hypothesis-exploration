"""The mention-only control bank and the concept-exclusion rule of umot.centring."""

from collections import Counter

import torch

from umot import mention_control as mc
from umot.capture import ItemCapture
from umot.centring import Centre


def test_bank_shape_and_prompts():
    items = mc.build()
    assert len(items) == 315
    assert Counter(i["condition"] for i in items) == {"hold": 105, "mention": 105, "holdmention": 70, "absent": 35}
    for it in items:
        assert it["prompt"].endswith(mc.COPY.format(carrier=it["carrier"]))
        first = it["prompt"].removesuffix(mc.COPY.format(carrier=it["carrier"]))
        for c in (it["held"], it["mentioned"]):
            if c:
                assert c in first
        if it["condition"] == "absent":
            assert first == ""
        if it["condition"] == "holdmention":
            assert it["held"] != it["mentioned"]
    assert items == mc.load()  # the committed bank is what the builder produces


def test_specs_reuse_bench_render_and_positions():
    items = mc.load()[:9]
    specs = mc.specs(items)
    assert [s.id for s in specs] == [i["id"] for i in items]
    assert all(s.render == "chat_dm" and s.positions["text"] == i["assistant"] for s, i in zip(specs, items))


def test_centre_excludes_items_sharing_a_concept():
    def item(name, v):
        return ItemCapture(id=name, ids=[], decoded=[], positions=[0], idx=[0], acts={0: torch.tensor([[v]])})

    a, b, c = item("a", 1.0), item("b", 10.0), item("c", 100.0)
    concepts = {"a": frozenset({"x", "y"}), "b": frozenset({"y"}), "c": frozenset({"z"})}
    centre = Centre([a, b, c], lambda it, i: "k", lambda it: concepts[it.id])
    assert centre(a, 0, 0).item() == 100.0  # b shares y with a: excluded with a itself
    assert centre(c, 0, 0).item() == 5.5  # c shares nothing: mean of a and b


def test_many_bank():
    items = mc.build_many()
    assert len(items) == 140
    assert Counter(i["condition"] for i in items) == {"listhold": 35, "holdlist": 35, "listnone": 35, "listrefer": 35}
    for it in items:
        first = it["prompt"].removesuffix(" " + mc.COPY.format(carrier=it["carrier"]))
        assert all(f" {c}" in first for c in it["listed"])
        n_listed = 4 if it["condition"] in ("listhold", "holdlist") else 5
        assert len(it["listed"]) == n_listed and len(set(it["listed"])) == n_listed
        if it["condition"] in ("listhold", "holdlist"):
            assert it["held"] not in it["listed"]
        assert (it["held"] is None) == (it["condition"] == "listnone")
        assert mc.concepts_of(it) == frozenset([it["concept"], *it["listed"]])
    assert items == mc.load(mc.FAMILY_MANY)
