"""S4 / U3 variants 1 and 6: cluster means (notes/iteration-anthony/studies/S4.md).

g(h) = the mean of the reference cells in the cluster that h falls in: a mu that depends on h through a
label-free "what kind of position is this", with the family label left out where the pool spans families.

Clustering follows J++'s router (U3 card), without its PCA step: unit-normalise h, centre by the pool's mean unit
vector, k-means (k-means++ init, seed 0, Lloyd to convergence), per layer. The cell is routed to its nearest
centroid in that space; g is the mean of the **raw** states of the cluster's reference cells, with the cell's own
group taken out (an item never centres itself, as in ``KeyedMean``). A cluster left empty by that falls back to the
pool mean without the group.

Pools (the reference cells clustered):
- ``km<k>``: the arm's own reference set (one family; ``@fit`` or ``@self``). ``km1`` is ``fam`` exactly.
- ``kmx<k>``: the read cells of every family's ``fit`` bank, pooled (2.5k cells, half of them user_modeling): no
  family label anywhere in g. ``kmx1`` is the all-family mean.
- ``kmw<k>``: positions 16+ of the wikitext corpus capture (``out/ctx/corpus-wikitext.pt``, 256 x 128 tokens), J++'s
  router data: no bench content in the centroids or the means.
- ``knnx<k>`` / ``knnw<k>``: the mean of the k nearest pool cells (cosine in the same space), the k = n end.
Controls: ``kmxr<k>`` / ``kmwr<k>`` / ``kmr<k>`` route the same way but cluster membership is a seeded permutation
of the fitted labels (same cluster sizes, random members): if they match, the clusters' content is not what helps.

Fairness caveat: with ``@self`` (or ``kmx`` reading a fit bank) the centroids were fitted with the read cell in the
pool, so its own state nudges which cluster it lands in; g itself never contains it. ``val`` reads (pool = fit) are
clean, and confirmation happens there.
"""

import random
import re
from collections import Counter, defaultdict
from functools import partial

import torch

from jlm.centres import CENTRES, Batch, CellRef

OWNER = "Anthony"  # dashboard pickers list these centres under "Anthony's centres" (catalog.owner)
CANDIDATES = ("knnx8",)  # dashboard pickers list these under "Anthony's best candidates" (catalog.candidate)


FAMILIES = ["typo", "association", "basic_readout", "multihop", "multilingual", "user_modeling", "directed_modulation",
            "typo_mt", "multihop_mt", "basic_readout_mt", "multilingual_mt"]
WIKI_SKIP = 16
CHAT_SKIP = 2  # the chat corpus: drop ``<|im_start|>user`` (the first position's massive activation), keep the rest
GPU_ABOVE = 20000  # pools larger than this fit k-means on the GPU when there is one (bench pools stay on CPU)  # J++'s router skips the first 16 positions of each corpus row

_POOLS: dict = {}  # pool key -> Pool (one load per process: evaluate.py reads many banks with the same pool)
_FITS: dict = {}  # (pool key, layer, k, seed) -> (centroids, labels, centre of unit vectors)


