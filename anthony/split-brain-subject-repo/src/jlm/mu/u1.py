"""Study U1: position-based means, carefully (notes/iteration-anthony/studies/U1.md).

A ladder of keyed means, from position-only keys to "same sentence, same position". Every rung is a mean over
reference cells sharing a key, own item and its group excluded (``KeyedMean``), with a fallback below
``min_cells``. Keys that need the layout of the cell's item (where its read span ends, where the chat template
starts) read it from the item's capture (``ItemKeyed``); keys that need every position read the context capture.

| centre | key | fallback |
|---|---|---|
| ``u1pos`` | absolute position t, every position of the reference renders (context capture) | fam |
| ``u1poswiki`` | absolute position t, every position of the wikitext corpus (no bench content) | fam |
| ``u1rel`` | offset of the cell from the end of its item's read span | fam |
| ``u1slot`` | (segment, index from the segment's start); segments: body / chat template from ``<|im_end|>`` | fam |
| ``u1relx`` | control: same offset as ``u1rel`` but a *different* read token | fam |
| ``u1tokany`` | same token at any position of the reference renders (context capture) | fam |
| ``u1reltok`` | (offset from the span's end, read token) | tok |
| ``u1carpos`` | (the item's read-span text, index in it): same sentence, same position (umot's carpos) | u1reltok |

On the single-cell families (one read cell per item) ``u1rel``, ``u1slot`` and ``u1carpos`` reduce to ``fam`` /
``tok`` by construction (a sanity check), so the ladder's action is on user_modeling and directed_modulation.
"""

from collections import defaultdict
from collections.abc import Hashable

import torch

from jlm.centres import CENTRES, Batch, CellRef, FamilyMean, KeyedMean, TokenMean, cell_refs
from jlm.context import ContextStore, corpus_path

OWNER = "Anthony"  # dashboard pickers list these centres under "Anthony's centres" (catalog.owner)


TEMPLATE_START = "<|im_end|>"


def _set_items(c, items: dict) -> None:
    """Give a centre and its fallback chain the item captures their keys look up."""
    while c is not None:
        if isinstance(c, ItemKeyed):
            c.items_of = {**c.items_of, **items}
        c = getattr(c, "fallback", None)


class ItemKeyed(KeyedMean):
    """A ``KeyedMean`` whose key may look at the cell's item (its read cells, its render), not only the
    ``CellRef``. Read-time items come from the ``Batch``; the targets are not in either."""

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.items_of: dict = {}

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        _set_items(self, {it.id: it for it in ref})
        super().fit(ref, family, groups)

    def transform(self, batch: Batch) -> torch.Tensor:
        _set_items(self, batch.items)
        return batch.H - torch.stack([self(c) for c in batch.cells])

    def members(self, batch: Batch) -> list[torch.Tensor]:
        _set_items(self, batch.items)
        return super().members(batch)

    # layout helpers
    def rel(self, cell: CellRef) -> int:
        it = self.items_of[cell.item]
        return it.idx[-1] - it.idx[cell.i]

    def slot(self, cell: CellRef) -> tuple[str, int]:
        it = self.items_of[cell.item]
        toks = [it.decoded[t] for t in it.idx]
        j = toks.index(TEMPLATE_START) if TEMPLATE_START in toks else len(toks)
        return ("body", cell.i) if cell.i < j else ("tmpl", cell.i - j)

    def span(self, cell: CellRef) -> tuple[str, ...]:
        it = self.items_of[cell.item]
        return tuple(it.decoded[it.idx[0] : it.idx[-1] + 1])

    def sentence(self, cell: CellRef) -> tuple[str, ...]:
        """The text a cell is read within: its read span, or the whole render when the item has one read cell."""
        it = self.items_of[cell.item]
        return self.span(cell) if len(it.idx) > 1 else tuple(it.decoded)


class RelMean(ItemKeyed):
    def __init__(self) -> None:
        super().__init__("u1rel", "mean over reference cells at the same offset from the end of their read span "
                         "(>= 3 cells, else fam)", min_cells=3, fallback=FamilyMean())

    def key(self, cell):
        return (cell.family, self.rel(cell))


