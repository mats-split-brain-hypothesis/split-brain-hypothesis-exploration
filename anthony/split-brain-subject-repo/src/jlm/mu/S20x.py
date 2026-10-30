"""S20x leave-one-family-out learned constant (notes/iteration-anthony/mu-log.md, card S20x).

**Supervised transfer centre, not label-free**: g contains the other families' target-fitted ceilings (S20's ``ceil.``
constants), i.e. fit-split labels of other families. The research loop's "learned" row allows fit targets in a learned
g's training if it is scored on val; the night-2 preamble's "no targets inside g" names only the ``ceil.`` arms as an
exception, so whether this counts as a method is the user's call (raised by the steward, 2026-10-12).

``g = mu_fam + alpha * dbar_{-F}``: the family mean plus the average of the other families' target-fitted corrections
(S20's ``ceil.const - fam``; ``experiments/s20x_dbar.py`` -> ``out/analysis/S20x/dbar.pt``). F's own targets never
enter, and the other families' targets enter only through their fit split: a learned g in the research loop's sense,
a method if it holds on val. alpha is chosen on fit.

- ``s20x:<alpha>``: as above.
- ``s20xt:<alpha>``: the same with F's twin family (``typo`` <-> ``typo_mt``, ...) also left out of the average: the
  same task in other languages teaches the same answer class.
- ``s20xp:<alpha>`` / ``s20xm:<alpha>``: twin-out with only the plain (single-token) / only the _mt families as sources
  (does the shared correction come from one kind of bank?).
- ``s20xon:<alpha>:<centre>``: any centre plus the twin-out correction, ``h - g_centre(h) - alpha * dbar`` (e.g.
  ``s20xon:1:s14t64``, A's template-subspace removal, which keeps multilingual_mt's language unit; A agreed, night-2).
- ``s20x1:<G>:<alpha>``: a single source family G's correction alone (the transfer matrix); reading G itself or its
  twin falls back to fam (no own targets).
- ``s20xtrms:<alpha>`` / ``s20xonrms:<alpha>:<centre>``: the same with the corrections C fitted through the rms map
  (``dbar-rms.pt``), for reading with ``|rms`` (readout-matched; S21 was cos-only).
- ``s20xu:<alpha>``: twin-out with user_modeling's constant as an 11th source (``dbar-11.pt``; the ensemble test).
- ``s20xk:<k>:<draw>:<alpha>`` / ``s20xkrms:...``: the average over k source families drawn at random (seeded by k and
  draw) from those eligible for the read family (it and its twin left out); k above the eligible count takes them all.
  The steward's source-scaling card.
- ``s20xr:<alpha>``: control, ``dbar`` replaced by a random direction of the same norm per layer (seeded).
"""

import torch

from jlm import OUT
from jlm import centres
from jlm.centres import PARAMETRIC, Batch, CellRef, FamilyMean

OWNER = "Anthony"
CANDIDATES = ()

_DBAR: dict = {}
_DBAR_RMS: dict = {}
_DBAR_11: dict = {}


def dbar(family: str, layer: int, readout: str = "cos") -> torch.Tensor:
    """The correction table: C's constants fitted through the cos map (``dbar.pt``) or the rms map (``dbar-rms.pt``)."""
    table, name = {"cos": (_DBAR, "dbar.pt"), "rms": (_DBAR_RMS, "dbar-rms.pt"), "cos11": (_DBAR_11, "dbar-11.pt")}[readout]
    if not table:
        table.update(torch.load(OUT / "analysis" / "S20x" / name, weights_only=False))
    return table[family][layer].float()


class Transfer:
    def __init__(self, alpha: float, random: bool = False, seed: int = 0, twin: bool = False, sources: str = "",
                 readout: str = "cos") -> None:
        self.alpha, self.random, self.seed, self.twin, self.sources, self.readout = alpha, random, seed, twin, sources, readout
        tag = {"plain": "p", "mt": "m"}.get(sources, "r" if random else "t" if twin else "")
        self.name = f"s20x{tag}{'' if readout == 'cos' else readout}:{alpha:g}".replace("tcos11", "u")
        self.doc = (f"family mean + {alpha:g} x the other families' mean target-fitted correction (S20 ceil.const - fam)"
                    + (" [control: a random direction of the same norm]" if random else ""))
        self.n_fallback = 0

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.fam = FamilyMean()
        self.fam.fit(ref, family, groups)
        self.family = family
        self._d: dict[int, torch.Tensor] = {}

    def delta(self, layer: int) -> torch.Tensor:
        if layer not in self._d:
            d = dbar(self.family + ("|" + self.sources if self.sources else "|twin" if self.twin else ""), layer, self.readout)
            if self.random:
                u = torch.randn(d.shape[0], generator=torch.Generator().manual_seed(self.seed * 1000 + layer))
                d = u / u.norm() * d.norm()
            self._d[layer] = self.alpha * d
        return self._d[layer]

    def __call__(self, cell: CellRef) -> torch.Tensor:
        return self.fam(cell) + self.delta(cell.layer)

    def transform(self, batch: Batch) -> torch.Tensor:
        return batch.H - torch.stack([self(c) for c in batch.cells])

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return self.fam.support(cell)


