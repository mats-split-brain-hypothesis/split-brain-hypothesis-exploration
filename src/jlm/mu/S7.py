"""S7 subspace removal: g(h) = mu + P_B (h - mu) (notes/iteration-anthony/studies/S6.md).

Generalises jle's pco: besides the family mean, remove h's component in a "background" subspace B fitted on the
reference cells (never the read cell's own group). Variants:

- ``pco<k>``: B = the top k principal directions of the family's reference cells at the layer (jle's pco).
- ``pcr<k>``: control, B = a random k-dimensional subspace (seeded per layer), the same mean.
- ``pmu``: g = the projection of h on the family mean's direction (removes the mean's direction at h's own scale,
  instead of the mean itself).
- ``fam50``: g = 0.5 mu (half the family mean): does the harm on multihop come with the mean's full size?

The PCs are fitted per excluded group (leave-one-group-out) when the reference bank is the read bank, once otherwise.
"""

import torch

from jlm.centres import CENTRES, Batch, FamilyMean, TokenMean, cell_refs

OWNER = "Anthony"  # dashboard pickers list these centres under "Anthony's centres" (catalog.owner)
CANDIDATES = ("pco16",)  # dashboard pickers list these under "Anthony's best candidates" (catalog.candidate)


class _RefStates:
    """Reference states per layer, with each cell's group, for leave-one-group-out fits."""

    def fit_states(self, ref, family, groups) -> None:
        self.X: dict[int, torch.Tensor] = {}
        self.G: dict[int, list[str]] = {}
        for layer in sorted({L for it in ref for L in it.acts}):
            rows, gs = [], []
            for it in ref:
                if layer not in it.acts:
                    continue
                for c in cell_refs([it], family, layer, groups):
                    rows.append(it.acts[layer][c.i].float())
                    gs.append(c.group)
            self.X[layer], self.G[layer] = torch.stack(rows), gs

    def others(self, layer: int, group: str) -> torch.Tensor:
        keep = torch.tensor([g != group for g in self.G[layer]])
        return self.X[layer][keep] if not keep.all() else self.X[layer]


class PCRemoval(_RefStates):
    def __init__(self, k: int, random: bool = False, seed: int = 0) -> None:
        self.k, self.random, self.seed = k, random, seed
        self.name = f"{'pcr' if random else 'pco'}{k}"
        self.doc = (f"control: family mean plus a random {k}-dim subspace removed" if random
                    else f"family mean plus its top {k} principal directions removed (own group excluded)")
        self.n_fallback = 0

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.fit_states(ref, family, groups)
        self._cache: dict = {}

    def _basis(self, layer: int, group: str) -> tuple[torch.Tensor, torch.Tensor]:
        X = self.others(layer, group)
        key = (layer, len(X) if len(X) == len(self.X[layer]) else group)
        if key not in self._cache:
            mu = X.double().mean(0)
            if self.random:
                g = torch.Generator().manual_seed(self.seed * 1000 + layer)
                V = torch.linalg.qr(torch.randn(X.shape[1], self.k, generator=g, dtype=torch.float64))[0]
            else:
                with torch.random.fork_rng():  # svd_lowrank draws from the global RNG: seed it
                    torch.manual_seed(layer)
                    _, S, V = torch.svd_lowrank(X.double() - mu, q=min(self.k + 16, *X.shape), niter=4)
                V = V[:, : self.k][:, S[: self.k] > 1e-6 * S[0]]  # fewer cells than k: only real directions
            self._cache[key] = (mu.float(), V.float())
        return self._cache[key]

    def transform(self, batch: Batch) -> torch.Tensor:
        out = torch.empty_like(batch.H)
        for j, c in enumerate(batch.cells):
            mu, V = self._basis(batch.layer, c.group)
            x = batch.H[j] - mu
            out[j] = x - V @ (V.T @ x)
        return out

    def support(self, cell) -> tuple[int, bool]:
        return len(self.others(cell.layer, cell.group)), False


