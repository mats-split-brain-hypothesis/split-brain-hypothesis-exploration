"""M1 (round 4, night-3): generic whitening with a data-free covariance, and the circuit's shared infrastructure.

Shared infrastructure (mu-log, "Shared infrastructure for the circuit"; B and C import from here):

- ``pool(name, family, layer)`` -> [N, d] float32: the generic reference cells of a pool at one layer. Pools come from
  the reference captures in ``out/captures`` (x14 / x24, model-written or minimal texts, no bench item):
  ``glosnone`` (``glos-none-*``), ``mwiki``, ``wshort``, ``mcut`` (x24's sets), ``nullp`` (``null-*``), ``uncond``
  (``uncond-*``), ``wiki`` (``corpus8``, a seeded sample of 2048 wikitext cells, every position from 8 on). For a
  plain-render family (every family but user_modeling and directed_modulation, the _mt ones included) a pool is the
  five plain families' captures stacked (one pool, no family dependence; 320 cells for ``glosnone``); for the two
  chat-render families it is the family's own ``glos-none-<family>`` (``nullp`` / ``uncond``: their own file) capture,
  since the render is visible from the prompt. ``pool_mean`` is mu_0, the data-free constant (``glosnone`` on the plain
  render = x14's ``glosall:none`` over the plain families).
- ``metric(layer, readout)`` -> (evals [d] fp64, evecs [d, d] fp32): the readout gram ``A_l = J^T G J = Q diag(lam) Q^T``
  from the cached eigendecompositions (``out/lens/pb-eig-<key>-<readout>-L<layer>.pt``), no ``W_U``.

Centres (``m1:<pool>:<lam>[:flags]``):

``GenericWhitening`` reads ``x = (h - mu_0) + sum_i (s_i - 1) u_i u_i^T (h - mu_0)`` with ``(u_i, ev_i)`` the eigenpairs of
the pool's covariance about its mean mu_0, ``s_i = sqrt(lam_abs / (ev_i + lam_abs))``, ``lam_abs = lam tr(C) / d``
(jle x90f's ``whitened``: lam -> infinity (``inf``) is the plain constant, lam -> 0 removes the pool's span; directions
outside the span are untouched). Flags: ``r`` / ``r-rms`` the readout-metric variant (``m1r``: the PCA of
``A^{1/2}(h - mu_0)``, mapped back through the pool's span, i.e. an A-oblique soft projection), ``rnd`` the same gains
on a random orthonormal basis of the same dimension (``m1rnd``), ``evshuf`` the gains permuted across the axes,
``n<k>`` a seeded subsample of k pool cells. ``m1:fam:<lam>`` whitens with the arm's own reference cells (the
read family's, own group left out: jle's ``wht``), the labelled ceiling of the class, never a method.
"""

import os
from functools import lru_cache
from pathlib import Path

import torch
from umot.capture import ItemCapture

from jlm import OUT
from jlm.centres import PARAMETRIC, Batch, CellRef, cell_refs

PLAIN = ("typo", "association", "basic_readout", "multihop", "multilingual")
CHAT = ("user_modeling", "directed_modulation")
#: banks read in another family's render (umot's mention-control banks are built from the DM pairs: DM's chat render)
RENDER_AS = {"mention_control": "directed_modulation", "mention_many": "directed_modulation"}
#: pool name -> capture prefix (``<prefix>-<family>.pt``)
PREFIX = {"glosnone": "glos-none", "mwiki": "glos-mwiki", "wshort": "glos-wshort", "mcut": "glos-mcut",
          "nullp": "null", "uncond": "uncond"}
WIKI_N = 2048
#: where the generic captures are read from (a pod may hold them on its local disk: JLM_M1_CAPTURES)
CAPS = Path(os.environ.get("JLM_M1_CAPTURES") or OUT / "captures")
#: (pool, render, layer, metric, n, seed) -> the pool's factors, shared by every arm of a process
_FACTORS: dict = {}