PARAMETRIC["s20x"] = lambda a: Transfer(float(a))
PARAMETRIC["s20xr"] = lambda a: Transfer(float(a), random=True)
PARAMETRIC["s20xt"] = lambda a: Transfer(float(a), twin=True)
PARAMETRIC["s20xp"] = lambda a: Transfer(float(a), sources="plain")
PARAMETRIC["s20xm"] = lambda a: Transfer(float(a), sources="mt")


class OnTop:
    """``h - g_base(h) - alpha * dbar_{-F, twin}``: the correction added to any centre's g (``random``: a random
    direction of dbar's norm instead, seeded per layer: the control)."""

    def __init__(self, alpha: float, base: str, random: bool = False, readout: str = "cos") -> None:
        self.alpha, self.base, self.random, self.readout = alpha, centres.make(base), random, readout
        self.name = f"s20x{'r' if random else ''}on{'' if readout == 'cos' else readout}:{alpha:g}:{base}"
        self.doc = (f"{self.base.doc}; plus {alpha:g} x " + ("a random direction with the norm of " if random else "")
                    + "the other families' mean target-fitted correction (twin out)")
        self.needs_ctx = getattr(self.base, "needs_ctx", False)
        self.n_fallback = 0

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.base.fit(ref, family, groups, ctx=ctx) if self.needs_ctx else self.base.fit(ref, family, groups)
        self.family = family

    def transform(self, batch: Batch) -> torch.Tensor:
        d = dbar(self.family + "|twin", batch.layer, self.readout)
        if self.random:
            u = torch.randn(d.shape[0], generator=torch.Generator().manual_seed(batch.layer))
            d = u / u.norm() * d.norm()
        return centres.apply(self.base, batch) - self.alpha * d

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return self.base.support(cell)


def _on_top(args: str, random: bool = False, readout: str = "cos") -> OnTop:
    alpha, _, base = args.partition(":")
    return OnTop(float(alpha), base, random, readout)


PARAMETRIC["s20xon"] = _on_top
PARAMETRIC["s20xron"] = lambda a: _on_top(a, random=True)
PARAMETRIC["s20xonrms"] = lambda a: _on_top(a, readout="rms")
PARAMETRIC["s20xu"] = lambda a: Transfer(float(a), twin=True, readout="cos11")
PARAMETRIC["s20xtrms"] = lambda a: Transfer(float(a), twin=True, readout="rms")


class Single(Transfer):
    def __init__(self, source: str, alpha: float) -> None:
        super().__init__(alpha)
        self.source = source
        self.name = f"s20x1:{source}:{alpha:g}"
        self.doc = f"family mean + {alpha:g} x {source}'s target-fitted correction (S20 ceil.const - fam) alone"

    def delta(self, layer: int) -> torch.Tensor:
        twin = self.family.removesuffix("_mt") if self.family.endswith("_mt") else self.family + "_mt"
        if self.source in (self.family, twin):
            return torch.zeros(1)
        if not _DBAR:
            dbar(self.family, layer)
        return self.alpha * _DBAR["d"][self.source][layer].float()


def _single(args: str) -> Single:
    source, _, alpha = args.rpartition(":")
    return Single(source, float(alpha))


PARAMETRIC["s20x1"] = _single


class KSources(Transfer):
    def __init__(self, k: int, draw: int, alpha: float, readout: str = "cos") -> None:
        super().__init__(alpha, readout=readout)
        self.k, self.draw = k, draw
        self.name = f"s20xk{'' if readout == 'cos' else readout}:{k}:{draw}:{alpha:g}"
        self.doc = f"family mean + {alpha:g} x the mean correction of {k} random other source families (draw {draw})"

    def drawn(self) -> list[str]:
        import random

        table = _DBAR if self.readout == "cos" else _DBAR_RMS
        twin = self.family.removesuffix("_mt") if self.family.endswith("_mt") else self.family + "_mt"
        ok = sorted(g for g in table["d"] if g not in (self.family, twin))
        return sorted(random.Random(1000 * self.k + self.draw).sample(ok, min(self.k, len(ok))))

    def delta(self, layer: int) -> torch.Tensor:
        if layer not in self._d:
            dbar(self.family + "|twin", layer, self.readout)  # loads the table
            table = _DBAR if self.readout == "cos" else _DBAR_RMS
            self._d[layer] = self.alpha * torch.stack([table["d"][g][layer].float() for g in self.drawn()]).mean(0)
        return self._d[layer]


def _ksources(args: str, readout: str = "cos") -> KSources:
    k, draw, alpha = args.split(":")
    return KSources(int(k), int(draw), float(alpha), readout)


PARAMETRIC["s20xk"] = _ksources
PARAMETRIC["s20xkrms"] = lambda a: _ksources(a, "rms")
