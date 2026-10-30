"""Read an arm (centre x readout) over a bank's captures.

Writes the bench's readout contract (one row per (item, layer, pos), top-10 display tokens and
scores) so ``wsbench judge`` takes it unchanged, and a sidecar with, per cell, the rank of the
best accepted target id over the whole vocabulary (what the strict rule thresholds at top-10) and the
norms ``||h||``, ``||g||``. With ``mask``, also the prompt-masked readout: the same contract, top 10
after the item's prompt-content tokens are removed from the vocabulary (a control; ``jlm.controls``).
With ``semantic`` (an exclusion list, ``controls.non_semantic_ids``), also the same three over the semantic
vocabulary only (J++'s Readout Filtering): top 10, rank and masked top 10 with those ids removed, from the same scores.
A readout may carry a plausibility tag (M3, contrastive decoding's alpha-mask): ``cos:p250`` ranks the centred scores
only among the top 250 tokens of the *uncentred* scores at the same cell and layer (the rest are -inf, so a target
outside them has rank N); ``cos:r250`` is its control, the uncentred top 10 plus 240 random other tokens.
"""

from dataclasses import dataclass
from typing import Any

import torch
from umot.capture import ItemCapture

from jlm.centres import Batch, Centre, apply, cell_refs
from jlm.context import ContextStore
from jlm.lens import Lens

TOP_K = 10
RANK_NONE = -1  # the cell's item has no single-token accepted id
ROWS = 256  # cells per [rows, V] score block


def readout_rule(readout: str) -> tuple[str, str | None, int]:
    """``cos`` -> ("cos", None, 0); ``cos:p250`` -> ("cos", "p", 250) (plausibility mask); ``cos:r250`` -> random control."""
    base, _, tag = readout.partition(":")
    if not tag:
        return base, None, 0
    if tag[0] not in "pr" or not tag[1:].isdigit() or int(tag[1:]) < TOP_K:
        raise ValueError(f"readout tag {tag!r}: expected p<N> or r<N> with N >= {TOP_K}")
    return base, tag[0], int(tag[1:])


def plausible(S: torch.Tensor, S0: torch.Tensor, kind: str, n: int, seed: int = 0) -> torch.Tensor:
    """``S`` with every token outside the cell's plausible set at -inf. ``p``: the top ``n`` of the uncentred scores
    ``S0``; ``r``: S0's top 10 plus ``n - 10`` other tokens drawn at random per cell (seeded)."""
    n = min(n, S.shape[1])  # N = V goes through the same path (the reproduction test)
    if kind == "p":
        keep = S0.topk(n, dim=1).indices
    else:
        g = torch.Generator(device=S0.device).manual_seed(seed)
        noise = torch.rand(S0.shape, generator=g, device=S0.device)
        top = S0.topk(TOP_K, dim=1).indices
        noise.scatter_(1, top, 2.0)  # the uncentred top 10 always kept
        keep = noise.topk(n, dim=1).indices
    out = torch.full_like(S, float("-inf"))
    return out.scatter_(1, keep, S.gather(1, keep))


@dataclass(frozen=True)
class Arm:
    centre: str  # centres.CENTRES key
    ref: str  # what the centre is fitted on: "self" (the read bank, own item excluded) or a split
    readout: str  # lens.READOUTS
    lens: str = "jlens"  # lens.LENSES; any other map prefixes the name, ``jpp:zero|cos``

    @property
    def name(self) -> str:
        base = f"{self.centre}|{self.readout}" if self.centre == "zero" else f"{self.centre}@{self.ref}|{self.readout}"
        return base if self.lens == "jlens" else f"{self.lens}:{base}"