class Pool:
    """Reference cells: per layer [N, d] states (float32; bf16 for the corpus, cast per layer on use), with each
    row's group, family and token."""

    def __init__(self, X: dict[int, torch.Tensor], groups: list[str], fams: list[str], toks: list[str],
                 words: list[frozenset] | None = None) -> None:
        self.X, self.groups, self.fams, self.toks = X, groups, fams, toks
        self.words = words or [frozenset()] * len(groups)  # each row's item's prompt words (``prompt_words``)
        gi = defaultdict(list)
        for j, g in enumerate(groups):
            gi[g].append(j)
        self.rows_of = {g: torch.tensor(v) for g, v in gi.items()}

    @classmethod
    def of_items(cls, items, family: str, groups: dict[str, str] | None = None) -> "Pool":
        groups = groups or {}
        X = defaultdict(list)
        gs, fs, ts, ws = [], [], [], []
        for it in items:
            w = prompt_words(it.decoded)
            for i in range(len(it.positions)):
                gs.append(groups.get(it.id, it.id))
                fs.append(family)
                ts.append(it.token(i))
                ws.append(w)
            for L, a in it.acts.items():
                X[L].append(a.float())
        return cls({L: torch.cat(v) for L, v in X.items()}, gs, fs, ts, ws)

    @classmethod
    def bench_fit(cls) -> "Pool":
        from jlm import banks, capture

        parts = []
        for f in FAMILIES:
            bank = banks.load(f, "fit")
            groups = {it["id"]: it.get("pair_id") or it["id"] for it in bank.items}
            parts.append(cls.of_items(capture.load(bank), f, groups))
        layers = set.intersection(*(set(p.X) for p in parts))
        return cls({L: torch.cat([p.X[L] for p in parts]) for L in sorted(layers)},
                   sum((p.groups for p in parts), []), sum((p.fams for p in parts), []), sum((p.toks for p in parts), []),
                   sum((p.words for p in parts), []))

    @classmethod
    def bench_ctx(cls, skip: int = 1) -> "Pool":
        """Every position (from ``skip`` on) of every family's fit render, from the context captures: about 20x the
        read-cell pool, the same items (no new content), so the own-group exclusion applies as for ``bench_fit``."""
        from jlm import banks, context

        X = defaultdict(list)
        gs, fs, ts, ws = [], [], [], []
        for f in FAMILIES:
            bank = banks.load(f, "fit")
            groups = {it["id"]: it.get("pair_id") or it["id"] for it in bank.items}
            for it in context.ContextStore.of(bank).items.values():
                n = len(it.ids) - skip
                if n <= 0:
                    continue
                w = prompt_words(it.decoded)
                gs += [groups.get(it.id, it.id)] * n
                fs += [f] * n
                ts += it.decoded[skip:]
                ws += [w] * n
                for L, a in it.acts.items():
                    X[L].append(a[skip:])
        return cls({L: torch.cat(v) for L, v in X.items()}, gs, fs, ts, ws)

    @classmethod
    def wiki(cls) -> "Pool":
        return cls.corpus("wikitext", WIKI_SKIP, "wiki")

    @classmethod
    def chat(cls) -> "Pool":
        """Every position past the first ``CHAT_SKIP`` of the chat-format corpus (``out/ctx/corpus-chat.pt``,
        no_robots prompts rendered as the bench renders: a label-free pool of chat-template cells, S4 round 2)."""
        return cls.corpus("chat", CHAT_SKIP, "chat")

    @classmethod
    def corpus(cls, name: str, skip: int, tag: str) -> "Pool":
        from jlm import context

        store = context.ContextStore(context.corpus_path(name))
        X = defaultdict(list)
        gs, ts = [], []
        for it in store.items.values():
            n = len(it.ids) - skip
            if n <= 0:
                continue
            gs += [f"{tag}:{it.id}"] * n
            ts += it.decoded[skip:]
            for L, a in it.acts.items():
                X[L].append(a[skip:])
        return cls({L: torch.cat(v) for L, v in X.items()}, gs, [tag] * len(gs), ts)


def prompt_words(decoded) -> frozenset:
    """Lower-cased alphabetic words of 4+ letters in a rendered prompt (for the content-sharing control)."""
    return frozenset(w.lower() for w in re.findall(r"[^\W\d_]{4,}", "".join(decoded).replace("Ġ", " ")))


def pool(key: str, loader) -> Pool:
    if key not in _POOLS:
        _POOLS[key] = loader()
    return _POOLS[key]


def unit_space(X: torch.Tensor, centre: torch.Tensor | None = None) -> tuple[torch.Tensor, torch.Tensor]:
    U = X / X.norm(dim=1, keepdim=True).clamp_min(1e-6)
    if centre is None:
        centre = U.mean(0)
    return U - centre, centre


def kmeans(U: torch.Tensor, k: int, seed: int = 0, iters: int = 200) -> tuple[torch.Tensor, torch.Tensor]:
    """(centroids [k, d], labels [N]) by k-means++ then Lloyd; deterministic for a seed."""
    n = len(U)
    k = min(k, n)
    gen = torch.Generator().manual_seed(seed)
    C = [U[torch.randint(n, (1,), generator=gen).to(U.device)].squeeze(0)]
    d2 = ((U - C[0]) ** 2).sum(1)
    for _ in range(1, k):
        p = (d2 / d2.sum() if d2.sum() > 0 else torch.full((n,), 1.0 / n)).cpu()
        j = torch.multinomial(p, 1, generator=gen).to(U.device)
        C.append(U[j].squeeze(0))
        d2 = torch.minimum(d2, ((U - C[-1]) ** 2).sum(1))
    C = torch.stack(C)
    labels = None
    for _ in range(iters):
        new = torch.cdist(U, C).argmin(1)
        if labels is not None and torch.equal(new, labels):
            break
        labels = new
        for c in range(k):
            m = labels == c
            if m.any():
                C[c] = U[m].mean(0)
    return C, labels


