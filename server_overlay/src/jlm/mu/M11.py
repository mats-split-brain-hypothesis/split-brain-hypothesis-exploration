"""M11 (night-3 C): n-scaling of M1's generic pool (notes/iteration-anthony/mu-log.md, card M11).

``m11:<pool>:<lam>:n<k>:s<seed>[:cov]``: M1's ``GenericWhitening`` with the pool subsampled to k cells (seeded).
Without ``cov`` the mean mu_0 and the covariance both come from the k cells (A's ``n<k>`` with a seed); with ``cov``
the mean comes from the whole pool and only the covariance from the k cells. ``lam = inf`` is the constant alone.
A's module is used as is; the factors are cached here, keyed with ``cov`` and the seed.
"""

from jlm.centres import PARAMETRIC
from jlm.mu import M1
from jlm.mu.M1 import GenericWhitening, pca, whiten_gains

_CACHE: dict = {}


class SubsampledWhitening(GenericWhitening):
    def __init__(self, pool_name: str, lam: float, n: int, seed: int, cov_only: bool, name: str) -> None:
        super().__init__(pool_name, lam, n=n, seed=seed, name=name)
        self.cov_only = cov_only
        self.doc += f"; seed {seed}" + ("; mean from the whole pool, covariance from the subsample" if cov_only else "")

    def op(self, layer: int):
        if layer in self._ops:
            return self._ops[layer]
        key = (self.pool_name, self.family, layer, self.n, self.seed, self.cov_only)
        if key not in _CACHE:
            X = self._pool_rows(layer).double()  # A's seeded subsample of n cells
            mu_k, ev, V = pca(X)
            mu = M1.pool(self.pool_name, self.family, layer).double().mean(0) if self.cov_only else mu_k
            _CACHE[key] = (mu, ev, V)
        mu, ev, V = _CACHE[key]
        self._ops[layer] = (mu, whiten_gains(ev, self.lam, len(mu)), V, V)
        return self._ops[layer]


def make(args: str) -> SubsampledWhitening:
    parts = args.split(":")
    pool_name, lam = parts[0], float(parts[1])
    n = next(int(p[1:]) for p in parts[2:] if p.startswith("n") and p[1:].isdigit())
    seed = next((int(p[1:]) for p in parts[2:] if p.startswith("s") and p[1:].isdigit()), 0)
    return SubsampledWhitening(pool_name, lam, n, seed, "cov" in parts[2:], name=f"m11:{args}")


PARAMETRIC["m11"] = make
