"""S23's layer map applies each layer's own centre."""

import json

import torch
from umot.capture import ItemCapture

from jlm import centres
from jlm.mu import S23


def test_layer_map(tmp_path):
    p = tmp_path / "map.json"
    p.write_text(json.dumps({"5": "zero", "9": "fam"}))
    g = torch.Generator().manual_seed(0)
    items = [ItemCapture(id=f"i{j}", ids=[0, 1], decoded=["x", "t"], positions=[-1], idx=[1],
                         acts={L: torch.randn(1, 4, generator=g) for L in (5, 9)}) for j in range(4)]
    m, fam = S23.LayerMap("cos", p), centres.make("fam")
    m.fit(items, "typo")
    fam.fit(items, "typo")
    for L in (5, 9):
        cells = centres.cell_refs(items, "typo", L)
        b = centres.Batch(L, cells, torch.cat([it.acts[L] for it in items]).float(), {it.id: it for it in items})
        want = b.H if L == 5 else centres.apply(fam, b)
        assert torch.allclose(centres.apply(m, b), want)
