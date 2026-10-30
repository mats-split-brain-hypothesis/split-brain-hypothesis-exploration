"""Centres ``g`` for the readout ``J_l (h - g)`` ("mu" when g is a mean).

A centre is fitted on a reference set of captures and then gives ``g`` for a read cell. The simple form is
``__call__(CellRef) -> mu``; a centre whose g depends on the state itself, on other layers or on earlier
positions implements ``transform(Batch) -> h - g`` instead (``apply`` picks). It sees
a ``CellRef``: the item id, family, layer, read position and token and the rendered prompt up to
the read cell, but never the item's targets. That is the "no crystal ball" rule, enforced by
what the pipeline passes, not by convention. An item never contributes to its own centre, nor
does any item of its group (DM: the pair's twin, which holds the same concept, as umot's
concept-aware exclusion). So fitting on the read set itself gives leave-one-group-out means
(jle's loo1) and fitting on a dev bank gives held-out means (jle's dev1).
"""

from collections import defaultdict
from collections.abc import Hashable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

import torch
from umot.capture import ItemCapture

if TYPE_CHECKING:
    from jlm.context import ContextStore


@dataclass(frozen=True)
class CellRef:
    item: str
    group: str  # items of one group never centre each other (the item id unless the bank pairs items)
    family: str
    layer: int
    i: int  # index into the item's read cells
    pos: int  # read position as the plan reports it
    token: str  # the read-site token
    context: tuple[str, ...]  # decoded render up to and including the read token


def cell_refs(items: list[ItemCapture], family: str, layer: int, groups: dict[str, str] | None = None) -> list[CellRef]:
    groups = groups or {}
    return [
        CellRef(it.id, groups.get(it.id, it.id), family, layer, i, it.positions[i], it.token(i),
                tuple(it.decoded[: it.idx[i] + 1]))
        for it in items
        for i in range(len(it.positions))
    ]


@dataclass
class Batch:
    """What a centre may look at to read one layer of a bank: the read cells, their states, the bank's
    read-cell captures (every captured layer) and, when a context capture exists and the centre asks for it
    (``needs_ctx``), every position's state. Never the targets."""

    layer: int
    cells: list[CellRef]
    H: torch.Tensor  # [n, d] float32, the states at ``cells``
    items: dict[str, ItemCapture]
    ctx: "ContextStore | None" = None


class Centre(Protocol):
    name: str
    doc: str
    needs_ctx: bool  # optional (default False): fit and transform want every-position states

    def fit(self, ref: list[ItemCapture], family: str, groups: dict[str, str] | None = None,
            ctx: "ContextStore | None" = None) -> None: ...

    def __call__(self, cell: CellRef) -> torch.Tensor: ...  # [d] float32; or instead:
    # def transform(self, batch: Batch) -> torch.Tensor: ...  # [n, d] float32, the states to read (h - g)

    def support(self, cell: CellRef) -> tuple[int, bool]: ...  # (reference cells behind mu, fell back)

    # Optional, for the dashboard's per-cell view of how mu is chosen (centres that average reference cells):
    # def reference(self, layer: int) -> tuple[torch.Tensor, list[tuple[str, str, str]]]: ...  # pool [N, d], (group, family, token)
    # def members(self, batch: Batch) -> list[torch.Tensor]: ...  # per cell, the reference rows averaged into its mu


def apply(centre: "Centre", batch: Batch) -> torch.Tensor:
    """The states the lens reads, ``h - g`` [n, d] float32: the centre's own ``transform`` if it has one,
    else ``g = centre(cell)`` per cell."""
    if hasattr(centre, "transform"):
        return centre.transform(batch)
    return batch.H - torch.stack([centre(c) for c in batch.cells])


class Zero:
    """``mu = 0``: the released lens's uncentred readout."""

    name, doc = "zero", "no centring (the released lens reads J h)"

    def fit(self, ref: list[ItemCapture], family: str, groups: dict[str, str] | None = None, ctx=None) -> None:
        self.d = next(iter(ref[0].acts.values())).shape[1]

    def __call__(self, cell: CellRef) -> torch.Tensor:
        return torch.zeros(self.d)

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return 0, False


