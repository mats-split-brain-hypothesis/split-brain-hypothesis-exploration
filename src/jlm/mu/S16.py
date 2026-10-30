"""S16 form-blind neighbours, full-state means (notes/iteration-anthony/mu-log.md, card S16).

knnx8 (S4) averages the 8 pool cells nearest h in the centred unit space; its gain is the question-type match, its leak
the same-sentence match (S8). Here the neighbours are chosen by distance in a **form subspace** only, and g is still the
mean of their full raw states. Pool, unit space and exclusions are knnx8's (``clusters.NearestMean``: every family's
fit read cells, own group excluded).

- ``s16pc<k>``: knnx's score (dot product of centred unit vectors) after projecting onto the top-16 principal directions of the pooled fit cells at the layer
  (all families: the axes S7 removes, family-free).
- ``s16tb<k>``: the same in S14's template subspace ``B`` (``pullback.load_tbasis``, first 64 template tokens).
- ``s16pcd<k>``: ``s16pc`` with knnxd's content-disjoint rule (no neighbour whose prompt shares a rare word).
- ``s16pr<k>``: control, a random 16-dim subspace in place of the PCs.
- ``s16xo<k>`` (S18 x S16, night-2 insight): knnx's score with the 32 outlier coordinates (largest mean |h| over the
  pool, per layer: the massive activations that hold 40-70 % of ||h||^2 and none of fam's gain, S18) zeroed before
  the unit normalisation, so the distance is set by the coordinates the readout uses; ``s16xopc<k>`` the same in the
  top-16 PCs of the outlier-free pool.
- ``knnxs<k>`` (the steward's card: the fair DM kNN): knnx<k> with every neighbour that shares the read cell's carrier
  excluded. Carrier = the bank item's ``carrier`` sentence where the bank has one (DM: 12 carriers shared by fit and val),
  else the last 6 tokens of the rendered context up to the read cell (S8 / S16's same-sentence test).
- ``knnxm<k>`` / ``knnxsm<k>`` (mention control with a carrier-sharing pool, research-loop rule): knnx<k> / knnxs<k>
  whose pool is the bench fit pool **plus the arm's own reference cells** (own group excluded as always). Read with
  ``experiments/u1_mention.py --arms knnxm8,knnxsm8``, the reference is the mention bank's own pool, whose other pairs
  share the probe's carrier: the test pilot-1 asked for. Not for out/eval (on a dev bank it would add the read bank).
k in 8 / 32. ``s16pc`` with ``dim = d`` would be knnx (tested on a toy).
"""

from collections import Counter
from functools import partial

import torch

from jlm import pullback
from jlm.centres import CENTRES, Batch
from jlm.mu.clusters import NearestMean, prompt_words, unit_space

OWNER = "Anthony"
CANDIDATES = ()

_SPACES: dict = {}  # (space, layer, dim) -> [d, dim] orthonormal basis


