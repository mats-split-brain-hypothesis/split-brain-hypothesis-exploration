"""S25 label-free answer-position correction (notes/iteration-anthony/mu-log.md, card S25).

``s25on:<alpha>:<class>:<base>``: ``h - (g_base(h) - alpha * d_class)``, i.e. the read state is moved by +alpha * d along the
chat corpus's "the next token is a <class> word" direction (``experiments/s25_dirs.py`` -> out/analysis/S25/dirs.pt:
mean of cells before such tokens minus the mean of all cells; class cap / content / latin, and rand: a random subset of the
same size, the control). Label-free: no bench cells, no targets in d. Used as S14b-x's early part in place of S20x's dbar.
"""

import torch

from jlm import OUT, centres
from jlm.centres import PARAMETRIC, Batch, CellRef

OWNER = "Anthony"
CANDIDATES = ()

_DIRS: dict = {}


def direction(cls: str, layer: int) -> torch.Tensor:
    if not _DIRS:
        _DIRS.update(torch.load(OUT / "analysis" / "S25" / "dirs.pt", weights_only=False))
    return _DIRS[cls][layer].float()


class AnswerPosition:
    def __init__(self, alpha: float, cls: str, base: str) -> None:
        self.alpha, self.cls, self.base = alpha, cls, centres.make(base)
        self.name = f"s25on:{alpha:g}:{cls}:{base}"
        self.doc = f"{self.base.doc}; read state moved by {alpha:g} x the chat corpus's next-token-is-{cls} direction"
        self.needs_ctx = getattr(self.base, "needs_ctx", False)
        self.n_fallback = 0

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.base.fit(ref, family, groups, ctx=ctx) if self.needs_ctx else self.base.fit(ref, family, groups)

    def transform(self, batch: Batch) -> torch.Tensor:
        return centres.apply(self.base, batch) + self.alpha * direction(self.cls, batch.layer)

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return self.base.support(cell)


def _make(args: str) -> AnswerPosition:
    alpha, cls, base = args.split(":", 2)
    return AnswerPosition(float(alpha), cls, base)


PARAMETRIC["s25on"] = _make
