"""Depth-scheduled centres (card S17): one centre up to a layer, another above it.

``sched:<L>:<A>+<B>`` reads ``J_l (h - g_A)`` at layers ``l <= L`` and ``J_l (h - g_B)`` above. ``A`` and ``B`` are any
arm centre names (parametric ones included: they may contain ':' but not '+'); ``zero`` stops centring late
(``sched:48:fam+zero``). Both are fitted on the arm's reference set; the schedule itself has one hyperparameter, ``L``,
chosen on fit. The swapped schedule (``sched:<L>:<B>+<A>``) is the card's control.
"""

from jlm import centres
from jlm.centres import PARAMETRIC, Batch, CellRef


class Schedule:
    def __init__(self, split_layer: int, early: str, late: str) -> None:
        self.split_layer = split_layer
        self.early, self.late = centres.make(early), centres.make(late)
        self.name = f"sched:{split_layer}:{early}+{late}"
        self.doc = f"layers <= {split_layer}: {self.early.doc}; above: {self.late.doc}"
        self.needs_ctx = getattr(self.early, "needs_ctx", False) or getattr(self.late, "needs_ctx", False)
        self.n_fallback = 0

    def _at(self, layer: int):
        return self.early if layer <= self.split_layer else self.late

    def set_bank(self, family: str, items) -> None:
        for c in (self.early, self.late):
            if hasattr(c, "set_bank"):
                c.set_bank(family, items)

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        for c in (self.early, self.late):
            c.fit(ref, family, groups, ctx=ctx if getattr(c, "needs_ctx", False) else None)

    def transform(self, batch: Batch):
        return centres.apply(self._at(batch.layer), batch)

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return self._at(cell.layer).support(cell)


def make(args: str) -> Schedule:
    layer, _, rest = args.partition(":")
    early, plus, late = rest.partition("+")
    if not plus:
        raise ValueError(f"sched: expected '<L>:<A>+<B>', got {args!r}")
    return Schedule(int(layer), early, late)


PARAMETRIC["sched"] = make