class ClusterMean:
    """g = the raw mean of the reference cells in h's cluster (see the module doc)."""

    def __init__(self, k: int, pool_kind: str, random: bool = False, seed: int = 0) -> None:
        self.k, self.pool_kind, self.random, self.seed = k, pool_kind, random, seed
        stem = {"fam": "km", "bench": "kmx", "wiki": "kmw", "chat": "kmch", "ctx": "kmc"}[pool_kind]
        self.name = f"{stem}{'r' if random else ''}{k}"
        where = {"fam": "the arm's reference cells", "bench": "every family's fit read cells",
                 "wiki": "wikitext positions", "chat": "chat-corpus positions (no_robots renders)",
                 "ctx": "every position of every family's fit renders"}[pool_kind]
        self.doc = (f"mean of h's k-means cluster (k={k}) over {where}, own group excluded"
                    + (" [control: random members, same sizes]" if random else ""))
        self.n_fallback = 0

    def fit(self, ref, family: str, groups: dict[str, str] | None = None, ctx=None) -> None:
        if self.pool_kind == "fam":
            self.key = ("fam", family, tuple(it.id for it in ref))
            self.pool = pool(self.key, lambda: Pool.of_items(ref, family, groups))
        elif self.pool_kind == "bench":
            self.key = ("bench",)
            self.pool = pool(self.key, Pool.bench_fit)
        elif self.pool_kind == "ctx":
            self.key = ("ctx",)
            self.pool = pool(self.key, Pool.bench_ctx)
        elif self.pool_kind == "chat":
            self.key = ("chat",)
            self.pool = pool(self.key, Pool.chat)
        else:
            self.key = ("wiki",)
            self.pool = pool(self.key, Pool.wiki)
        self.n_fallback = 0

    def _layer(self, L: int):
        fk = (self.key, L, self.k, self.seed)
        if fk not in _FITS:
            X = self.pool.X[L]
            dev = "cuda" if len(X) > GPU_ABOVE and torch.cuda.is_available() else "cpu"  # the corpus pool: 30k rows
            U, centre = unit_space(X.to(dev).float())
            C, labels = kmeans(U, self.k, self.seed)
            _FITS[fk] = (C.cpu(), labels.cpu(), centre.cpu())
        C, labels, centre = _FITS[fk]
        if self.random:
            perm = torch.randperm(len(labels), generator=torch.Generator().manual_seed(1000 + self.seed + L))
            labels = labels[perm]
        return C, labels, centre

    def assign(self, H: torch.Tensor, L: int) -> torch.Tensor:
        C, _, centre = self._layer(L)
        return torch.cdist(unit_space(H, centre)[0], C).argmin(1)

    def transform(self, batch: Batch) -> torch.Tensor:
        L = batch.layer
        X = self.pool.X[L].double()
        _, labels, _ = self._layer(L)
        S = torch.zeros(int(labels.max()) + 1, X.shape[1], dtype=torch.float64).index_add_(0, labels, X)
        n = torch.bincount(labels, minlength=len(S)).double()
        total, N = X.sum(0), float(len(X))
        G = torch.empty_like(batch.H)
        for j, (cell, c) in enumerate(zip(batch.cells, self.assign(batch.H, L).tolist(), strict=True)):
            s, m = S[c].clone(), n[c].item()
            tot, nn = total.clone(), N
            own = self.pool.rows_of.get(cell.group)
            if own is not None:
                mine = own[labels[own] == c]
                s -= X[mine].sum(0)
                m -= len(mine)
                tot -= X[own].sum(0)
                nn -= len(own)
            if m > 0:
                G[j] = (s / m).float()
            else:
                self.n_fallback += 1
                G[j] = (tot / nn).float()
        return batch.H - G

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return self.k, False

    def reference(self, layer: int) -> tuple[torch.Tensor, list[tuple[str, str, str]]]:
        return self.pool.X[layer].float(), list(zip(self.pool.groups, self.pool.fams, self.pool.toks, strict=True))

    def members(self, batch: Batch) -> list[torch.Tensor]:
        """Per cell, the pool rows of its cluster without its own group (every other row when that is empty)."""
        _, labels, _ = self._layer(batch.layer)
        out = []
        for cell, c in zip(batch.cells, self.assign(batch.H, batch.layer).tolist(), strict=True):
            keep = torch.ones(len(labels), dtype=torch.bool)
            own = self.pool.rows_of.get(cell.group)
            if own is not None:
                keep[own] = False
            m = keep & (labels == c)
            out.append((m if m.any() else keep).nonzero().squeeze(1))
        return out


