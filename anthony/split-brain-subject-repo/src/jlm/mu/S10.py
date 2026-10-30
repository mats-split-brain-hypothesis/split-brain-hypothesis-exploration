"""S10 mechanism test: a family mean restricted to the read item's prompt language, or to every other language
(studies/S10.md). Uses the bank's ``lang`` item field (metadata of the prompt, never a target); a test of why matched
centres lose multilingual_mt's language unit, not a candidate centre.

- ``samelang``: mean over the family's reference cells whose item has the same ``lang`` (own group excluded), else fam.
- ``otherlang``: mean over the family's reference cells whose item has a different ``lang``.
"""

from collections.abc import Hashable

import torch

from jlm import banks
from jlm.centres import CENTRES, CellRef, FamilyMean, KeyedMean

OWNER = "Anthony"  # dashboard pickers list these centres under "Anthony's centres" (catalog.owner)


_LANG: dict[str, str] = {}


def lang_of(family: str, item: str) -> str:
    if not _LANG.get(f"{family}\0loaded"):
        for split in ("fit", "val", "bench"):
            try:
                for it in banks.load(family, split).items:
                    _LANG[it["id"]] = it.get("lang", "")
            except (FileNotFoundError, ValueError):
                pass
        _LANG[f"{family}\0loaded"] = "1"
    return _LANG.get(item, "")


class SameLanguage(KeyedMean):
    def __init__(self) -> None:
        super().__init__("samelang", "mean over reference cells whose prompt has the same language (else fam)",
                         min_cells=3, fallback=FamilyMean())

    def key(self, cell: CellRef) -> Hashable:
        return (cell.family, lang_of(cell.family, cell.item))


class OtherLanguages:
    name, doc = "otherlang", "mean over reference cells whose prompt is in another language"

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.same, self.fam = SameLanguage(), FamilyMean()
        self.same.fit(ref, family, groups)
        self.fam.fit(ref, family, groups)
        self.n_fallback = 0

    def __call__(self, cell: CellRef) -> torch.Tensor:
        """(n_fam mu_fam - n_same mu_same) / (n_fam - n_same), both leaving out the cell's own group."""
        nf, _ = self.fam.support(cell)
        ns, fell = self.same.support(cell)
        if fell or ns == 0:
            return self.fam(cell)
        return (nf * self.fam(cell) - ns * self.same(cell)) / (nf - ns)

    def support(self, cell) -> tuple[int, bool]:
        return self.fam.support(cell)[0] - self.same.support(cell)[0], False


CENTRES["samelang"] = SameLanguage
CENTRES["otherlang"] = OtherLanguages