class SlotMean(ItemKeyed):
    def __init__(self) -> None:
        super().__init__("u1slot", "mean over reference cells in the same template slot (body index from the start "
                         "of the read span, chat-template index from <|im_end|>; >= 3 cells, else fam)",
                         min_cells=3, fallback=FamilyMean())

    def key(self, cell):
        return (cell.family, self.slot(cell))


class RelTokMean(ItemKeyed):
    def __init__(self) -> None:
        super().__init__("u1reltok", "mean over reference cells with the same read token at the same offset from "
                         "the end of the read span (>= 3 cells, else tok)", min_cells=3, fallback=TokenMean())

    def key(self, cell):
        return (cell.family, self.rel(cell), cell.token)


class CarPosMean(ItemKeyed):
    def __init__(self) -> None:
        super().__init__("u1carpos", "mean over reference cells of items with the same read-span text at the same "
                         "index (same sentence, same position; >= 2 cells, else u1reltok)",
                         min_cells=2, fallback=RelTokMean())

    def key(self, cell):
        return (cell.family, self.span(cell), cell.i)


class RelOtherTokMean:
    """Control for position matching: the mean over reference cells at the same offset from the span's end but
    with a *different* read token (position-matched, token-mismatched). Fewer than 3 such cells: fam."""

    name = "u1relx"
    doc = "control: mean over reference cells at the same offset from the span's end with another read token"

    def __init__(self) -> None:
        self.rel, self.reltok, self.fam = RelMean(), RelTokMean(), FamilyMean()
        self.items_of: dict = {}
        self.n_fallback = 0

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        for c in (self.rel, self.reltok, self.fam):
            c.fit(ref, family, groups)

    def _sum(self, c: KeyedMean, cell: CellRef) -> tuple:
        k = (cell.layer, c.key(cell))
        s, n = c.s.get(k, 0.0), c.n.get(k, 0)
        if (*k, cell.group) in c.own:
            o = c.own[(*k, cell.group)]
            s, n = s - o[0], n - o[1]
        return s, n

    def __call__(self, cell: CellRef) -> torch.Tensor:
        (s1, n1), (s2, n2) = self._sum(self.rel, cell), self._sum(self.reltok, cell)
        if n1 - n2 < 3:
            self.n_fallback += 1
            return self.fam(cell)
        return ((s1 - s2) / (n1 - n2)).float()

    def transform(self, batch: Batch) -> torch.Tensor:
        _set_items(self.rel, batch.items)
        _set_items(self.reltok, batch.items)
        return batch.H - torch.stack([self(c) for c in batch.cells])

    def support(self, cell: CellRef) -> tuple[int, bool]:
        n = self._sum(self.rel, cell)[1] - self._sum(self.reltok, cell)[1]
        return (n, False) if n >= 3 else (self.fam.support(cell)[0], True)


class _Keyed(ItemKeyed):
    """A plain keyed sum with a key function given at construction (building block, not registered)."""

    def __init__(self, keyf) -> None:
        super().__init__("_keyed", "", min_cells=1, fallback=None)
        self.keyf = keyf

    def key(self, cell):
        return self.keyf(self, cell)


class OtherSentenceMean:
    """Token matching without sentence matching: the mean over reference cells with the same key (``tok``: read token;
    ``reltok``: offset and read token) from items whose sentence (read-span text; the whole render for a one-cell
    item) differs from this item's. A rare carrier word
    can then no longer pool the few items that copy the same sentence (U1 insight 2). Fewer than 3 such cells:
    ``u1rel``."""

    def __init__(self, with_rel: bool) -> None:
        self.with_rel = with_rel
        self.name = "u1reltokxs" if with_rel else "u1tokxs"
        self.doc = (f"mean over reference cells with the same {'offset and ' if with_rel else ''}read token from items "
                    "with a different read-span text (>= 3 cells, else u1rel)")
        tk = (lambda c, x: (x.family, c.rel(x), x.token)) if with_rel else (lambda c, x: (x.family, x.token))
        self.key = _Keyed(tk)
        self.key_span = _Keyed(lambda c, x: (*tk(c, x), c.sentence(x)))
        self.rel = RelMean()
        self.n_fallback = 0

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        for c in (self.key, self.key_span, self.rel):
            c.fit(ref, family, groups)

    def _other(self, cell: CellRef) -> tuple:
        def raw(c):  # sums over the key, own group NOT removed (the span sum removes it when spans match)
            k = (cell.layer, c.key(cell))
            return c.s.get(k, 0.0), c.n.get(k, 0)

        (s1, n1), (s2, n2) = raw(self.key), raw(self.key_span)
        s, n = s1 - s2, n1 - n2
        k = (cell.layer, self.key.key(cell))
        o = self.key.own.get((*k, cell.group))
        ks = (cell.layer, self.key_span.key(cell))
        os_ = self.key_span.own.get((*ks, cell.group))
        if o is not None:  # own-group cells in other sentences (a group member with another span) also leave
            on, osum = o[1] - (os_[1] if os_ else 0), o[0] - (os_[0] if os_ else 0.0)
            s, n = s - osum, n - on
        return s, n

    def __call__(self, cell: CellRef) -> torch.Tensor:
        s, n = self._other(cell)
        if n < 3:
            self.n_fallback += 1
            return self.rel(cell)
        return (s / n).float()

    def transform(self, batch: Batch) -> torch.Tensor:
        for c in (self.key, self.key_span, self.rel):
            _set_items(c, batch.items)
        return batch.H - torch.stack([self(c) for c in batch.cells])

    def support(self, cell: CellRef) -> tuple[int, bool]:
        n = self._other(cell)[1]
        return (n, False) if n >= 3 else (self.rel.support(cell)[0], True)


