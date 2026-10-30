"""S3 dynamic g: the part of h_t a corpus predicts from the previous position's state (studies/S3.md).

``ar1e<p>``: g = my + (h_{t-1} - mx) A, with A the ridge regression of h_t on h_{t-1} at the same layer, fitted on the
wikitext context capture (``experiments/s3_stats.py``: no bank item), lambda = 10^-p * tr(C) / d. The Taylor reading:
``J(h_t - E[h_t | h_{t-1}])``, what is new at t beyond what any text with this previous state would hold. As lambda
grows, g tends to the corpus mean ``my`` (jle's G1, "does nothing"), so p is a dial from a constant to a full
prediction; p is chosen on fit. h_{t-1} comes from the item's own context capture (``needs_ctx``).
"""

import torch

from jlm import OUT
from jlm.centres import CENTRES, Batch

OWNER = "Anthony"  # dashboard pickers list these centres under "Anthony's centres" (catalog.owner)


STATS = OUT / "analysis" / "S3"
_SOLVED: dict = {}  # (corpus, p, layer) -> (mx, my, A), shared by every bank of one evaluate run


def solve(corpus: str, p: int, layer: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    key = (corpus, p, layer)
    if key not in _SOLVED:
        s = torch.load(STATS / f"arstats-{corpus}-L{layer:03d}.pt", weights_only=False)
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        C, B = s["C"].to(dev, torch.float64), s["B"].to(dev, torch.float64)
        lam = 10.0 ** (-p) * torch.trace(C) / C.shape[0]
        A = torch.linalg.solve(C + lam * torch.eye(C.shape[0], dtype=C.dtype, device=dev), B)
        _SOLVED[key] = (s["mx"], s["my"], A.float().cpu())
    return _SOLVED[key]


class LagPredictor:
    needs_ctx = True

    def __init__(self, p: int, corpus: str = "wikitext") -> None:
        self.p, self.corpus = p, corpus
        self.name = f"ar1e{p}"
        self.doc = f"ridge prediction of h_t from h_(t-1) on {corpus} (lambda = 1e-{p} tr(C)/d)"
        self.n_fallback = 0

    def fit(self, ref, family, groups=None, ctx=None) -> None:  # the predictor is fitted on the corpus, not on ref
        self.n_fallback = 0

    def transform(self, batch: Batch) -> torch.Tensor:
        assert batch.ctx is not None, "ar1 needs a context capture (out/ctx)"
        mx, my, A = solve(self.corpus, self.p, batch.layer)
        P = torch.zeros_like(batch.H)
        first = torch.zeros(len(batch.cells), dtype=torch.bool)
        for j, c in enumerate(batch.cells):
            t = batch.ctx.items[c.item].idx[c.i]
            if t == 0:
                first[j] = True
                continue
            P[j] = batch.ctx.states(c.item, batch.layer)[t - 1].float()
        G = my + (P - mx) @ A
        G[first] = my  # no previous position: the corpus mean
        self.n_fallback += int(first.sum())
        return batch.H - G

    def support(self, cell) -> tuple[int, bool]:
        return 1, False


for _p in (0, 1, 2):
    CENTRES[f"ar1e{_p}"] = lambda p=_p: LagPredictor(p)