class FormNearest(NearestMean):
    def __init__(self, k: int, space: str, dim: int = 16, disjoint: bool = False, tb_k: int = 64, seed: int = 0,
                 drop_outliers: int = 0) -> None:
        super().__init__(k, "bench", disjoint=disjoint)
        self.space, self.dim, self.tb_k, self.seed, self.drop = space, dim, tb_k, seed, drop_outliers
        stem = {"pc": "s16pc", "tb": "s16tb", "rand": "s16pr", "full": "s16xo"}[space]
        if drop_outliers and space == "pc":
            stem = "s16xopc"
        self.name = f"{stem}{'d' if disjoint and space == 'pc' else ''}{k}"
        where = {"pc": f"the top-{dim} principal directions of the pooled fit cells",
                 "tb": f"S14's template subspace (first {tb_k} template tokens' reading directions)",
                 "rand": f"a random {dim}-dim subspace (control)", "full": "the full space"}[space]
        if drop_outliers:
            where += f", the {drop_outliers} outlier coordinates (largest pool-mean |h|) left out of the distance"
        self.doc = (f"mean of the {k} fit read cells (all families) nearest h in {where}, own group excluded"
                    + (" [no neighbour sharing a rare prompt word]" if disjoint else ""))

    def keep(self, L: int) -> torch.Tensor:
        """[d] 0/1 mask of the coordinates the distance uses (all, or all but the outliers)."""
        key = ("keep", L, self.drop)
        if key not in _SPACES:
            X = self.pool.X[L].float()
            m = torch.ones(X.shape[1])
            if self.drop:
                m[X.abs().mean(0).topk(self.drop).indices] = 0.0
            _SPACES[key] = m
        return _SPACES[key]

    def basis(self, L: int, U: torch.Tensor) -> torch.Tensor:
        key = (self.space, L, self.dim if self.space != "tb" else self.tb_k, self.seed, self.drop)
        if key not in _SPACES:
            if self.space == "pc":
                with torch.random.fork_rng():
                    torch.manual_seed(L)
                    _, _, V = torch.svd_lowrank(U.double(), q=self.dim + 16, niter=4)
                _SPACES[key] = V[:, : self.dim].float()
            elif self.space == "tb":
                _SPACES[key] = pullback.load_tbasis(pullback.default_key(), "cos", "template", self.tb_k, L).float()
            else:
                g = torch.Generator().manual_seed(self.seed * 1000 + L)
                _SPACES[key] = torch.linalg.qr(torch.randn(U.shape[1], self.dim, generator=g))[0]
        return _SPACES[key]

    def similarities(self, batch: Batch) -> torch.Tensor:
        m = self.keep(batch.layer)
        X = self.pool.X[batch.layer].float() * m
        U, centre = unit_space(X)  # already centred by the pool's mean unit vector
        Q = unit_space(batch.H * m, centre)[0]
        if self.space == "full":
            return Q @ U.T
        B = self.basis(batch.layer, U)
        return (Q @ B) @ (U @ B).T  # knnx's score, restricted to the subspace

    def _neighbours(self, batch: Batch) -> torch.Tensor:
        """knnx's exclusions (``NearestMean._neighbours``), with ``similarities`` in place of the full-space cosine."""
        sims = self.similarities(batch)
        if self.disjoint:
            df = Counter(w for g, rows in self.pool.rows_of.items() for w in self.pool.words[int(rows[0])])
            rare = {w for w, n in df.items() if n <= self.rare}
        for j, cell in enumerate(batch.cells):
            own = self.pool.rows_of.get(cell.group)
            if own is not None:
                sims[j, own] = -torch.inf
            if self.disjoint:
                mine = prompt_words(batch.items[cell.item].decoded[: batch.items[cell.item].idx[cell.i] + 1]) & rare
                if mine:
                    sims[j, [r for r, w in enumerate(self.pool.words) if w & mine]] = -torch.inf
        return sims.topk(min(self.k, sims.shape[1]), dim=1).indices


for _k in (8, 32):
    CENTRES[f"s16pc{_k}"] = partial(FormNearest, _k, "pc")
    CENTRES[f"s16pcd{_k}"] = partial(FormNearest, _k, "pc", disjoint=True)
    CENTRES[f"s16tb{_k}"] = partial(FormNearest, _k, "tb")
    CENTRES[f"s16pr{_k}"] = partial(FormNearest, _k, "rand")
    CENTRES[f"s16xo{_k}"] = partial(FormNearest, _k, "full", drop_outliers=32)
    CENTRES[f"s16xopc{_k}"] = partial(FormNearest, _k, "pc", drop_outliers=32)


_CARRIERS: dict = {}


def _carrier_of(family: str, item: str) -> str | None:
    if family not in _CARRIERS:
        from jlm import banks

        if family == "mention_control":  # umot's mention bank (u1_mention.py reads it under this family name)
            from umot import mention_control as mc

            _CARRIERS[family] = {it["id"]: it.get("carrier") for it in mc.load()}
        else:
            _CARRIERS[family] = {it["id"]: it.get("carrier") for s in banks.SPLITS for it in _items(banks, family, s)}
    return _CARRIERS[family].get(item)


def _items(banks, family: str, split: str) -> list:
    try:
        return banks.load(family, split).items
    except FileNotFoundError:
        return []