class NearestMean:
    """g = the raw mean of the k nearest pool cells to h (cosine in the centred unit space), own group excluded."""

    def __init__(self, k: int, pool_kind: str, disjoint: bool = False, rare: int = 10, cross_token: bool = False,
                 frac: float = 1.0) -> None:
        self.k, self.pool_kind, self.disjoint, self.rare, self.cross_token = k, pool_kind, disjoint, rare, cross_token
        self.frac = frac  # n-scaling: keep this share of the pool's groups (seeded), drop the rest
        tag = "t" if cross_token else "" if not disjoint else ("d" if rare == 10 else f"d{rare}_")
        self.name = f"knn{ {'bench': 'x', 'ctx': 'c', 'wiki': 'w', 'chat': 'ch'}[pool_kind] }{tag}{k}" + (f"s{round(frac * 100)}" if frac < 1 else "")
        self.doc = (f"mean of the {k} nearest { {'bench': 'fit read cells (all families)', 'ctx': 'positions of every family\'s fit renders', 'wiki': 'wikitext positions', 'chat': 'chat-corpus positions (no_robots renders)'}[pool_kind] }, own group excluded"
                    + (f" [control: no neighbour whose prompt shares a rare word (in <= {rare} pool items) with the cell's]" if disjoint else "")
                    + (" [only neighbours whose read token differs from the cell's]" if cross_token else ""))

    fit = ClusterMean.fit
    reference = ClusterMean.reference

    def members(self, batch: Batch) -> list[torch.Tensor]:
        return list(self._neighbours(batch))

    def transform(self, batch: Batch) -> torch.Tensor:
        return batch.H - self.pool.X[batch.layer].float()[self._neighbours(batch)].mean(1)

    def _neighbours(self, batch: Batch) -> torch.Tensor:
        """[n, k] pool rows nearest each cell, after the exclusions."""
        L = batch.layer
        X = self.pool.X[L].float()
        U, centre = unit_space(X)
        Q = unit_space(batch.H, centre)[0]
        sims = Q @ U.T
        if self.frac < 1:
            gs = sorted(self.pool.rows_of)
            keep = set(random.Random(0).sample(gs, max(1, round(self.frac * len(gs)))))
            drop = torch.cat([self.pool.rows_of[g] for g in gs if g not in keep])
            sims[:, drop] = -torch.inf
        if self.disjoint:
            df = Counter(w for g, rows in self.pool.rows_of.items() for w in self.pool.words[int(rows[0])])
            rare = {w for w, n in df.items() if n <= self.rare}
        for j, cell in enumerate(batch.cells):
            own = self.pool.rows_of.get(cell.group)
            if own is not None:
                sims[j, own] = -torch.inf
            if self.cross_token:
                sims[j, [r for r, t in enumerate(self.pool.toks) if t == cell.token]] = -torch.inf
            if self.disjoint:
                mine = prompt_words(batch.items[cell.item].decoded[: batch.items[cell.item].idx[cell.i] + 1]) & rare
                if mine:
                    clash = [r for r, w in enumerate(self.pool.words) if w & mine]
                    sims[j, clash] = -torch.inf
        return sims.topk(min(self.k, len(X)), dim=1).indices

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return self.k, False


for _k in (1, 2, 4, 8, 16):
    CENTRES[f"km{_k}"] = partial(ClusterMean, _k, "fam")
    CENTRES[f"kmr{_k}"] = partial(ClusterMean, _k, "fam", True)
for _k in (1, 4, 8, 11, 16, 32, 64, 128, 256):
    CENTRES[f"kmx{_k}"] = partial(ClusterMean, _k, "bench")
    CENTRES[f"kmxr{_k}"] = partial(ClusterMean, _k, "bench", True)
