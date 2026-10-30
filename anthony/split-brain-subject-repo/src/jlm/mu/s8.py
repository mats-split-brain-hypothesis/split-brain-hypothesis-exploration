"""Study S8: the tightness of the match as a dial (notes/iteration-anthony/studies/S8.md).

U1 found that matching position (``u1rel``) is selective in umot's mention control while adding the read token
(``u1reltok``, ``tok``, ``u1carpos``) lets the prompt's mentioned word through: carrier words are rare, so "same token"
is close to "same sentence". S8 makes the step from one to the other continuous:

* ``s8lam<p>``: ``g = mu_rel + (p / 100) (mu_reltok - mu_rel)``, p in {0, 25, 50, 75, 100}. p = 0 is ``u1rel``; p = 100
  is the raw same-offset same-token mean (no ``min_cells`` fallback; ``mu_rel`` where no such cell exists).
* ``s8eb<k>``: empirical-Bayes shrinkage of the tight mean toward the coarse one by its support,
  ``g = (n mu_reltok + k mu_rel) / (n + k)`` with n the number of same-offset same-token reference cells, k in
  {1, 3, 10, 30}: a sparse key (a rare carrier word, the case that reads the prompt) is pulled to the position mean,
  a well-supported one (template tokens, "." at the end) keeps its own.

The dial is chosen on fit; the mention control is reported along the whole dial.
"""

import torch

from jlm.centres import CENTRES, Batch, CellRef, cell_refs
from jlm.mu.u1 import RelMean, RelTokMean, _set_items

OWNER = "Anthony"  # dashboard pickers list these centres under "Anthony's centres" (catalog.owner)


def keyed_sum(c, cell: CellRef) -> tuple:
    """(sum, n) of a fitted ``KeyedMean``'s reference cells for this cell's key, own group excluded."""
    k = (cell.layer, c.key(cell))
    s, n = c.s.get(k, 0.0), c.n.get(k, 0)
    if (*k, cell.group) in c.own:
        o = c.own[(*k, cell.group)]
        s, n = s - o[0], n - o[1]
    return s, n


class Dial:
    def __init__(self, name: str, doc: str, weight) -> None:
        """``weight(n) -> w``: the share of the tight (same-token) mean given its n reference cells."""
        self.name, self.doc, self.weight = name, doc, weight
        self.rel, self.rt = RelMean(), RelTokMean()
        self.n_fallback = 0

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.rel.fit(ref, family, groups)
        self.rt.fit(ref, family, groups)

    def __call__(self, cell: CellRef) -> torch.Tensor:
        mu_rel = self.rel(cell)
        s, n = keyed_sum(self.rt, cell)
        if n == 0:
            self.n_fallback += 1
            return mu_rel
        w = self.weight(n)
        return (1 - w) * mu_rel + w * (s / n).float()

    def transform(self, batch: Batch) -> torch.Tensor:
        _set_items(self.rel, batch.items)
        _set_items(self.rt, batch.items)
        return batch.H - torch.stack([self(c) for c in batch.cells])

    def support(self, cell: CellRef) -> tuple[int, bool]:
        n = keyed_sum(self.rt, cell)[1]
        return (n, False) if n else (self.rel.support(cell)[0], True)


def _lam(p: int):
    return lambda: Dial(f"s8lam{p}", f"mu_rel + {p / 100:g} (mu_reltok - mu_rel) (raw same-offset same-token mean)",
                        lambda n: p / 100)


def _eb(k: int):
    return lambda: Dial(f"s8eb{k}", f"(n mu_reltok + {k} mu_rel) / (n + {k}), n = same-offset same-token cells",
                        lambda n: n / (n + k))


for _p in (0, 25, 50, 75, 100):
    CENTRES[f"s8lam{_p}"] = _lam(_p)
for _k in (1, 3, 10, 30):
    CENTRES[f"s8eb{_k}"] = _eb(_k)


class RelKnn:
    """S8 part 2: neighbours in h-space inside the position key. g = the mean of the k reference cells at the same
    offset from the end of their read span whose states are nearest (cosine) to this cell's h, own group excluded;
    ``xs``: neighbours only from items with another sentence (read-span text; the whole render for one-cell items),
    the guard against same-sentence reading (U1 insight 2). Fewer than k candidates: all of them; none: ``u1rel``."""

    def __init__(self, k: int, xs: bool) -> None:
        self.k, self.xs = k, xs
        self.name = f"s8knn{k}{'xs' if xs else ''}"
        self.doc = (f"mean of the {k} nearest (cosine) reference cells at the same offset from the span's end"
                    f"{', other sentences only' if xs else ''} (own group excluded; else u1rel)")
        self.rel = RelMean()
        self.n_fallback = 0

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.rel.fit(ref, family, groups)
        groups = groups or {}
        rows: dict = {}  # (layer, rel key) -> [states], [groups], [sentences]
        for it in ref:
            for L, acts in it.acts.items():
                for c in cell_refs([it], family, L, groups):
                    r = rows.setdefault((L, self.rel.key(c)), ([], [], []))
                    r[0].append(acts[c.i].float())
                    r[1].append(c.group)
                    r[2].append(self.rel.sentence(c))
        self.bank = {k: (torch.stack(h), torch.nn.functional.normalize(torch.stack(h), dim=1), g, s)
                     for k, (h, g, s) in rows.items()}

    def transform(self, batch: Batch) -> torch.Tensor:
        _set_items(self.rel, batch.items)
        G = torch.empty_like(batch.H)
        Hn = torch.nn.functional.normalize(batch.H, dim=1)
        for j, c in enumerate(batch.cells):
            b = self.bank.get((batch.layer, self.rel.key(c)))
            ok = None
            if b is not None:
                sent = self.rel.sentence(c) if self.xs else None
                ok = [n for n, (g, s) in enumerate(zip(b[2], b[3])) if g != c.group and (not self.xs or s != sent)]
            if not ok:
                self.n_fallback += 1
                G[j] = self.rel(c)
                continue
            sims = b[1][ok] @ Hn[j]
            top = sims.topk(min(self.k, len(ok))).indices
            G[j] = b[0][ok][top].mean(0)
        return batch.H - G

    def support(self, cell) -> tuple[int, bool]:
        return self.k, False


for _k in (4, 8, 16, 32):
    for _xs in (False, True):
        CENTRES[f"s8knn{_k}{'xs' if _xs else ''}"] = (lambda k, xs: lambda: RelKnn(k, xs))(_k, _xs)