def render(family: str) -> str:
    return "chat" if RENDER_AS.get(family, family) in CHAT else "plain"


#: pools stacked from several x24 sets (M1n): the chat render keeps its own glos-none capture
STACKS = {"gen3": ("glosnone", "mwiki", "wshort")}


def _files(name: str, family: str) -> list[str]:
    family = RENDER_AS.get(family, family)
    if name in STACKS:
        return list(dict.fromkeys(f for part in STACKS[name] for f in _files(part, family)))
    if render(family) == "chat":
        own = f"{PREFIX.get(name, 'glos-none')}-{family}.pt"
        # x24's sets exist for the plain families only; the chat render keeps its own glos-none capture
        return [own if (CAPS / own).exists() else f"glos-none-{family}.pt"]
    return [f"{PREFIX[name]}-{f}.pt" for f in PLAIN]


@lru_cache(maxsize=32)
def _capture_rows(fname: str) -> dict[int, torch.Tensor]:
    from umot import capture as ucap

    items = ucap.load(CAPS / fname)
    layers = sorted({L for it in items for L in it.acts})
    return {L: torch.cat([it.acts[L].float() for it in items if L in it.acts]) for L in layers}


@lru_cache(maxsize=2)
def _wiki_rows() -> dict[int, torch.Tensor]:
    from jlm.mu.constant_mu import _corpus_sample

    return _corpus_sample(n=WIKI_N)


def pool(name: str, family: str, layer: int) -> torch.Tensor:
    """[N, d] float32: the generic reference cells of pool ``name`` for a cell of ``family`` at ``layer``."""
    if name == "wiki":
        return _wiki_rows()[layer]
    return torch.cat([_capture_rows(f)[layer] for f in _files(name, family)])


def pool_mean(name: str, family: str, layer: int) -> torch.Tensor:
    """mu_0 [d] float32: the pool's mean, the data-free constant of the circuit."""
    return pool(name, family, layer).double().mean(0).float()


@lru_cache(maxsize=4)
def _metric(layer: int, readout: str) -> tuple[torch.Tensor, torch.Tensor]:
    from jlm import pullback

    try:
        key = pullback.default_key()
    except Exception:  # no HF metadata on this machine: the released 27B J-lens's cached key
        key = "a4114d77"
    obj = torch.load(OUT / "lens" / f"pb-eig-{key}-{readout}-L{layer:03d}.pt")
    return obj["evals"], obj["evecs"]


def metric(layer: int, readout: str) -> tuple[torch.Tensor, torch.Tensor]:
    """The readout gram ``A_l = Q diag(lam) Q^T`` (lam fp64 [d] descending, Q fp32 [d, d] columns), no ``W_U``."""
    return _metric(layer, readout)


def metric_sqrt_apply(X: torch.Tensor, layer: int, readout: str, power: float = 0.5) -> torch.Tensor:
    """Rows of ``X`` times ``A^power`` (A symmetric): ``X Q diag(lam^power) Q^T``, float64 [n, d]."""
    lam, Q = metric(layer, readout)
    Q = Q.double()
    return ((X.double() @ Q) * lam.clamp_min(0).pow(power)) @ Q.T


def whiten_gains(ev: torch.Tensor, lam: float, d: int) -> torch.Tensor:
    """``s_i - 1`` for eigenvalues ``ev`` of a covariance on its span; ``lam`` relative to the mean eigenvalue."""
    if lam == float("inf"):
        return torch.zeros_like(ev)
    lam_abs = lam * ev.sum() / d
    return torch.sqrt(lam_abs / (ev + lam_abs)) - 1.0


def pca(X: torch.Tensor, tol: float = 1e-9) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """(mean [d], eigenvalues [k] of the covariance on its span, directions [k, d]) of the rows of X, fp64."""
    X = X.double()
    mu = X.mean(0)
    _u, sv, Vh = torch.linalg.svd(X - mu, full_matrices=False)
    ev = sv.square() / X.shape[0]
    keep = ev > tol * ev.max().clamp_min(1e-300)
    return mu, ev[keep], Vh[keep]