class EndCarPos(ItemKeyed):
    """``u1carpos`` at the last read cell of the span (the end of the copied unit, where the mention control finds held
    and mentioned concepts separating for every centre), ``u1rel`` everywhere else (U1 insight 8)."""

    def __init__(self) -> None:
        super().__init__("u1endcar", "same sentence, same position at the span's last cell (>= 2 cells); offset mean "
                         "elsewhere", min_cells=2, fallback=RelMean())

    def key(self, cell):
        return (cell.family, self.span(cell), cell.i) if self.rel(cell) == 0 else (cell.family, "rel", self.rel(cell))

    def _mean(self, cell, k):
        if k[1][1] == "rel":  # not the last cell: the offset mean
            self._last_fallback = 0
            return self.fallback(cell)
        return super()._mean(cell, k)


class RelMeanFew(RelMean):
    """n-scaling control for ``u1rel``: the same offset mean from only ``n`` reference groups (seeded sample, the cell's
    the cell's own group excluded as always, so n - 1 when it is sampled). Does the position mean need many references?"""

    def __init__(self, n: int, seed: int = 0) -> None:
        super().__init__()
        self.n_groups, self.seed = n, seed
        self.name, self.doc = f"u1rel{n}", f"offset mean from {n} sampled reference groups (n-scaling of u1rel)"

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        import random

        g = groups or {}
        keep = sorted({g.get(it.id, it.id) for it in ref})
        random.Random(self.seed).shuffle(keep)
        keep = set(keep[: self.n_groups])
        super().fit([it for it in ref if g.get(it.id, it.id) in keep], family, groups)


class CtxKeyed(KeyedMean):
    """A ``KeyedMean`` over every position of the reference renders (the context capture), not only their read
    cells. ``ctx_key(item, t)`` keys position t of a reference render; ``key(cell)`` keys the read cell."""

    needs_ctx = True

    def ctx_key(self, decoded: list[str], t: int) -> Hashable:
        raise NotImplementedError

    def fit(self, ref, family, groups=None, ctx: ContextStore | None = None) -> None:
        assert ctx is not None, f"{self.name} needs a context capture (out/ctx)"
        groups = groups or {}
        layers = sorted({L for it in ref for L in it.acts} & set(ctx.layers()))
        ids = {it.id for it in ref}
        self.s, self.n = defaultdict(float), defaultdict(int)
        self.rows: dict = defaultdict(list)  # group -> [(keys, ctx row)]: own sums are taken at read time
        for iid, row in ctx.items.items():
            if iid not in ids:
                continue
            keys = [self.ctx_key(row.decoded, t) for t in range(len(row.ids))]
            self.rows[groups.get(iid, iid)].append((keys, row))
            for L in layers:
                A = row.acts[L].double()
                for t, kk in enumerate(keys):
                    k = (L, kk)
                    self.s[k] = self.s[k] + A[t]
                    self.n[k] += 1
        self.own = {}
        self.fallback.fit(ref, family, groups)
        self.n_fallback, self._memo = 0, {}

    def _own(self, cell: CellRef, k: tuple) -> tuple:
        s, n = 0.0, 0
        for keys, row in self.rows.get(cell.group, []):
            ts = [t for t, kk in enumerate(keys) if kk == k[1]]
            if ts and k[0] in row.acts:
                s, n = s + row.acts[k[0]][ts].double().sum(0), n + len(ts)
        return s, n

    def _mean(self, cell: CellRef, k: tuple) -> torch.Tensor:
        self._last_fallback = 0
        os_, on = self._own(cell, k)
        s, n = self.s.get(k, 0.0) - os_, self.n.get(k, 0) - on
        if n < self.min_cells:
            self.n_fallback += 1
            self._last_fallback = 1
            return self.fallback(cell)
        return (s / n).float()

    def support(self, cell: CellRef) -> tuple[int, bool]:
        k = (cell.layer, self.key(cell))
        n = self.n.get(k, 0) - self._own(cell, k)[1]
        return (self.fallback.support(cell)[0], True) if n < self.min_cells else (n, False)


