"""S25's centre adds alpha times the stored direction to the base's read state."""

import torch
from umot.capture import ItemCapture

from jlm import centres
from jlm.mu import S25


def test_answer_position_shift(monkeypatch):
    g = torch.Generator().manual_seed(0)
    items = [ItemCapture(id=f"i{j}", ids=[0, 1], decoded=["x", "t"], positions=[-1], idx=[1],
                         acts={5: torch.randn(1, 3, generator=g)}) for j in range(3)]
    monkeypatch.setattr(S25, "_DIRS", {"cap": {5: torch.tensor([1.0, 0, 2])}})
    c, fam = centres.make("s25on:2:cap:fam"), centres.make("fam")
    c.fit(items, "typo")
    fam.fit(items, "typo")
    cells = centres.cell_refs(items, "typo", 5)
    b = centres.Batch(5, cells, torch.cat([it.acts[5] for it in items]).float(), {it.id: it for it in items})
    assert torch.allclose(centres.apply(c, b), centres.apply(fam, b) + 2 * torch.tensor([1.0, 0, 2]))
    assert centres.make("sched:40:s25on:1:cap:kmx64+s14t64").name == "sched:40:s25on:1:cap:kmx64+s14t64"
