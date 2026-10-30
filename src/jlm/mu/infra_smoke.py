"""Infrastructure smoke centre: exercises the context path (``needs_ctx``, ``Batch.ctx``) end to end.

``prev4``: g = the mean of the item's own states at the 4 positions before the read cell (fewer at the start of
the prompt; 0 at position 0). A crude S3 ("dynamic mu") variant written to test the pipeline, not a study: its
numbers belong to whoever runs S3.
"""

import torch

from jlm.centres import CENTRES, Batch

OWNER = "Anthony"  # dashboard pickers list these centres under "Anthony's centres" (catalog.owner)


class PrevMean:
    needs_ctx = True

    def __init__(self, k: int = 4) -> None:
        self.k = k
        self.name, self.doc = f"prev{k}", f"mean of the item's own states at the {k} positions before the read cell"

    def fit(self, ref, family, groups=None, ctx=None) -> None:  # nothing to fit: g comes from the item's own context
        pass

    def transform(self, batch: Batch) -> torch.Tensor:
        assert batch.ctx is not None, "prev needs a context capture (out/ctx)"
        G = torch.zeros_like(batch.H)
        for j, c in enumerate(batch.cells):
            t = batch.ctx.items[c.item].idx[c.i]
            if t > 0:
                G[j] = batch.ctx.states(c.item, batch.layer)[max(0, t - self.k) : t].float().mean(0)
        return batch.H - G

    def support(self, cell) -> tuple[int, bool]:
        return self.k, False


CENTRES["prev4"] = PrevMean