def read(
    lens: Lens,
    items: list[ItemCapture],
    family: str,
    centre: Centre,
    readout: str,
    accepted: dict[str, list[int]],
    layers: list[int],
    groups: dict[str, str] | None = None,
    ctx: ContextStore | None = None,
    mask: dict[str, list[int]] | None = None,
    semantic: list[int] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, list[dict[str, Any]]] | None]:
    """(readout rows, rank rows, masked readout rows, semantic-only {readouts, ranks, masked} or None) for ``h - g``
    at every captured cell and layer; the masked rows are empty without ``mask``."""
    rows: list[dict[str, Any]] = []
    ranks: list[dict[str, Any]] = []
    masked: list[dict[str, Any]] = []
    sem = None if semantic is None else {"readouts": [], "ranks": [], "masked": []}
    by_id = {it.id: it for it in items}
    base, kind, n = readout_rule(readout)
    for layer in layers:
        cells = cell_refs([it for it in items if layer in it.acts], family, layer, groups)
        H = torch.stack([by_id[c.item].acts[layer][c.i].float() for c in cells])
        X = apply(centre, Batch(layer, cells, H, by_id, ctx))
        nh, ng = H.norm(dim=1).tolist(), (H - X).norm(dim=1).tolist()
        acc = _padded([accepted.get(c.item, []) for c in cells])
        msk = _padded([mask.get(c.item, []) for c in cells]) if mask is not None else None
        excl = torch.tensor(semantic, dtype=torch.int64) if semantic is not None else None
        for a in range(0, len(cells), ROWS):
            block = cells[a : a + ROWS]
            S = lens.scores(X[a : a + ROWS], layer, base)
            if kind is not None:  # M3: rank only what the uncentred lens finds plausible at this cell
                S0 = lens.scores(H[a : a + ROWS], layer, base)
                S = plausible(S, S0, kind, n, seed=layer * 1_000_003 + a)
            A = acc[a : a + ROWS].to(S.device)
            has = A >= 0
            got = torch.where(has, S.gather(1, A.clamp_min(0)), torch.full_like(A, float("-inf"), dtype=S.dtype))
            best, arg = got.max(1)  # accepted ids are spared by the semantic filter: the same best in both
            best_id = A.gather(1, arg[:, None])[:, 0].tolist()
            reachable = has.any(1).tolist()
            norms = [(round(nh[a + j], 3), round(ng[a + j], 3)) for j in range(len(block))]
            views = [(S, rows, ranks, masked)]
            if sem is not None:
                views.append((S.index_fill(1, excl.to(S.device), float("-inf")), sem["readouts"], sem["ranks"], sem["masked"]))
            for V, out_rows, out_ranks, out_masked in views:
                rank = (V > best[:, None]).sum(1).tolist()
                _top_rows(lens, V, block, layer, out_rows)
                for j, c in enumerate(block):
                    ok = reachable[j]
                    out_ranks.append({"id": c.item, "layer": layer, "pos": c.pos,
                                      "rank": rank[j] if ok else RANK_NONE, "best_id": best_id[j] if ok else None,
                                      "h_norm": norms[j][0], "g_norm": norms[j][1]})
                if msk is not None:  # V is not needed after this: mask in place
                    M = msk[a : a + ROWS].to(V.device)
                    r, k = (M >= 0).nonzero(as_tuple=True)
                    V[r, M[r, k]] = float("-inf")
                    _top_rows(lens, V, block, layer, out_masked)
    return rows, ranks, masked, sem


def _top_rows(lens: Lens, S: torch.Tensor, block, layer: int, out: list[dict[str, Any]]) -> None:
    """Append each cell's top 10 (display tokens and scores) under scores ``S`` [len(block), V]."""
    vals, top = S.topk(TOP_K, dim=1)
    names, vals = lens.display(top.flatten().tolist()), vals.tolist()
    for j, c in enumerate(block):
        out.append({"id": c.item, "layer": layer, "pos": c.pos, "token": c.token,
                    "tokens": names[j * TOP_K : (j + 1) * TOP_K], "scores": [round(v, 4) for v in vals[j]]})


def _padded(lists: list[list[int]]) -> torch.Tensor:
    """[n, m] int64, -1 padded (m >= 1)."""
    m = max(1, max((len(x) for x in lists), default=1))
    out = torch.full((len(lists), m), -1, dtype=torch.int64)
    for k, x in enumerate(lists):
        out[k, : len(x)] = torch.tensor(x, dtype=torch.int64)
    return out
