"""S18 sparse mu: the family mean restricted to a few coordinates (notes/iteration-anthony/mu-log.md, card S18).

The residual stream's mean is dominated by a handful of outlier coordinates (the massive activations): at L20-48 the
top 8 coordinates of fam hold 60-90 % of ||mu||^2 (``experiments/s18_coords.py``). If fam's gain lives there, a
context-free value for those coordinates (the wikitext mean) would do fam's job with no bench data.

Coordinates are chosen once per layer at fit time, by |value| of the family mean over the whole reference set; g per
cell is then the cell's own leave-group-out mean (as ``fam``) on those coordinates, zero elsewhere.

- ``s18k<k>``: fam on its top-k coordinates.
- ``s18c<k>``: the complement, fam with its top-k coordinates zeroed (s18k + s18c = fam).
- ``s18r<k>``: control, fam on k random coordinates (seeded per layer).
- ``s18w<k>``: the wikitext mean (``corpus8``: positions 8+ of the wikitext capture) on fam's top-k coordinates.
- ``s18ww<k>``: the wikitext mean on its own top-k coordinates (no bench data at all).
- ``s18cc<k>`` / ``s18cfull`` (S18c): the same with the chat-format corpus mean (template-format cells, bench-free).
- ``s18wc<k>`` (S18b): the wikitext mean with **its own** top-k coordinates zeroed (bench-free: does the corpus mean
  work once its outlier offset is gone?); ``s18wfull``: the whole wikitext mean (G1's null, as the reference).
k in 8 / 32 / 128 / 512; d = 5120, so ``s18k5120`` would be fam exactly (tested on a toy).
"""

import torch

from jlm.centres import CENTRES, Batch, CellRef, FamilyMean

OWNER = "Anthony"
CANDIDATES = ()

_WIKI: dict[int, torch.Tensor] = {}
_CHAT: dict[int, torch.Tensor] = {}


def chat_mean(layer: int) -> torch.Tensor:
    """The chat-format corpus mean (no_robots prompts rendered as the bench renders; ``clusters.Pool.chat``, positions
    past the first two), loaded once per process. Needs ``out/ctx/corpus-chat.pt`` (the pod's volume)."""
    if not _CHAT:
        from jlm.mu.clusters import Pool, pool

        p = pool(("chat",), Pool.chat)
        for L, X in p.X.items():
            _CHAT[L] = X.double().mean(0).float()
    return _CHAT[layer]


def wiki_mean(layer: int) -> torch.Tensor:
    """The wikitext corpus mean at ``layer`` (positions 8+), loaded once per process."""
    if not _WIKI:
        from jlm import capture

        items = capture.load_ref("corpus8")
        for L in sorted({L for it in items for L in it.acts}):
            _WIKI[L] = torch.cat([it.acts[L].double() for it in items if L in it.acts]).mean(0).float()
    return _WIKI[layer]


class Sparse:
    def __init__(self, k: int, mode: str, seed: int = 0) -> None:
        assert mode in ("top", "comp", "rand", "wiki", "wikiown", "wikicomp", "wikifull", "chatcomp", "chatfull")
        self.k, self.mode, self.seed = k, mode, seed
        self.name = {"top": "s18k", "comp": "s18c", "rand": "s18r", "wiki": "s18w", "wikiown": "s18ww", "wikicomp": "s18wc",
                     "wikifull": "s18wfull", "chatcomp": "s18cc", "chatfull": "s18cfull"}[mode] + ("" if mode.endswith("full") else str(k))
        self.doc = {
            "top": f"family mean on its top-{k} coordinates by |value|, zero elsewhere",
            "comp": f"family mean with its top-{k} coordinates zeroed",
            "rand": f"control: family mean on {k} random coordinates",
            "wiki": f"wikitext mean on the family mean's top-{k} coordinates",
            "wikiown": f"wikitext mean on its own top-{k} coordinates (no bench data)",
            "wikicomp": f"wikitext mean with its own top-{k} coordinates zeroed (no bench data)",
            "wikifull": "the whole wikitext mean (no bench data)",
            "chatcomp": f"chat-corpus mean with its own top-{k} coordinates zeroed (no bench data)",
            "chatfull": "the whole chat-corpus mean (no bench data)",
        }[mode]
        self.n_fallback = 0

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.fam = FamilyMean()
        self.fam.fit(ref, family, groups)
        self.d = next(iter(ref[0].acts.values())).shape[1]
        self.mask: dict[int, torch.Tensor] = {}
        for (L, _key), s in self.fam.s.items():
            mu = (s / self.fam.n[(L, _key)]).float()
            if self.mode == "rand":
                g = torch.Generator().manual_seed(self.seed * 1000 + L)
                idx = torch.randperm(self.d, generator=g)[: self.k]
            elif self.mode in ("wikiown", "wikicomp"):
                idx = wiki_mean(L).abs().topk(self.k).indices
            elif self.mode == "chatcomp":
                idx = chat_mean(L).abs().topk(self.k).indices
            elif self.mode.endswith("full"):
                idx = torch.arange(self.d)
            else:
                idx = mu.abs().topk(min(self.k, self.d)).indices
            m = torch.zeros(self.d)
            m[idx] = 1.0
            self.mask[L] = 1.0 - m if self.mode in ("comp", "wikicomp", "chatcomp") else m

    def __call__(self, cell: CellRef) -> torch.Tensor:
        m = self.mask[cell.layer]
        if self.mode.startswith("wiki"):
            return wiki_mean(cell.layer) * m
        if self.mode.startswith("chat"):
            return chat_mean(cell.layer) * m
        return self.fam(cell) * m

    def transform(self, batch: Batch) -> torch.Tensor:
        return batch.H - torch.stack([self(c) for c in batch.cells])

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return (0, False) if self.mode.startswith(("wiki", "chat")) else self.fam.support(cell)


for _k in (8, 32, 128, 512):
    CENTRES[f"s18k{_k}"] = lambda k=_k: Sparse(k, "top")
    CENTRES[f"s18c{_k}"] = lambda k=_k: Sparse(k, "comp")
    CENTRES[f"s18r{_k}"] = lambda k=_k: Sparse(k, "rand")
    CENTRES[f"s18w{_k}"] = lambda k=_k: Sparse(k, "wiki")
    CENTRES[f"s18ww{_k}"] = lambda k=_k: Sparse(k, "wikiown")
    CENTRES[f"s18wc{_k}"] = lambda k=_k: Sparse(k, "wikicomp")
CENTRES["s18wfull"] = lambda: Sparse(0, "wikifull")
CENTRES["s18cfull"] = lambda: Sparse(0, "chatfull")
for _k in (8, 32, 128):
    CENTRES[f"s18cc{_k}"] = lambda k=_k: Sparse(k, "chatcomp")
