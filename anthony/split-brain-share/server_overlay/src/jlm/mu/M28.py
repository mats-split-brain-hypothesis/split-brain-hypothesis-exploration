"""M28 (night-3 B; R5a): a model-written task-prompt pool as bench-kind cells for S14bL's late neighbour step.

``tpk<K>`` = the mean of h's K nearest (cosine) cells among the final tokens of the task prompts the 27B wrote from 16
generic task types (``out/captures/tprompt-<task>.pt``, ``experiments/m28_pools.py``); ``tpkr<K>`` = K random cells of
the same pool (the control). Chat renders (UM, DM): the pool is plain-render, so the centre falls back to the M23
default's base (``gnw1``). Arms: ``sched:40:gnw1+s14:chatpunct:128:mean=tpk8:a=0.5`` (S14bL's form with the task pool).
"""

import torch

from jlm import centres
from jlm.centres import CENTRES, Batch, CellRef
import re

from jlm.mu.M28pools import DOLLY, TASKS  # noqa: F401  (kept in one place)

_ROWS: dict = {}


def task_rows(layer: int) -> torch.Tensor:
    if layer not in _ROWS:
        from jlm.mu import M1

        _ROWS[layer] = torch.cat([M1._capture_rows(f"tprompt-{t}.pt")[layer] for t in TASKS]).float()
    return _ROWS[layer]


class TaskKNN:
    def __init__(self, k: int, rand: bool = False, plain_only: bool = False) -> None:
        self.k, self.rand, self.plain_only = k, rand, plain_only
        self.name = f"tpk{'r' if rand else ''}{k}"
        self.doc = f"mean of {k} {'random' if rand else 'nearest (cosine)'} task-prompt cells (model-written, 16 task types)"
        self.n_fallback = 0

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        from jlm.mu import M1

        self.family, self.chat = family, M1.render(family) == "chat" and not self.plain_only
        if self.chat:
            self.fallback = centres.make("gnw1")
            self.fallback.fit(ref, family, groups)

    def transform(self, batch: Batch) -> torch.Tensor:
        if self.chat:
            return centres.apply(self.fallback, batch)
        P = task_rows(batch.layer)
        k = min(self.k, len(P))
        if self.rand:
            g = torch.Generator().manual_seed(batch.layer)
            idx = torch.stack([torch.randperm(len(P), generator=g)[:k] for _ in range(len(batch.H))])
        else:
            sim = torch.nn.functional.normalize(batch.H.float(), dim=1) @ torch.nn.functional.normalize(P, dim=1).T
            idx = sim.topk(k, dim=1).indices
        return batch.H - P[idx].mean(1)

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return self.k, False


for _k in (8, 32):
    CENTRES[f"tpk{_k}"] = lambda k=_k: TaskKNN(k)
    CENTRES[f"tpkr{_k}"] = lambda k=_k: TaskKNN(k, rand=True)

# the M23 default under a name without ':' (for schedules: ``sched:40:dflt+...``)
# ``tpk32p``: no chat fallback (the plain task pool on chat-render cells too): the mention-bank content test
CENTRES["tpk32p"] = lambda: TaskKNN(32, plain_only=True)
CENTRES["dflt"] = lambda: centres.make("s14:chatpunct:128:mean=gnw1:a=1")


# M31: the pool rebuilt from Dolly-15k's 8 categories (``tpdolly-<cat>.pt``) and a prompt-word filter on the neighbours.
_POOLS: dict = {}


def _words(t: str) -> set[str]:
    return {w for w in re.findall(r"[^\W_]+", t.lower()) if len(w) >= 3}


def pool(prefix: str, names, layer: int):
    """(rows [N, d], word sets per row) of a task-prompt pool at ``layer``."""
    key = (prefix, layer)
    if key not in _POOLS:
        from umot import capture as ucap

        from jlm.mu import M1

        items = [it for n in names for it in ucap.load(M1.CAPS / f"{prefix}-{n}.pt")]
        _POOLS[key] = (torch.cat([it.acts[layer].float() for it in items]), [_words("".join(it.decoded)) for it in items])
    return _POOLS[key]


class FilteredTaskKNN(TaskKNN):
    """``tpb<K>[f]``: kNN over the Dolly pool; ``f``: drop neighbours whose text shares a word with the read item's prompt."""

    def __init__(self, k: int, rand: bool = False, filt: bool = False, prefix: str = "tpdolly") -> None:
        super().__init__(k, rand)
        self.filt, self.prefix = filt, prefix
        self.names = DOLLY if prefix == "tpdolly" else TASKS
        self.name = f"{'tpb' if prefix == 'tpdolly' else 'tpk'}{'r' if rand else ''}{k}{'f' if filt else ''}"
        self.doc = (f"mean of {k} {'random' if rand else 'nearest'} cells of the Dolly-category task-prompt pool"
                    + (", neighbours sharing a word with the item's prompt dropped" if filt else ""))

    def transform(self, batch: Batch) -> torch.Tensor:
        if self.chat:
            return centres.apply(self.fallback, batch)
        P, W = pool(self.prefix, self.names, batch.layer)
        if self.rand:
            g = torch.Generator().manual_seed(batch.layer)
            idx = torch.stack([torch.randperm(len(P), generator=g)[: self.k] for _ in range(len(batch.H))])
            return batch.H - P[idx].mean(1)
        sim = torch.nn.functional.normalize(batch.H.float(), dim=1) @ torch.nn.functional.normalize(P, dim=1).T
        order = sim.topk(min(len(P), 8 * self.k), dim=1).indices
        out = []
        for c, h, row in zip(batch.cells, batch.H, order.tolist()):
            if self.filt:
                pw = _words("".join(c.context))
                row = [j for j in row if not (W[j] & pw)] or row
            out.append(h - P[row[: self.k]].mean(0))
        return torch.stack(out)


CENTRES["tpb32"] = lambda: FilteredTaskKNN(32)
CENTRES["tpb32f"] = lambda: FilteredTaskKNN(32, filt=True)
CENTRES["tpbr32"] = lambda: FilteredTaskKNN(32, rand=True)
CENTRES["tpk32f"] = lambda: FilteredTaskKNN(32, filt=True, prefix="tprompt")  # M28's pool with M31's filter
