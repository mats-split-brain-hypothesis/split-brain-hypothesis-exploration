"""S12: same token, other content (notes/iteration-anthony/studies/S12.md).

S6 and S10: a mean over cells that share X removes X (the bridge's category; the prompt's language). The token mean
helps UM / DM because it shares the read token's identity (form), but its reference cells also share the family's
content and language. ``xtok``: g = the mean over every position of the **other** 10 families' fit renders (context
captures) whose token equals the read token, else the family mean. It keeps the token, drops this family's content.
B's ``u1tokany`` is the same key over the read family's own renders.
"""

from collections import defaultdict

import torch

from jlm import banks, capture
from jlm.centres import CENTRES, CellRef, FamilyMean
from jlm.context import ContextStore, bank_path

OWNER = "Anthony"  # dashboard pickers list these centres under "Anthony's centres" (catalog.owner)


FAMILIES = ["typo", "association", "basic_readout", "multihop", "multilingual", "user_modeling", "directed_modulation",
            "typo_mt", "multihop_mt", "basic_readout_mt", "multilingual_mt"]
_SUMS: dict = {}  # source family -> {(layer, token): [sum float64, n]}, for the tokens any family reads


def _read_tokens() -> set[str]:
    out: set[str] = set()
    for f in FAMILIES:
        for split in ("fit", "val"):
            for it in capture.load(banks.load(f, split)):
                out |= {it.token(i) for i in range(len(it.positions))}
    return out


def source_sums(layers: list[int]) -> dict:
    if not _SUMS:
        want = _read_tokens()
        for f in FAMILIES:
            store = ContextStore(bank_path(banks.load(f, "fit")))
            acc: dict = defaultdict(lambda: [0.0, 0])
            for row in store.items.values():
                ts = [t for t, tok in enumerate(row.decoded) if tok in want]
                for L in layers:
                    if L not in row.acts:
                        continue
                    A = row.acts[L]
                    for t in ts:
                        a = acc[(L, row.decoded[t])]
                        a[0], a[1] = a[0] + A[t].double(), a[1] + 1
            _SUMS[f] = dict(acc)
            del store
    return _SUMS


class OtherFamilyTokenMean:
    name = "xtok"
    doc = "mean over every occurrence of the read token in the other families' fit renders (>= 3, else fam)"

    def __init__(self, min_cells: int = 3) -> None:
        self.min_cells = min_cells

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.family, self.n_fallback = family, 0
        self.fam = FamilyMean()
        self.fam.fit(ref, family, groups)
        self.layers = sorted({L for it in ref for L in it.acts})
        self._memo: dict = {}

    def _sum(self, layer: int, token: str) -> tuple:
        if (layer, token) not in self._memo:
            s, n = 0.0, 0
            for f, sums in source_sums(self.layers).items():
                if f != self.family and (layer, token) in sums:
                    s, n = s + sums[(layer, token)][0], n + sums[(layer, token)][1]
            self._memo[(layer, token)] = (s, n)
        return self._memo[(layer, token)]

    def __call__(self, cell: CellRef) -> torch.Tensor:
        s, n = self._sum(cell.layer, cell.token)
        if n < self.min_cells:
            self.n_fallback += 1
            return self.fam(cell)
        return (s / n).float()

    def support(self, cell: CellRef) -> tuple[int, bool]:
        n = self._sum(cell.layer, cell.token)[1]
        return (self.fam.support(cell)[0], True) if n < self.min_cells else (n, False)


CENTRES["xtok"] = OtherFamilyTokenMean
