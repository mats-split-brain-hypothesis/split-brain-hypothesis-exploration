"""Centres for centred token readers: a mean residual per cell, built from OTHER items' cells.

A centre is defined by a key on cells (which cells are pooled: every cell of the family, cells with
the same read token, cells of the same sentence at the same position, ...) and an exclusion rule:
an item never contributes to its own centre, nor does any item that shares one of its concepts
(a pair's twin holds the same concept; in the mention control an item that holds or mentions the
same word). Everything is label-free in the no-peeking sense: keys and exclusions use the prompt
and its metadata, never the readout's judged answer. jlens-edits' x99/x100 arms are special cases
(own1/loo1: one key; tok1: the read token with at least ``min_cells`` cells, else the family mean).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Hashable

import torch

from umot.capture import ItemCapture

CellKey = Callable[[ItemCapture, int], Hashable]  # (item, read index) -> pooling key


class Centre:
    """Per-cell means over matching cells of items that share none of the item's concepts.

    ``key`` picks which cells pool together; ``concepts`` maps an item to the set of concepts it
    involves (an item always excludes itself, even with an empty set); ``fallback`` (optional) is
    the centre used where fewer than ``min_cells`` cells remain. Sums are float64.
    """

    def __init__(
        self,
        items: list[ItemCapture],
        key: CellKey,
        concepts: Callable[[ItemCapture], frozenset],
        *,
        min_cells: int = 1,
        fallback: Centre | None = None,
    ) -> None:
        self.key, self.concepts, self.min_cells, self.fallback = key, concepts, min_cells, fallback
        self.s: dict = defaultdict(lambda: 0.0)  # (layer, key) -> sum over all items
        self.n: dict = defaultdict(int)
        self.per_item: dict = defaultdict(dict)  # (layer, key) -> {item id: [sum, n]}
        self.by_concept: dict = defaultdict(set)  # concept -> item ids
        for it in items:
            for c in concepts(it):
                self.by_concept[c].add(it.id)
            for layer, acts in it.acts.items():
                for i in range(acts.shape[0]):
                    k, h = key(it, i), acts[i].double()
                    self.s[layer, k] = self.s[layer, k] + h
                    self.n[layer, k] += 1
                    cell = self.per_item[layer, k].setdefault(it.id, [0.0, 0])
                    cell[0] = cell[0] + h
                    cell[1] += 1
        self.n_fallback = 0

    def excluded(self, item: ItemCapture) -> set[str]:
        out = {item.id}
        for c in self.concepts(item):
            out |= self.by_concept[c]
        return out

    def __call__(self, item: ItemCapture, layer: int, i: int) -> torch.Tensor:
        k = self.key(item, i)
        pool = self.per_item[layer, k]
        s, n = self.s[layer, k], self.n[layer, k]
        for j in self.excluded(item):
            if j in pool:
                s, n = s - pool[j][0], n - pool[j][1]
        if n < self.min_cells:
            if self.fallback is None:
                raise ValueError(f"{item.id} L{layer} #{i}: {n} cells for key {k!r}")
            self.n_fallback += 1
            return self.fallback(item, layer, i)
        return (s / n).float()


def centred_rows(
    method, items: list[ItemCapture], centre: Centre, keep: Callable[[ItemCapture, int], bool] | None = None
):
    """Readout rows of ``method`` on ``h − centre(cell)`` at every captured cell (or those ``keep``
    accepts), in the bench's readouts contract."""
    from umot.readers import row

    for item in items:
        for layer, acts in sorted(item.acts.items()):
            for i in range(acts.shape[0]):
                if keep is not None and not keep(item, i):
                    continue
                h = acts[i].float() - centre(item, layer, i)
                yield row(item, layer, i, method.read(h, layer).row())
