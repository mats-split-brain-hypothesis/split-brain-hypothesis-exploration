"""Readout-space geometry of the lens: pull vocabulary-space vectors back into the residual stream, the lens's
reading directions for chosen tokens, and the singular structure of ``J_l`` (round-2 cards S13, S14, S15).

The centred readout is linear, ``L(h - g) = L(h) - L(g)``, so any change ``c`` to the scores that lies in the column
space of the readout map ``M_l`` is realised by some ``g``: choosing ``c`` in vocabulary space and pulling it back
(``g = M_l^+ c``) is a way to construct a centre from a *principle* (a prior over tokens) instead of from reference
cells. The maps, per layer and readout (``jlm.lens``):

- ``rms``: ``M_l = W_U J_l`` (the rms normalisation is a per-cell rescale, so only the direction of ``J(h - g)``
  matters; ``g`` is pulled back up to scale and the arm's ``beta`` sets it);
- ``cos``: ``M_l = D_l^{-1} W_U J_l`` with ``D_l = diag(||J_l^T W_U[t]||)`` (the bench's denominators).

``g = argmin ||P (M_l g - c)||^2 + ridge ||g||^2`` with ``P = I - 1 1^T / V`` (a constant added to every token's
score changes no rank, so the fit ignores it), through the normal equations: ``A_l g = b`` with
``A_l = J^T G_l J``, ``G_l = W^T W - V m m^T`` for ``W = D_l^{-1} W_U`` (cos) or ``W_U`` (rms) and ``m`` the mean row of
``W``, and ``b = J^T W^T (c - mean(c))``. ``A_l`` is d x d, so the pseudo-inverse is an eigendecomposition per layer,
cached; the only pass over the 248k x 5120 ``W_U`` per pullback is the right-hand side, batched over many ``c`` at
once. ``rank`` keeps the top eigen-directions of ``A_l`` only (the directions the readout can actually move; the rest
are ridge-dominated noise).

Everything heavy is cached under ``out/lens`` keyed by the lens pin, like the cos denominators, so that a centre at
evaluation time loads small tensors (``out/priors/pullback/...``, ``out/lens/tbasis-...``, ``out/lens/jsvd-...``)
and never ``W_U``. ``experiments/precompute_pullback.py`` fills the caches on a machine that can hold the lens.
"""

from pathlib import Path

import torch

from jlm import OUT
from jlm.lens import Lens, reader

CACHE = OUT / "lens"
PRIORS = OUT / "priors"
PULLBACK = PRIORS / "pullback"
CHUNK = 16384  # vocabulary rows per pass over W_U


def lens_key(lens: Lens) -> str:
    """Eight hex characters identifying the map (its HF pin, or a local map's content hash), as the denominator cache."""
    return lens.name if lens.identity else reader(lens.name)[1][:8] if lens.repo else f"{lens.name}-{reader(lens.name)[1][7:15]}"


def centre_scores(c: torch.Tensor) -> torch.Tensor:
    """Remove each row's mean over the vocabulary: a constant added to every token's score changes no rank, so the
    pullback should not spend its budget on it."""
    return c - c.mean(dim=-1, keepdim=True)