def _random_basis(k: int, d: int, seed: int) -> torch.Tensor:
    g = torch.Generator().manual_seed(seed)
    Qr, _ = torch.linalg.qr(torch.randn(d, k, generator=g, dtype=torch.float64))
    return Qr.T.contiguous()


class GenericWhitening:
    """``m1:<pool>:<lam>[:r|:r-rms][:rnd][:evshuf][:n<k>]`` (module doc)."""

    def __init__(self, pool_name: str, lam: float, *, metric: str | None = None, rnd: bool = False,
                 evshuf: bool = False, n: int | None = None, seed: int = 0, name: str | None = None) -> None:
        self.pool_name, self.lam, self.metric, self.rnd, self.evshuf, self.n, self.seed = pool_name, lam, metric, rnd, evshuf, n, seed
        self.name = name or f"m1:{pool_name}:{lam:g}"
        what = "the read family's reference cells (own group left out; labelled ceiling)" if pool_name == "fam" else f"the {pool_name} generic pool"
        self.doc = (f"whiten h - mu_0 along the covariance of {what}, lam {lam:g}"
                    + (f" in the {metric} readout metric" if metric else "")
                    + ("; control: random orthonormal basis" if rnd else "")
                    + ("; control: eigenvalues shuffled across axes" if evshuf else "")
                    + (f"; {n} pool cells" if n else ""))
        self._ops: dict = {}

    # -- fitting -----------------------------------------------------------------------------------------------

    def fit(self, ref: list[ItemCapture], family: str, groups: dict[str, str] | None = None, ctx=None) -> None:
        self.family, self._ops = family, {}
        if self.pool_name == "fam":
            self._ref, self._groups = ref, groups or {}

    def _pool_rows(self, layer: int) -> torch.Tensor:
        X = pool(self.pool_name, self.family, layer)
        if self.n and self.n < len(X):
            pick = torch.randperm(len(X), generator=torch.Generator().manual_seed(self.seed * 1000 + layer))[: self.n]
            X = X[pick]
        return X

    def _factors(self, layer: int):
        """(mu_0, eigenvalues, left, right) of the pool at ``layer``, before the gains (shared across arms)."""
        X = self._pool_rows(layer).double()
        if self.metric is None:
            mu, ev, V = pca(X)
            return mu, ev, V, V
        mu = X.mean(0)
        Z = X - mu
        Y = metric_sqrt_apply(Z, layer, self.metric)
        U, sv, _ = torch.linalg.svd(Y, full_matrices=False)
        ev = sv.square() / X.shape[0]
        keep = ev > 1e-9 * ev.max()
        U, sv, ev = U[:, keep], sv[keep], ev[keep]
        left = (Z.T @ U / sv).T
        return mu, ev, left, metric_sqrt_apply(left, layer, self.metric, power=1.0)

    def op(self, layer: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """(mu_0 [d], gains [k], left [k, d], right [k, d]) fp64: read ``x + ((x right^T) * gains) left`` for
        ``x = h - mu_0``. Euclidean: left = right = the pool's principal directions. Readout metric: with
        ``Y = Z A^{1/2} = U S V^T`` (Z the centred pool rows), left_i = Z^T U_i / S_i (= A^{-1/2} v_i, in the pool's
        span) and right_i = A Z^T U_i / S_i (= A^{1/2} v_i)."""
        if layer in self._ops:
            return self._ops[layer]
        key = (self.pool_name, render(self.family), layer, self.metric, self.n, self.seed)
        if key not in _FACTORS:
            _FACTORS[key] = self._factors(layer)
        mu, ev, left, right = _FACTORS[key]
        d = len(mu)
        gains = whiten_gains(ev, self.lam, d)
        if self.evshuf:
            gains = gains[torch.randperm(len(gains), generator=torch.Generator().manual_seed(self.seed * 1000 + layer + 7))]
        if self.rnd:
            left = right = _random_basis(len(gains), d, self.seed * 1000 + layer)
        self._ops[layer] = (mu, gains, left, right)
        return self._ops[layer]

    # -- reading -----------------------------------------------------------------------------------------------

    def transform(self, batch: Batch) -> torch.Tensor:
        if self.pool_name == "fam":
            return self._transform_fam(batch)
        mu, gains, left, right = self.op(batch.layer)
        x = batch.H.double() - mu
        return (x + ((x @ right.T) * gains) @ left).float()

    def _transform_fam(self, batch: Batch) -> torch.Tensor:
        """jle's ``wht`` with the item's own group left out, exactly, in the n-dimensional row space: per group the
        centred Gram of the remaining rows gives the covariance's eigenpairs."""
        layer = batch.layer
        refs = [it for it in self._ref if layer in it.acts]
        rows = cell_refs(refs, self.family, layer, self._groups)
        by_id = {it.id: it for it in refs}
        R = torch.stack([by_id[c.item].acts[layer][c.i] for c in rows]).double()  # [n, d]
        g_rows = [c.group for c in rows]
        K = R @ R.T
        HR = batch.H.double() @ R.T  # [b, n]
        out = torch.empty_like(batch.H, dtype=torch.float64)
        d = R.shape[1]
        for grp in dict.fromkeys(c.group for c in batch.cells):
            keep = torch.tensor([g != grp for g in g_rows])
            idx = torch.nonzero(keep).squeeze(1)
            m = len(idx)
            Ks = K[idx][:, idx]
            rbar = Ks.mean(0)
            Kc = Ks - rbar[None, :] - rbar[:, None] + rbar.mean()  # centred Gram of the remaining rows
            w, U = torch.linalg.eigh(Kc)
            ok = w > 1e-9 * w.max()
            w, U = w[ok], U[:, ok]
            ev = w / m
            gains = whiten_gains(ev, self.lam, d)
            mu = R[idx].mean(0)
            sel = torch.tensor([c.group == grp for c in batch.cells])
            x = batch.H[sel].double() - mu
            # x . v_i with v_i = Zc^T U_i / sqrt(w_i), Zc = R[idx] - mu
            xz = HR[sel][:, idx] - (batch.H[sel].double() @ mu)[:, None] - (R[idx] @ mu)[None, :] + mu @ mu
            coef = (xz @ U) / w.sqrt()
            V = ((R[idx] - mu).T @ U / w.sqrt()).T  # [k, d]
            out[sel] = x + (coef * gains) @ V
        return out.float()

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return (self.n or 0), False


def make(args: str, *, metric_default: str | None = None) -> GenericWhitening:
    parts = args.split(":")
    pool_name, lam = parts[0], float(parts[1])
    flags = parts[2:]
    metric = metric_default
    n = None
    for f in flags:
        if f in ("r", "r-cos"):
            metric = "cos"
        elif f == "r-rms":
            metric = "rms"
        elif f.startswith("n") and f[1:].isdigit():
            n = int(f[1:])
    return GenericWhitening(pool_name, lam, metric=metric, rnd="rnd" in flags, evshuf="evshuf" in flags, n=n,
                            name=f"m1:{args}")


def make_r(args: str) -> GenericWhitening:
    """``m1r:<pool>:<lam>[:rms]``: the readout-metric variant (cos metric unless ``rms``)."""
    parts = args.split(":")
    metric = "rms" if "rms" in parts[2:] else "cos"
    c = make(":".join(p for p in parts if p != "rms"), metric_default=metric)
    c.name = f"m1r:{args}"
    return c


def make_rnd(args: str) -> GenericWhitening:
    c = make(args)
    c.rnd, c.name = True, f"m1rnd:{args}"
    c.doc += "; control: random orthonormal basis"
    return c


PARAMETRIC.update({"m1": make, "m1r": make_r, "m1rnd": make_rnd})
