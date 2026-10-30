"""S20 ceilings read through the pipeline: the g that ``experiments/ceilings.py --save-g`` fitted WITH the fit split's
targets, per family (notes/iteration-anthony/studies/S20.md). Labelled ``ceil.`` and evaluated only with
``evaluate.py --out out/analysis/S20/eval``, never into ``out/eval``: an in-sample ceiling, not a method.

``ceil.const`` (one vector per layer), ``ceil.tok`` (one per read token seen >= 3 times on fit, else the shared one),
``ceil.proj16`` (a learned mean plus a learned rank-16 subspace removed). The family comes from the read bank, so the
arm reads the g fitted on that family's fit split. Read on val (``@fit``): fit on fit, scored on val.
"""

import torch

from jlm import OUT
from jlm.centres import CENTRES, Batch

OWNER = "Anthony"
CANDIDATES = ()
GDIR = OUT / "analysis" / "S20" / "g"


class Ceiling:
    def __init__(self, cls: str, suffix: str = "") -> None:
        self.cls, self.suffix, self.name = cls, suffix, f"ceil.{cls}{suffix.replace('-', '')}"
        self.doc = f"S20 ceiling: the {cls} g fitted WITH fit targets (not a method)"
        self.n_fallback = 0

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        obj = torch.load(GDIR / f"{family}-{self.cls}{self.suffix}.pt", map_location="cpu")
        self.layers = {int(L): v for L, v in obj["layers"].items()}

    def transform(self, batch: Batch) -> torch.Tensor:
        m = self.layers[batch.layer]
        if m.get("pos_key"):
            keys = torch.tensor([m["pos_key"].get(c.i, 0) for c in batch.cells])
        elif m["tok_key"]:
            keys = torch.tensor([m["tok_key"].get(c.token, 0) for c in batch.cells])
        else:
            keys = torch.zeros(len(batch.cells), dtype=torch.long)
        X = batch.H - m["mu"].float()[keys]
        if m["V"] is not None:
            Q = m["V"].float()
            X = X - (X @ Q) @ Q.T
        return X

    def support(self, cell) -> tuple[int, bool]:
        return 0, False


for _c in ("const", "tok", "proj16"):
    CENTRES[f"ceil.{_c}"] = lambda _c=_c: Ceiling(_c)
CENTRES["ceil.pos"] = lambda: Ceiling("pos")  # keyed by the offset in the read span (U1's u1rel key)
CENTRES["ceil.constfirst"] = lambda: Ceiling("const", "-first")  # _mt: fitted on each form's first token


class ReadFreq:
    """S20b (no targets): ``g = mu_fam + beta * g_prior[F, L]``, the pullback of the readout-frequency prior built from
    the other families' fit cells (``experiments/s20b_prior.py``). ``s20b:<K>:<beta>``."""

    def __init__(self, k: int, beta: float) -> None:
        from jlm.centres import FamilyMean

        self.k, self.beta, self.name = k, beta, f"s20b:{k}:{beta:g}"
        self.doc = f"family mean + {beta:g} x the pulled-back readout-frequency prior (top {k}, other families; no targets)"
        self.fam = FamilyMean()
        self.n_fallback = 0

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.fam.fit(ref, family, groups)
        obj = torch.load(OUT / "priors" / "S20b" / f"readfreq-k{self.k}.pt", map_location="cpu")
        key = family if family in next(iter(obj["layers"].values())) else "all"
        self.g = {int(L): v[key].float() for L, v in obj["layers"].items()}

    def __call__(self, cell) -> torch.Tensor:
        return self.fam(cell) + self.beta * self.g[cell.layer]

    def support(self, cell) -> tuple[int, bool]:
        return self.fam.support(cell)


def _readfreq(args: str) -> ReadFreq:
    k, beta = args.split(":")
    return ReadFreq(int(k), float(beta))


from jlm.centres import PARAMETRIC  # noqa: E402

PARAMETRIC["s20b"] = _readfreq


class Universal:
    """S20u: one learned constant per layer for every family (``experiments/s20u_fit.py``). ``s20u``: family F is read
    with the g fitted on the other 10 families' fit targets (no own targets, no family label in g); ``s20u0``: the
    untuned pooled mean of every family's fit read cells (the init); ``ceil.u``: fitted on all 11 (in-sample; never
    in out/eval)."""

    def __init__(self, which: str) -> None:
        self.which = which
        self.name = {"lofo": "s20u", "init": "s20u0", "all": "ceil.u"}[which]
        self.doc = {"lofo": "one learned constant for all families, fitted on the other families' fit targets",
                    "init": "the pooled mean of every family's fit read cells (no label, untuned)",
                    "all": "S20u ceiling: one constant fitted on all 11 families' fit targets (not a method)"}[which]
        self.n_fallback = 0

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        obj = torch.load(OUT / "priors" / "S20u" / "g.pt", map_location="cpu")
        key = self.which if self.which != "lofo" else family
        self.g = {int(L): v.get(key, v["all"]).float() for L, v in obj["layers"].items()}

    def __call__(self, cell) -> torch.Tensor:
        return self.g[cell.layer]

    def support(self, cell) -> tuple[int, bool]:
        return 0, False


CENTRES["s20u"] = lambda: Universal("lofo")
CENTRES["s20u0"] = lambda: Universal("init")
CENTRES["ceil.u"] = lambda: Universal("all")


class FamRand:
    """Control (S24d, steward): ``g = mu_fam + ||g_inner - mu_fam|| u`` per cell, u a random unit direction seeded per
    layer: the arm's change from the family mean replaced by a random direction of the same norm. The matched null for
    "the arm adds something to fam". ``famr:<seed>:<inner centre>`` (e.g. ``famr:0:s20xt:1``)."""

    def __init__(self, seed: int, inner_name: str) -> None:
        from jlm.centres import FamilyMean, make

        self.seed, self.inner, self.fam = seed, make(inner_name), FamilyMean()
        self.name = f"famr:{seed}:{inner_name}"
        self.doc = f"control: fam + a random direction with the norm of ({inner_name}) - fam, seed {seed}"
        self.needs_ctx = getattr(self.inner, "needs_ctx", False)
        self.n_fallback = 0

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.inner.fit(ref, family, groups, ctx)
        self.fam.fit(ref, family, groups)

    def transform(self, batch: Batch) -> torch.Tensor:
        from jlm.centres import apply

        g_in = batch.H - apply(self.inner, batch)
        g_fam = torch.stack([self.fam(c) for c in batch.cells])
        norm = (g_in - g_fam).norm(dim=1, keepdim=True)
        u = torch.randn(batch.H.shape[1], generator=torch.Generator().manual_seed(self.seed * 1000 + batch.layer))
        return batch.H - (g_fam + norm * (u / u.norm()))

    def support(self, cell) -> tuple[int, bool]:
        return self.fam.support(cell)


def _famrand(args: str) -> FamRand:
    seed, _, inner = args.partition(":")
    return FamRand(int(seed), inner)


PARAMETRIC["famr"] = _famrand