class PosMean(CtxKeyed):
    def __init__(self) -> None:
        super().__init__("u1pos", "mean over every position t of the reference renders at the cell's absolute "
                         "position t (context capture; >= 3 cells, else fam)", min_cells=3, fallback=FamilyMean())

    def ctx_key(self, decoded, t):
        return ("pos", t)

    def key(self, cell):
        return ("pos", len(cell.context) - 1)


class TokAnyMean(CtxKeyed):
    def __init__(self) -> None:
        super().__init__("u1tokany", "mean over every occurrence of the read token in the reference renders, any "
                         "position (context capture; >= 3 cells, else fam)", min_cells=3, fallback=FamilyMean())

    def ctx_key(self, decoded, t):
        return ("tok", decoded[t])

    def key(self, cell):
        return ("tok", cell.token)


_WIKI: dict = {}  # layer -> ([T, d] float64 sums, [T] counts), computed once per process


def wiki_position_sums(path=None) -> dict:
    if not _WIKI:
        store = ContextStore(path or corpus_path("wikitext"))
        for L in store.layers():
            rows = [r.acts[L] for r in store.items.values()]
            T = max(len(r) for r in rows)
            S, N = torch.zeros(T, rows[0].shape[1], dtype=torch.float64), torch.zeros(T, dtype=torch.long)
            for r in rows:
                S[: len(r)] += r.double()
                N[: len(r)] += 1
            _WIKI[L] = (S, N)
        del store
    return _WIKI


class WikiPosMean:
    """Mean of the wikitext corpus states at the cell's absolute position t (no bench content at all); position
    beyond the corpus length or a layer the corpus lacks: fam."""

    name = "u1poswiki"
    doc = "mean of the wikitext corpus states (256 x 128 tokens) at the cell's absolute position t, else fam"

    def __init__(self, path=None) -> None:
        self.path, self.fam, self.n_fallback = path, FamilyMean(), 0

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.sums = wiki_position_sums(self.path)
        self.fam.fit(ref, family, groups)

    def __call__(self, cell: CellRef) -> torch.Tensor:
        t = len(cell.context) - 1
        if cell.layer in self.sums and t < len(self.sums[cell.layer][1]) and self.sums[cell.layer][1][t] > 0:
            S, N = self.sums[cell.layer]
            return (S[t] / N[t]).float()
        self.n_fallback += 1
        return self.fam(cell)

    def support(self, cell: CellRef) -> tuple[int, bool]:
        t = len(cell.context) - 1
        if cell.layer in self.sums and t < len(self.sums[cell.layer][1]):
            return int(self.sums[cell.layer][1][t]), False
        return self.fam.support(cell)[0], True


CENTRES |= {"u1pos": PosMean, "u1poswiki": WikiPosMean, "u1rel": RelMean, "u1slot": SlotMean,
            "u1relx": RelOtherTokMean, "u1tokany": TokAnyMean, "u1reltok": RelTokMean, "u1carpos": CarPosMean,
            "u1endcar": EndCarPos, "u1rel4": lambda: RelMeanFew(4), "u1rel8": lambda: RelMeanFew(8),
            "u1rel16": lambda: RelMeanFew(16), "u1tokxs": lambda: OtherSentenceMean(False), "u1reltokxs": lambda: OtherSentenceMean(True)}
