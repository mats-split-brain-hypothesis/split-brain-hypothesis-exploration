"""S23 per-layer centre selection (notes/iteration-anthony/mu-log.md, card S23).

``s23map:<readout>``: each grid layer read with the centre that ``experiments/s23_select.py`` chose for it on fit
(``out/analysis/S23/map-<readout>.json``: layer -> centre name, label-free centres only). Every component is fitted on the
arm's reference set, so the arm equals the per-layer mix of the components' own arms.
"""

import json

from jlm import OUT, centres
from jlm.centres import PARAMETRIC, Batch, CellRef

OWNER = "Anthony"
CANDIDATES = ()


class LayerMap:
    def __init__(self, readout: str, path=None) -> None:
        path = path or OUT / "analysis" / "S23" / f"map-{readout}.json"
        self.map = {int(L): c for L, c in json.loads(path.read_text()).items()}
        self.parts = {c: centres.make(c) for c in sorted(set(self.map.values()))}
        self.name = f"s23map:{readout}"
        self.doc = "per-layer centre chosen on fit: " + ", ".join(f"L{L} {c}" for L, c in sorted(self.map.items()))
        self.needs_ctx = any(getattr(c, "needs_ctx", False) for c in self.parts.values())
        self.n_fallback = 0

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        for c in self.parts.values():
            c.fit(ref, family, groups, ctx=ctx if getattr(c, "needs_ctx", False) else None)

    def transform(self, batch: Batch):
        return centres.apply(self.parts[self.map[batch.layer]], batch)

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return self.parts[self.map[cell.layer]].support(cell)


PARAMETRIC["s23map"] = lambda r: LayerMap(r)