class KeyedMean:
    """Mean over reference cells sharing ``key(cell)``, excluding the cell's own item. Below
    ``min_cells`` remaining cells it uses ``fallback``. Sums are float64."""

    def __init__(self, name: str, doc: str, *, min_cells: int = 1, fallback: "Centre | None" = None) -> None:
        self.name, self.doc, self.min_cells, self.fallback = name, doc, min_cells, fallback
        self.n_fallback = 0

    def key(self, cell: CellRef) -> Hashable:
        raise NotImplementedError

    def fit(self, ref: list[ItemCapture], family: str, groups: dict[str, str] | None = None, ctx=None) -> None:
        self._ref, self._family, self._groups = ref, family, groups  # for reference() / members()
        self.s: dict = defaultdict(float)  # (layer, key) -> sum
        self.n: dict = defaultdict(int)
        self.own: dict = defaultdict(lambda: [0.0, 0])  # (layer, key, group) -> [sum, n]
        for layer in sorted({L for it in ref for L in it.acts}):
            for it in ref:
                if layer not in it.acts:
                    continue
                acts = it.acts[layer]
                for c in cell_refs([it], family, layer, groups):
                    k, h = (layer, self.key(c)), acts[c.i].double()
                    self.s[k] = self.s[k] + h
                    self.n[k] += 1
                    o = self.own[(*k, c.group)]
                    o[0], o[1] = o[0] + h, o[1] + 1
        if self.fallback is not None:
            self.fallback.fit(ref, family, groups)
        self.n_fallback = 0
        self._memo: dict = {}

    def __call__(self, cell: CellRef) -> torch.Tensor:
        k = (cell.layer, self.key(cell))
        if (*k, cell.group) in self._memo:  # same key and group -> same mean
            hit, mu = self._memo[(*k, cell.group)]
            self.n_fallback += hit
            return mu
        mu = self._mean(cell, k)
        self._memo[(*k, cell.group)] = (self._last_fallback, mu)
        return mu

    def _mean(self, cell: CellRef, k: tuple) -> torch.Tensor:
        self._last_fallback = 0
        s, n = self.s.get(k, 0.0), self.n.get(k, 0)
        if (*k, cell.group) in self.own:
            o = self.own[(*k, cell.group)]
            s, n = s - o[0], n - o[1]
        if n < self.min_cells:
            if self.fallback is None:
                raise ValueError(f"{cell.item} L{cell.layer}: {n} reference cells for key {k[1]!r}")
            self.n_fallback += 1
            self._last_fallback = 1
            return self.fallback(cell)
        return (s / n).float()

    def support(self, cell: CellRef) -> tuple[int, bool]:
        """(reference cells averaged into this cell's mu, whether it fell back), as ``__call__`` decides."""
        k = (cell.layer, self.key(cell))
        n = self.n.get(k, 0) - self.own.get((*k, cell.group), (0.0, 0))[1]
        if n < self.min_cells and self.fallback is not None:
            return self.fallback.support(cell)[0], True
        return n, False

    def _rows(self, layer: int) -> list[CellRef]:
        return cell_refs([it for it in self._ref if layer in it.acts], self._family, layer, self._groups)

    def reference(self, layer: int) -> tuple[torch.Tensor, list[tuple[str, str, str]]]:
        rows, by_id = self._rows(layer), {it.id: it for it in self._ref}
        return (torch.stack([by_id[c.item].acts[layer][c.i].float() for c in rows]),
                [(c.group, c.family, c.token) for c in rows])

    def members(self, batch: Batch) -> list[torch.Tensor]:
        """Per cell, the reference rows (in ``reference`` order) averaged into its mu, as ``__call__`` decides."""
        rows, out = self._rows(batch.layer), []
        for cell in batch.cells:
            n, fell = self.support(cell)
            if fell:
                out.append(self.fallback.members(Batch(batch.layer, [cell], batch.H[:1], batch.items))[0])
                continue
            k = self.key(cell)
            out.append(torch.tensor([j for j, c in enumerate(rows) if self.key(c) == k and c.group != cell.group], dtype=torch.long))
        return out