class OtherCarrier(NearestMean):
    """knnx with same-carrier neighbours excluded (see the module doc)."""

    def __init__(self, k: int) -> None:
        super().__init__(k, "bench")
        self.name = f"knnxs{k}"
        self.doc = f"mean of the {k} nearest fit read cells (all families), neighbours sharing the cell's carrier excluded"

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        super().fit(ref, family, groups, ctx)
        if not hasattr(self.pool, "carriers"):  # per pool row: (carrier sentence or None, last 6 context tokens)
            from jlm import banks, capture
            from jlm.mu.clusters import FAMILIES

            rows = []
            for f in FAMILIES:
                for it in capture.load(banks.load(f, "fit")):
                    for i in range(len(it.positions)):
                        rows.append((_carrier_of(f, it.id), tuple(it.decoded[max(0, it.idx[i] - 5): it.idx[i] + 1])))
            assert len(rows) == len(self.pool.groups), "pool row order changed"
            self.pool.carriers = rows

    def _neighbours(self, batch: Batch) -> torch.Tensor:
        L = batch.layer
        X = self.pool.X[L].float()
        U, centre = unit_space(X)
        sims = unit_space(batch.H, centre)[0] @ U.T
        for j, cell in enumerate(batch.cells):
            own = self.pool.rows_of.get(cell.group)
            if own is not None:
                sims[j, own] = -torch.inf
            it = batch.items[cell.item]
            car = _carrier_of(cell.family, cell.item)
            tail = tuple(it.decoded[max(0, it.idx[cell.i] - 5): it.idx[cell.i] + 1])
            key = (car, tail)
            memo = self.__dict__.setdefault("_clash", {})
            if key not in memo:
                memo[key] = [r for r, (c, t) in enumerate(self.pool.carriers) if (car is not None and c == car) or t == tail]
            clash = memo[key]
            if clash:
                sims[j, clash] = -torch.inf
        return sims.topk(min(self.k, len(X)), dim=1).indices


for _k in (8, 32):
    CENTRES[f"knnxs{_k}"] = partial(OtherCarrier, _k)


def _bench_carriers(pool) -> list:
    from jlm import banks, capture
    from jlm.mu.clusters import FAMILIES

    rows = []
    for f in FAMILIES:
        for it in capture.load(banks.load(f, "fit")):
            for i in range(len(it.positions)):
                rows.append((_carrier_of(f, it.id), tuple(it.decoded[max(0, it.idx[i] - 5): it.idx[i] + 1])))
    assert len(rows) == len(pool.groups), "pool row order changed"
    return rows


class WithRef(OtherCarrier):
    """knnx / knnxs over the bench fit pool plus the arm's reference cells (see the module doc)."""

    def __init__(self, k: int, exclude_carrier: bool) -> None:
        super().__init__(k)
        self.exclude = exclude_carrier
        self.name = f"knnx{'s' if exclude_carrier else ''}m{k}"
        self.doc = (f"mean of the {k} nearest cells of the fit read cells plus the reference cells"
                    + (", same-carrier neighbours excluded" if exclude_carrier else ""))

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        from jlm.mu.clusters import Pool, pool

        base = pool(("bench",), Pool.bench_fit)
        if not hasattr(base, "carriers"):
            base.carriers = _bench_carriers(base)
        extra = Pool.of_items(ref, family, groups)
        layers = sorted(set(base.X) & set(extra.X))
        self.pool = Pool({L: torch.cat([base.X[L].float(), extra.X[L].float()]) for L in layers},
                         base.groups + extra.groups, base.fams + extra.fams, base.toks + extra.toks, base.words + extra.words)
        self.pool.carriers = base.carriers + [
            (_carrier_of(family, it.id), tuple(it.decoded[max(0, it.idx[i] - 5): it.idx[i] + 1]))
            for it in ref for i in range(len(it.positions))]
        self.n_fallback = 0
        self.__dict__.pop("_clash", None)

    def _neighbours(self, batch: Batch) -> torch.Tensor:
        if self.exclude:
            return super()._neighbours(batch)
        return NearestMean._neighbours(self, batch)


for _k in (8,):
    CENTRES[f"knnxm{_k}"] = partial(WithRef, _k, False)
    CENTRES[f"knnxsm{_k}"] = partial(WithRef, _k, True)