class Geometry:
    """Pullbacks, reading bases and ``J``'s SVD for one loaded lens. Each method caches its heavy factor on disk."""

    def __init__(self, lens: Lens, cache: Path = CACHE) -> None:
        self.lens, self.cache = lens, cache
        self.key = lens_key(lens)
        self.d = lens.w_u.shape[1]
        self.cache.mkdir(parents=True, exist_ok=True)

    # -- grams and their eigendecompositions ------------------------------------------------------------------

    def _wu_gram(self, layer: int | None, readout: str) -> torch.Tensor:
        """``G = W^T P W = W^T W - V m m^T`` for ``W = W_U`` (rms; one per model) or ``D_l^{-1} W_U`` (cos; one per
        layer), ``m`` the mean row of ``W``: the gram of the readout map with the constant-score direction projected
        out. fp64 [d, d], cached."""
        path = (self.cache / "wu-gram-rms.pt" if readout == "rms"
                else self.cache / f"wu-gram-cos-{self.key}-L{layer:03d}.pt")
        if path.exists():
            return torch.load(path)
        W = self.lens.w_u
        inv = None if readout == "rms" else (1.0 / self.lens.denom[layer]).to(W.device)
        G = torch.zeros(self.d, self.d, dtype=torch.float64, device=W.device)
        s = torch.zeros(self.d, dtype=torch.float64, device=W.device)
        for i in range(0, W.shape[0], CHUNK):
            w = W[i : i + CHUNK]
            if inv is not None:
                w = w * inv[i : i + CHUNK, None]
            G += (w.T @ w).double()
            s += w.double().sum(0)
        G = (G - torch.outer(s, s) / W.shape[0]).cpu()
        torch.save(G, path)
        return G

    def gram(self, layer: int, readout: str) -> torch.Tensor:
        """``A_l = J_l^T G J_l`` fp64 [d, d] (the identity map: ``G`` itself)."""
        G = self._wu_gram(layer, readout)
        if self.lens.identity:
            return G
        J = self.lens.jac[layer].double().cpu()
        return J.T @ G @ J

    def eig(self, layer: int, readout: str) -> tuple[torch.Tensor, torch.Tensor]:
        """Eigenvalues (descending, fp64 [d]) and eigenvectors (fp32 [d, d], columns) of ``A_l``, cached."""
        path = self.cache / f"pb-eig-{self.key}-{readout}-L{layer:03d}.pt"
        if path.exists():
            obj = torch.load(path)
            return obj["evals"], obj["evecs"]
        lam, Q = torch.linalg.eigh(self.gram(layer, readout))
        lam, Q = lam.flip(0).clamp_min(0.0), Q.flip(1)
        torch.save({"evals": lam, "evecs": Q.float()}, path)
        return lam, Q.float()

    # -- right-hand sides and pullbacks ---------------------------------------------------------------------

    def rhs(self, C: torch.Tensor, layer: int, readout: str) -> torch.Tensor:
        """``b = J^T W_U^T D^{-1} c`` for each row of ``C`` [m, V] -> [m, d] fp32 (one pass over ``W_U``)."""
        W = self.lens.w_u
        C = C.to(W.device, torch.float32)
        if readout == "cos":
            C = C / self.lens.denom[layer].to(W.device)
        B = torch.zeros(C.shape[0], self.d, dtype=torch.float64, device=W.device)
        for i in range(0, W.shape[0], CHUNK):
            B += (C[:, i : i + CHUNK] @ W[i : i + CHUNK]).double()
        if not self.lens.identity:
            B = B @ self.lens.jac[layer].double()
        return B.float().cpu()

    def solve(self, B: torch.Tensor, layer: int, readout: str, *, ridge: float = 1e-4, rank: int | None = None) -> torch.Tensor:
        """``g`` [m, d] from right-hand sides ``B`` [m, d]: ``Q diag(1 / (lam + ridge * mean(lam))) Q^T b`` over the top
        ``rank`` eigen-directions (all of them when ``rank`` is None)."""
        lam, Q = self.eig(layer, readout)
        k = lam.numel() if rank is None else min(rank, lam.numel())
        lam, Q = lam[:k].float(), Q[:, :k]
        inv = 1.0 / (lam + ridge * lam.mean())
        return ((B @ Q) * inv) @ Q.T

    def pullback(self, C: torch.Tensor, layer: int, readout: str, *, ridge: float = 1e-4, rank: int | None = None) -> torch.Tensor:
        """``g`` [m, d] whose readout change ``L(g)`` best matches each (mean-centred) row of ``C`` [m, V]."""
        return self.solve(self.rhs(centre_scores(C), layer, readout), layer, readout, ridge=ridge, rank=rank)

    def fit_quality(self, C: torch.Tensor, G: torch.Tensor, layer: int, readout: str) -> torch.Tensor:
        """Per row, ``||a L(g) - c|| / ||c||`` with ``c`` mean-centred and ``a`` the least-squares scale: 0 is an exact
        pullback (up to scale), 1 is none at all. The scale matters for rms, whose readout normalises ``J g`` to a
        fixed rms so ``L(g)`` cannot match ``c``'s size; for cos ``a`` is close to 1 when the fit is good."""
        c = centre_scores(C.float())
        Lg = centre_scores(self.lens.scores(G, layer, readout).cpu())
        a = ((Lg * c).sum(1) / (Lg * Lg).sum(1).clamp_min(1e-12)).unsqueeze(1)
        return (a * Lg - c).norm(dim=1) / c.norm(dim=1).clamp_min(1e-12)

    # -- reading directions and J's spectrum ----------------------------------------------------------------

    def reading_rows(self, ids: list[int], layer: int, readout: str) -> torch.Tensor:
        """The lens's reading direction of each token, ``J^T W_U[t]`` (over ``||J^T W_U[t]||`` for cos) [k, d]."""
        R = self.lens.w_u[ids].float()
        if not self.lens.identity:
            R = R @ self.lens.jac[layer]
        if readout == "cos":
            R = R / self.lens.denom[layer][ids, None]
        return R.cpu()

    def reading_basis(self, ids: list[int], layer: int, readout: str) -> torch.Tensor:
        """An orthonormal basis [d, k'] of the span of the reading directions of ``ids`` (k' <= k: dependent rows
        dropped at 1e-6 of the largest singular value)."""
        R = self.reading_rows(ids, layer, readout).double()
        U, S, _ = torch.linalg.svd(R.T, full_matrices=False)
        keep = S > 1e-6 * S[0]
        return U[:, keep].float()

    def jsvd(self, layer: int) -> tuple[torch.Tensor, torch.Tensor]:
        """Singular values (descending, fp32 [d]) and right singular vectors (fp32 [d, d], rows) of ``J_l``: ``V[i]``
        is the i-th most amplified input direction. Cached."""
        path = self.cache / f"jsvd-{self.key}-L{layer:03d}.pt"
        if path.exists():
            obj = torch.load(path)
            return obj["S"], obj["Vh"]
        if self.lens.identity:
            S, Vh = torch.ones(self.d), torch.eye(self.d)
        else:
            _, S, Vh = torch.linalg.svd(self.lens.jac[layer].double().cpu())
            S, Vh = S.float(), Vh.float()
        torch.save({"S": S, "Vh": Vh}, path)
        return S, Vh


