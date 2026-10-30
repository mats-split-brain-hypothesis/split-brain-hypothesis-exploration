"""S22: a late partial mean from item-free reference cells (notes/iteration-anthony/mu-log.md, card S22).

The pool is read cells that hold a family's format and genre but none of its items' content: S2's hand-written neutral
fills (``data/dev/<family>/s2.json``, condition "neutral", captured to ``out/captures/<family>-s2.pt``: association,
typo, multihop_mt, multilingual_mt) and, where captured, S22's random-fill renders (``data/dev/<family>/s22.json`` ->
``out/captures/<family>-s22.pt``: the chat templates of user_modeling and directed_modulation). No family label is used
in reading: every cell sees the whole pool.

- ``s22nn<k>``: g(h) = mean of the k pool cells nearest to h (cosine, at the layer). Used as the late partial mean of
  S14b: ``sched:40:kmx64+s14:template:64:mean=s22nn8:a=0.5``.
- ``s22pm``: g = the pool's mean (one vector per layer), the constant version.
"""

import torch

from jlm import REPO_ROOT, capture
from jlm.centres import CENTRES, Batch, CellRef

OWNER = "Anthony"
CANDIDATES = ()
_POOL: dict = {}


def load_pool() -> dict[int, torch.Tensor]:
    """layer -> [N, d] float32: every neutral S2 fill's and every S22 fill's read cells that are captured."""
    if _POOL:
        return _POOL
    from wsbench.banks import load_bank

    from jlm.banks import Bank

    rows: dict[int, list] = {}
    for path in sorted((REPO_ROOT / "data" / "dev").glob("*/s2*.json")):
        family, split = path.parent.name, path.stem
        if split not in ("s2", "s22"):
            continue
        header, items = load_bank(path)
        keep = {it["name"] if "name" in it else it["id"] for it in items if split == "s22" or it.get("condition") == "neutral"}
        try:
            caps = capture.load(Bank(family, split, path, header, items))
        except FileNotFoundError:
            continue
        for c in caps:
            if c.id not in keep:
                continue
            for L, a in c.acts.items():
                rows.setdefault(L, []).append(a.float())
    if not rows:
        raise FileNotFoundError("S22: no S2 / S22 fill captures under out/captures")
    _POOL.update({L: torch.cat(v) for L, v in rows.items()})
    return _POOL


class NeutralNearest:
    def __init__(self, k: int, constant: bool = False) -> None:
        self.k, self.constant = k, constant
        self.name = "s22pm" if constant else f"s22nn{k}"
        self.doc = ("mean of the item-free fill pool (S2 neutral fills + S22 renders)" if constant else
                    f"mean of the {k} nearest cells of the item-free fill pool (S2 neutral fills + S22 renders)")
        self.n_fallback = 0

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.pool = load_pool()
        self.unit = {L: X / X.norm(dim=1, keepdim=True).clamp_min(1e-6) for L, X in self.pool.items()}

    def transform(self, batch: Batch) -> torch.Tensor:
        X = self.pool[batch.layer]
        if self.constant:
            return batch.H - X.mean(0)
        U = batch.H / batch.H.norm(dim=1, keepdim=True).clamp_min(1e-6)
        idx = (U @ self.unit[batch.layer].T).topk(min(self.k, len(X)), dim=1).indices
        return batch.H - X[idx].mean(1)

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return self.k, False


for _k in (4, 8, 16):
    CENTRES[f"s22nn{_k}"] = lambda k=_k: NeutralNearest(k)
CENTRES["s22pm"] = lambda: NeutralNearest(0, constant=True)