for _k in (1, 8, 32, 128, 512):
    CENTRES[f"kmw{_k}"] = partial(ClusterMean, _k, "wiki")
    CENTRES[f"kmwr{_k}"] = partial(ClusterMean, _k, "wiki", True)
for _k in (4, 8, 16, 32, 128):
    CENTRES[f"knnx{_k}"] = partial(NearestMean, _k, "bench")
    CENTRES[f"knnxd{_k}"] = partial(NearestMean, _k, "bench", True)  # rare = in <= 10 pool items (catches question words)
    CENTRES[f"knnxd2_{_k}"] = partial(NearestMean, _k, "bench", True, 2)  # idiosyncratic words only (<= 2 items)
    CENTRES[f"knnxt{_k}"] = partial(NearestMean, _k, "bench", cross_token=True)  # neighbours with another read token
for _k in (8, 32):  # every position of the fit renders as the pool
    CENTRES[f"knnc{_k}"] = partial(NearestMean, _k, "ctx")
for _k in (1, 8, 32, 128):  # the chat-format corpus as the pool (S4 round 2: a label-free pool of chat-template cells)
    CENTRES[f"kmch{_k}"] = partial(ClusterMean, _k, "chat")
    CENTRES[f"kmchr{_k}"] = partial(ClusterMean, _k, "chat", True)
for _k in (8, 32):
    CENTRES[f"knnch{_k}"] = partial(NearestMean, _k, "chat")
for _f in (0.1, 0.25, 0.5):  # n-scaling of knnx8's pool
    CENTRES[f"knnx8s{round(_f * 100)}"] = partial(NearestMean, 8, "bench", frac=_f)
    CENTRES[f"knnw{_k}"] = partial(NearestMean, _k, "wiki")


class Direction:
    """U3 variant 5, router geometry as g. ``mode="scale"``: g = ||h|| * mean unit vector of h's cluster (the
    direction-only counterfactual, norm taken from the cell; ``kdir``). ``mode="proj"``: g = (h . m) m with m that
    direction normalised: remove h's component along its regime's mean direction only (a one-direction S7; ``kproj``).
    Clusters as ``ClusterMean`` (bench fit pool); the mean direction leaves out the cell's own group."""

    def __init__(self, k: int, mode: str) -> None:
        self.k, self.mode = k, mode
        self.name = f"{'kdir' if mode == 'scale' else 'kproj'}{k}"
        self.doc = (f"{'||h|| times' if mode == 'scale' else 'projection of h on'} the mean unit direction of h's "
                    f"k-means cluster (k={k}) over every family's fit read cells, own group excluded")
        self.inner = ClusterMean(k, "bench")

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.inner.fit(ref, family, groups, ctx)
        self.pool = self.inner.pool

    def transform(self, batch: Batch) -> torch.Tensor:
        L = batch.layer
        X = self.pool.X[L].double()
        Xu = X / X.norm(dim=1, keepdim=True).clamp_min(1e-9)
        _, labels, _ = self.inner._layer(L)
        S = torch.zeros(int(labels.max()) + 1, X.shape[1], dtype=torch.float64).index_add_(0, labels, Xu)
        G = torch.empty_like(batch.H)
        for j, (cell, c) in enumerate(zip(batch.cells, self.inner.assign(batch.H, L).tolist(), strict=True)):
            s = S[c].clone()
            own = self.pool.rows_of.get(cell.group)
            if own is not None:
                s -= Xu[own[labels[own] == c]].sum(0)
            m = (s / s.norm().clamp_min(1e-9)).float()
            h = batch.H[j]
            G[j] = h.norm() * m if self.mode == "scale" else (h @ m) * m
        return batch.H - G

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return self.k, False


for _k in (1, 64):
    CENTRES[f"kdir{_k}"] = partial(Direction, _k, "scale")
    CENTRES[f"kproj{_k}"] = partial(Direction, _k, "proj")


class Blend:
    """g = a * g_knnx8 + (1 - a) * g_kmx64: how much of kNN's tightness to keep (``blend<100a>``), a chosen on fit."""

    def __init__(self, a: float) -> None:
        self.a = a
        self.name = f"blend{round(a * 100)}"
        self.doc = f"{a:g} x (mean of the 8 nearest fit read cells) + {1 - a:g} x (kmx64 cluster mean)"
        self.knn, self.km = NearestMean(8, "bench"), ClusterMean(64, "bench")

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.knn.fit(ref, family, groups, ctx)
        self.km.fit(ref, family, groups, ctx)

    def transform(self, batch: Batch) -> torch.Tensor:
        return self.a * self.knn.transform(batch) + (1 - self.a) * self.km.transform(batch)

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return 8, False