class TokenPCRemoval(PCRemoval):
    """``tpco<k>``: g = mu_tok + V V^T (h - mu_tok), the token mean (``tok``) plus the family's top k principal
    directions (fitted around the family mean, own group excluded) removed from what is left."""

    def __init__(self, k: int) -> None:
        super().__init__(k)
        self.name = f"tpco{k}"
        self.doc = f"token mean plus the family's top {k} principal directions removed (own group excluded)"

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        super().fit(ref, family, groups)
        self.tok = TokenMean()
        self.tok.fit(ref, family, groups)

    def transform(self, batch: Batch) -> torch.Tensor:
        out = torch.empty_like(batch.H)
        for j, c in enumerate(batch.cells):
            _, V = self._basis(batch.layer, c.group)
            x = batch.H[j] - self.tok(c)
            out[j] = x - V @ (V.T @ x)
        self.n_fallback = self.tok.n_fallback
        return out

    def support(self, cell) -> tuple[int, bool]:
        return self.tok.support(cell)


class CrossPCRemoval:
    """``xpco<k>``: g = mu_fam + V V^T (h - mu_fam), V the top k principal directions of the **other** 10 families' fit
    read cells, each centred on its own family's mean. The family's own PCs hold its content axes (e.g. multilingual_mt's
    concept categories, multihop's answer type: studies/S7.md); directions shared across families should hold form
    (position, read token, template) instead. The read family's cells never enter V."""

    FAMILIES = ["typo", "association", "basic_readout", "multihop", "multilingual", "user_modeling",
                "directed_modulation", "typo_mt", "multihop_mt", "basic_readout_mt", "multilingual_mt"]

    def __init__(self, k: int) -> None:
        self.k, self.n_fallback = k, 0
        self.name, self.doc = f"xpco{k}", f"family mean plus the other families' top {k} principal directions removed"

    def _other_states(self, family: str) -> dict[int, list[torch.Tensor]]:
        from jlm import banks, capture

        out: dict[int, list[torch.Tensor]] = {}
        for f in self.FAMILIES:
            if f == family:
                continue
            items = capture.load(banks.load(f, "fit"))
            for layer in sorted({L for it in items for L in it.acts}):
                X = torch.stack([it.acts[layer][i].float() for it in items if layer in it.acts
                                 for i in range(len(it.positions))])
                out.setdefault(layer, []).append(X - X.mean(0))
        return out

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.fam = FamilyMean()
        self.fam.fit(ref, family, groups)
        self.V: dict[int, torch.Tensor] = {}
        for layer, parts in self._other_states(family).items():
            X = torch.cat(parts).double()
            with torch.random.fork_rng():
                torch.manual_seed(layer)
                _, S, V = torch.svd_lowrank(X, q=min(self.k + 16, *X.shape), niter=4, M=None)
            self.V[layer] = V[:, : self.k][:, S[: self.k] > 1e-6 * S[0]].float()

    def transform(self, batch: Batch) -> torch.Tensor:
        V = self.V[batch.layer]
        X = batch.H - torch.stack([self.fam(c) for c in batch.cells])
        return X - (X @ V) @ V.T

    def support(self, cell) -> tuple[int, bool]:
        return self.fam.support(cell)


class MeanDirection:
    """g = (h . u) u with u the family mean's unit direction (own group excluded)."""

    name, doc = "pmu", "projection of h on the family mean's direction (own group excluded)"

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.fam = FamilyMean()
        self.fam.fit(ref, family, groups)
        self.n_fallback = 0

    def transform(self, batch: Batch) -> torch.Tensor:
        U = torch.stack([self.fam(c) for c in batch.cells])
        U = U / U.norm(dim=1, keepdim=True).clamp_min(1e-6)
        return batch.H - (batch.H * U).sum(1, keepdim=True) * U

    def support(self, cell) -> tuple[int, bool]:
        return self.fam.support(cell)


class ScaledMean:
    def __init__(self, a: float) -> None:
        self.a = a
        self.name, self.doc = f"fam{round(a * 100)}", f"{a} x the family mean (own group excluded)"

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.fam = FamilyMean()
        self.fam.fit(ref, family, groups)
        self.n_fallback = 0

    def __call__(self, cell) -> torch.Tensor:
        return self.a * self.fam(cell)

    def support(self, cell) -> tuple[int, bool]:
        return self.fam.support(cell)


for _k in (4, 8, 16, 32, 64):
    CENTRES[f"pco{_k}"] = lambda k=_k: PCRemoval(k)
    CENTRES[f"pcr{_k}"] = lambda k=_k: PCRemoval(k, random=True)
    CENTRES[f"tpco{_k}"] = lambda k=_k: TokenPCRemoval(k)
    CENTRES[f"xpco{_k}"] = lambda k=_k: CrossPCRemoval(k)
CENTRES["pmu"] = MeanDirection
CENTRES["fam50"] = lambda: ScaledMean(0.5)
