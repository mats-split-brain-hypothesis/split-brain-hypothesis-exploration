"""S2 neutral-context mean (notes/iteration-anthony/studies/S2.md).

``neu``: g = the mean, at the layer, of the read cells of the family's hand-authored **neutral** fills
(``data/dev/<family>/s2.json``, condition "neutral"; captured to ``out/captures/<family>-s2.pt``): the family's template
with content that does not share what the family's items share (S6 / S10). ``neuc``: the same over the "matched" fills
(multihop_mt only: famous people / works, the family's own category), the negative control that should reproduce fam's
harm. A family without an S2 bank (or without that condition) falls back to the family mean (``n_fallback``). The fills
are never read items, so no exclusion is needed.
"""

import torch

from jlm import REPO_ROOT, capture
from jlm.centres import CENTRES, CellRef, FamilyMean

OWNER = "Anthony"  # dashboard pickers list these centres under "Anthony's centres" (catalog.owner)


def fill_states(family: str, condition: str) -> dict[int, torch.Tensor] | None:
    """layer -> [d] mean over the family's S2 fills of ``condition``, or None when there are none."""
    from wsbench.banks import load_bank

    from jlm.banks import Bank

    path = REPO_ROOT / "data" / "dev" / family / "s2.json"
    if not path.exists():
        return None
    header, items = load_bank(path)
    keep = {it["id"] for it in items if it.get("condition") == condition}
    if not keep:
        return None
    caps = [c for c in capture.load(Bank(family, "s2", path, header, items)) if c.id in keep]
    return {L: torch.stack([c.acts[L][i].float() for c in caps for i in range(len(c.positions))]).double().mean(0).float()
            for L in caps[0].acts}


class NeutralMean:
    def __init__(self, condition: str) -> None:
        self.condition = condition
        self.name = {"neutral": "neu", "matched": "neuc"}[condition]
        self.doc = f"mean of the family's hand-authored S2 fills ({condition}), else fam"
        self.n_fallback = 0

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.mu = fill_states(family, self.condition)
        self.fam = FamilyMean()
        self.fam.fit(ref, family, groups)
        self.n_fallback = 0

    def __call__(self, cell: CellRef) -> torch.Tensor:
        if self.mu is None or cell.layer not in self.mu:
            self.n_fallback += 1
            return self.fam(cell)
        return self.mu[cell.layer]

    def support(self, cell) -> tuple[int, bool]:
        return (self.fam.support(cell)[0], True) if self.mu is None else (24, False)


CENTRES["neu"] = lambda: NeutralMean("neutral")
CENTRES["neuc"] = lambda: NeutralMean("matched")