for _a in (0.25, 0.5, 0.75):
    CENTRES[f"blend{round(_a * 100)}"] = partial(Blend, _a)


class SharedRoute(ClusterMean):
    """``kmxs<k>``: one routing for every layer. Clusters and the cell's assignment come from layer ``route`` (L44);
    g at layer l is the mean at l of the reference cells sharing that L44 cluster. Tests whether a regime is a property
    of the position rather than of each layer's state."""

    def __init__(self, k: int, route: int = 44) -> None:
        super().__init__(k, "bench")
        self.route = route
        self.name, self.doc = f"kmxs{k}", f"mean at each layer of the cell's L{route} k-means cluster (k={k}, all fit read cells)"

    def transform(self, batch: Batch) -> torch.Tensor:
        L = batch.layer
        _, labels, _ = self._layer(self.route)
        Hr = torch.stack([batch.items[c.item].acts[self.route][c.i].float() for c in batch.cells])
        assign = self.assign(Hr, self.route).tolist()
        X = self.pool.X[L].double()
        S = torch.zeros(int(labels.max()) + 1, X.shape[1], dtype=torch.float64).index_add_(0, labels, X)
        n = torch.bincount(labels, minlength=len(S)).double()
        G = torch.empty_like(batch.H)
        for j, (cell, c) in enumerate(zip(batch.cells, assign, strict=True)):
            s, m = S[c].clone(), n[c].item()
            own = self.pool.rows_of.get(cell.group)
            if own is not None:
                mine = own[labels[own] == c]
                s -= X[mine].sum(0)
                m -= len(mine)
            G[j] = (s / m).float() if m > 0 else X.mean(0).float()
        return batch.H - G


for _k in (16, 64):
    CENTRES[f"kmxs{_k}"] = partial(SharedRoute, _k)


class ClusterPCO(ClusterMean):
    """``kpc<kc>_<kp>``: S7's pco with the family replaced by a label-free regime: g = mu_c + V V^T (h - mu_c), where c is
    h's bench-pool k-means cluster (kc clusters), mu_c its mean and V its top kp principal directions, both fitted
    without the cell's own group (seeded ``svd_lowrank``, q = kp + 16, as S7)."""

    def __init__(self, kc: int, kp: int) -> None:
        super().__init__(kc, "bench")
        self.kp = kp
        self.name = f"kpc{kc}_{kp}"
        self.doc = (f"mean of h's k-means cluster (k={kc}, all fit read cells) plus h's projection on that cluster's top "
                    f"{kp} principal directions, own group excluded")
        self._basis: dict = {}

    def basis(self, L: int, c: int, group: str, X: torch.Tensor, labels: torch.Tensor):
        key = (L, c, group)
        if key not in self._basis:
            m = labels == c
            own = self.pool.rows_of.get(group)
            if own is not None:
                m[own] = False
            Xc = X[m].double()
            mu = Xc.mean(0) if len(Xc) else X.double().mean(0)
            if len(Xc) > 2:
                with torch.random.fork_rng():
                    torch.manual_seed(1000 * L + c)
                    _, _, V = torch.svd_lowrank(Xc - mu, q=min(self.kp + 16, *Xc.shape), niter=4)
                V = V[:, : self.kp]
            else:
                V = torch.zeros(X.shape[1], 0, dtype=torch.float64)
            self._basis[key] = (mu.float(), V.float())
        return self._basis[key]

    def transform(self, batch: Batch) -> torch.Tensor:
        L = batch.layer
        X = self.pool.X[L].float()
        _, labels, _ = self._layer(L)
        G = torch.empty_like(batch.H)
        for j, (cell, c) in enumerate(zip(batch.cells, self.assign(batch.H, L).tolist(), strict=True)):
            mu, V = self.basis(L, c, cell.group, X, labels)
            r = batch.H[j] - mu
            G[j] = mu + V @ (V.T @ r)
        return batch.H - G


for _kc, _kp in ((16, 8), (16, 16), (64, 4)):
    CENTRES[f"kpc{_kc}_{_kp}"] = partial(ClusterPCO, _kc, _kp)