# -- what the centres load (no lens needed) -----------------------------------------------------------------------


def prior_path(prior: str, readout: str, rank: str | int) -> Path:
    """``out/priors/pullback/<prior>-<readout>-r<rank>.pt``: ``{"layers": {L: g [d]}, "meta": {...}}``."""
    return PULLBACK / f"{prior}-{readout}-r{rank}.pt"


def cells_path(family: str, split: str, readout: str, rank: str | int) -> Path:
    """Per-cell pullbacks of a bank: ``{"cells": [(item, i)], "layers": {L: [n_cells, d]}, "meta": {...}}``."""
    return PULLBACK / f"nt-{family}-{split}-{readout}-r{rank}.pt"


def tbasis_path(key: str, readout: str, token_set: str, k: int, layer: int) -> Path:
    return CACHE / f"tbasis-{key}-{readout}-{token_set}-k{k}-L{layer:03d}.pt"


def jsvd_path(key: str, layer: int) -> Path:
    return CACHE / f"jsvd-{key}-L{layer:03d}.pt"


def load_prior(prior: str, readout: str, rank: str | int = "full") -> dict:
    path = prior_path(prior, readout, rank)
    if not path.exists():
        raise FileNotFoundError(f"no pulled-back prior at {path}; run experiments/precompute_pullback.py --priors {prior}")
    return torch.load(path, weights_only=False)


def load_cells(family: str, split: str, readout: str, rank: str | int = "full") -> dict:
    path = cells_path(family, split, readout, rank)
    if not path.exists():
        raise FileNotFoundError(f"no per-cell pullbacks at {path}; run experiments/precompute_pullback.py --next-token {family}/{split}")
    return torch.load(path, weights_only=False)


def load_tbasis(key: str, readout: str, token_set: str, k: int, layer: int) -> torch.Tensor:
    path = tbasis_path(key, readout, token_set, k, layer)
    if not path.exists():
        raise FileNotFoundError(f"no template basis at {path}; run experiments/precompute_pullback.py --template-tokens")
    return torch.load(path)


def load_jsvd(key: str, layer: int) -> tuple[torch.Tensor, torch.Tensor]:
    path = jsvd_path(key, layer)
    if not path.exists():
        raise FileNotFoundError(f"no SVD of J at {path}; run experiments/precompute_pullback.py --jsvd")
    obj = torch.load(path)
    return obj["S"], obj["Vh"]


def default_key() -> str:
    """The released 27B J-lens's key (``LENSES['jlens']`` pin), the only map centres are read through."""
    return reader("jlens")[1][:8]
