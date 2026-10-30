"""S6 causal test: a family mean without the family's shared category (notes/iteration-anthony/studies/S6.md).

S6 finding 2: on multihop_mt the family mean holds the bridge's category ("a famous author / composer"), so
subtracting it pushes the bridge down. If that is the mechanism, a mean of cells with the same form but another
category should remove the template prior and spare the bridge.

- ``mhfam``: g = the mean of multihop's **fit** read cells at the layer (country / capital questions, "Fact: The
  capital of ... is"), whatever family is read. Read on multihop itself it is fam@fit.
- ``othfam``: g = the average of the 10 other families' fit means at the layer (each family weighted equally):
  a generic bench-cell mean without the read family's own content (jle's ctr1).

Both are fitted on fit banks only, so on val they see no val item; on multihop/fit, ``mhfam`` excludes the read
cell's own group as ``fam`` does.
"""

import torch

from jlm import banks, capture
from jlm.centres import CENTRES, CellRef, FamilyMean, cell_refs

OWNER = "Anthony"  # dashboard pickers list these centres under "Anthony's centres" (catalog.owner)


FAMILIES = ["typo", "association", "basic_readout", "multihop", "multilingual", "user_modeling", "directed_modulation",
            "typo_mt", "multihop_mt", "basic_readout_mt", "multilingual_mt"]


def _fit_mean(family: str, groups=None) -> FamilyMean:
    m = FamilyMean()
    m.fit(capture.load(banks.load(family, "fit")), family, groups)
    return m


class SourceFamilyMean:
    def __init__(self, source: str) -> None:
        self.source = source
        self.name = {"multihop": "mhfam"}[source]
        self.doc = f"the {source} fit bank's family mean, whatever family is read"
        self.n_fallback = 0

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.m = _fit_mean(self.source, groups)

    def __call__(self, cell: CellRef) -> torch.Tensor:
        from dataclasses import replace

        return self.m(replace(cell, family=self.source))

    def support(self, cell) -> tuple[int, bool]:
        from dataclasses import replace

        return self.m.support(replace(cell, family=self.source))


class OtherFamilies:
    name, doc = "othfam", "the mean of the other 10 families' fit means (each family weighted equally)"

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.family, self.n_fallback = family, 0
        self.means = {f: _fit_mean(f) for f in FAMILIES if f != family}
        self._memo: dict[int, torch.Tensor] = {}

    def __call__(self, cell: CellRef) -> torch.Tensor:
        from dataclasses import replace

        if cell.layer not in self._memo:
            self._memo[cell.layer] = torch.stack(
                [m(replace(cell, family=f, group="\0none")) for f, m in self.means.items()]).mean(0)
        return self._memo[cell.layer]

    def support(self, cell) -> tuple[int, bool]:
        return len(self.means), False


CENTRES["mhfam"] = lambda: SourceFamilyMean("multihop")
CENTRES["othfam"] = OtherFamilies


class PredictionDeflation:
    """S6c ``pdf``: g = mu_fam + (x . u) u with x = h - mu_fam and u the unit direction of the cell's own **final-layer**
    state, centred on the family's final-layer mean (own group excluded): remove what the model is about to say.

    S6 finding 5: on multihop, centres that lift the scored bridge do it by pushing the final answer (the model's next
    words) down. The final block's state (layer 63) is what the model's next-token logits read; its direction, centred,
    is the cell-specific part of that prediction. Needs the context capture (final layer at the read cell); never a
    target. Control: the next-token baseline (this centre removes it by construction)."""

    needs_ctx = True
    name, doc = "pdf", "family mean plus the projection on the cell's centred final-layer state removed"

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        from collections import defaultdict

        from jlm.context import FINAL_LAYER

        assert ctx is not None, "pdf needs a context capture (out/ctx)"
        self.fam = FamilyMean()
        self.fam.fit(ref, family, groups)
        self.s, self.n = 0.0, 0
        self.own: dict = defaultdict(lambda: [0.0, 0])
        for it in ref:
            for c in cell_refs([it], family, FINAL_LAYER, groups):
                h = ctx.at(it.id, FINAL_LAYER, c.i).double()
                self.s, self.n = self.s + h, self.n + 1
                o = self.own[c.group]
                o[0], o[1] = o[0] + h, o[1] + 1
        self.n_fallback = 0

    def _mu_final(self, group: str) -> torch.Tensor:
        o = self.own.get(group, (0.0, 0))
        return ((self.s - o[0]) / (self.n - o[1])).float()

    def transform(self, batch) -> torch.Tensor:
        from jlm.context import FINAL_LAYER

        assert batch.ctx is not None, "pdf needs a context capture (out/ctx)"
        X = batch.H - torch.stack([self.fam(c) for c in batch.cells])
        U = torch.stack([batch.ctx.at(c.item, FINAL_LAYER, c.i).float() - self._mu_final(c.group) for c in batch.cells])
        U = U / U.norm(dim=1, keepdim=True).clamp_min(1e-6)
        return X - (X * U).sum(1, keepdim=True) * U

    def support(self, cell) -> tuple[int, bool]:
        return self.fam.support(cell)


CENTRES["pdf"] = PredictionDeflation