class FamilyMean(KeyedMean):
    """One mean per layer over every reference cell of the family (jle's loo1 / dev1)."""

    def __init__(self) -> None:
        super().__init__("fam", "mean over every reference cell at the layer, own item and its group excluded")

    def key(self, cell: CellRef) -> Hashable:
        return cell.family


class TokenMean(KeyedMean):
    """Mean over reference cells with the same read token (jle's tok1), else the family mean."""

    def __init__(self, min_cells: int = 3) -> None:
        super().__init__(
            "tok",
            f"mean over reference cells with the same read token (>= {min_cells} cells, else fam)",
            min_cells=min_cells,
            fallback=FamilyMean(),
        )

    def key(self, cell: CellRef) -> Hashable:
        return (cell.family, cell.token)


def _derangement(n: int, seed: int) -> torch.Tensor:
    """A random permutation of ``range(n)`` with no fixed point (one random cycle), for n >= 2."""
    p = torch.randperm(n, generator=torch.Generator().manual_seed(seed))
    out = torch.empty(n, dtype=torch.long)
    out[p] = p.roll(-1)
    return out


class Shuffled:
    """Control: every cell is read with the g of another read cell at the same layer (a seeded random cycle
    over the bank's cells), the arm otherwise unchanged. If this matches the arm, the gain does not come from
    matching g to the cell. Identical to the arm when g is one vector per layer (``fam``)."""

    def __init__(self, inner: Centre, seed: int = 0) -> None:
        self.inner, self.seed = inner, seed
        self.name, self.doc = f"shuf.{inner.name}", f"control: another cell's g ({inner.doc})"
        self.needs_ctx = getattr(inner, "needs_ctx", False)

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.inner.fit(ref, family, groups, ctx)

    def transform(self, batch: Batch) -> torch.Tensor:
        G = batch.H - apply(self.inner, batch)
        if len(G) < 2:
            return batch.H - G
        return batch.H - G[_derangement(len(G), self.seed * 1000 + batch.layer)]

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return self.inner.support(cell)


class RandomDir:
    """Control: g replaced by a random direction (one per layer, seeded) with each cell's ||g||. If this
    matches the arm, the gain is a norm or bias effect, not content."""

    def __init__(self, inner: Centre, seed: int = 0) -> None:
        self.inner, self.seed = inner, seed
        self.name, self.doc = f"rand.{inner.name}", f"control: a random direction with ||g|| of ({inner.doc})"
        self.needs_ctx = getattr(inner, "needs_ctx", False)

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.inner.fit(ref, family, groups, ctx)

    def transform(self, batch: Batch) -> torch.Tensor:
        norms = (batch.H - apply(self.inner, batch)).norm(dim=1, keepdim=True)
        u = torch.randn(batch.H.shape[1], generator=torch.Generator().manual_seed(self.seed * 1000 + batch.layer))
        return batch.H - norms * (u / u.norm())

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return self.inner.support(cell)


CENTRES: dict[str, type] = {"zero": Zero, "fam": FamilyMean, "tok": TokenMean}
#: Control wrappers: ``shuf.<centre>``, ``rand.<centre>`` (see notes/iteration-anthony/research-loop.md, "Controls").
CONTROLS = {"shuf": Shuffled, "rand": RandomDir}
#: Parametric names ``<head>:<args>`` (``genk:8``, ``dict:fam:0.5``): a study module registers a factory taking
#: ``<args>``; ``make`` uses it only when the full name is not a ``CENTRES`` key.
PARAMETRIC: dict = {}


def make(name: str) -> Centre:
    """A centre by arm name: a ``CENTRES`` key, a study centre (``jlm.mu``), or a control prefix on either."""
    head, dot, rest = name.partition(".")
    if dot and head in CONTROLS:
        return CONTROLS[head](make(rest))
    if name not in CENTRES:
        import jlm.mu  # noqa: F401  (study modules register their centres on import)
    head, colon, rest = name.partition(":")
    if name not in CENTRES and colon and head in PARAMETRIC:
        return PARAMETRIC[head](rest)
    return CENTRES[name]()
