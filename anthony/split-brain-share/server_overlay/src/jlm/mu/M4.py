"""M4: the prompt's own background, pulled back (notes/iteration-anthony/mu-log.md, card M4; studies/M4.md).

``B(prompt)`` = the tokens in the uncentred cos readout's top 10 at a share >= q of the prompt's (position x grid
layer) cells, weighted by that share (occupancy); ``g = beta * pullback(w_B)`` through the cos readout map (ridge
1e-4 x mean eigenvalue, full rank or the top ``r`` eigen-directions; ``jlm.pullback``). Per prompt, label-free, no
reference cells. The per-position top 10s and a token table come from ``experiments/m4_background.py``
(``out/priors/m4/``); this centre needs ``J`` at the read layers (from the HF cache) and the cached eigs of ``A_l``,
never ``W_U``.

Arms ``m4:<q>:<beta>[:<opt>...]`` (pullback) and ``m4p:<q>[:<opt>...]`` (projection: remove h's component in the span
of B's reading directions, S14's form with a per-prompt list), options:
- ``x``: B without the prompt's own content tokens (``controls.mask_ids``): fairer, and the difference measures how
  much of B is the prompt;
- ``rand``: every token of B replaced by its frequency-matched random substitute (the random-list control);
- ``layer``: B from the read layer's cells only; ``causal``: from the positions before the read cell only;
- ``r<k>``: the pullback on the top k eigen-directions of ``A_l``;
- ``frame`` (M4b): only B's non-word tokens (``controls.token_class`` != word: blanks, punctuation, chat specials),
  which the precompute keeps down to share ``fmin`` (0.02);
- ``own`` (M14): B = the prompt's own content-token ids (its render's tokens whose form is a prompt form; template
  forms excluded), weight 1, q ignored; ``ownshuf``: another item's (same family file, a fixed derangement);
  ``ownrand``: each replaced by a frequency- and class-matched random token (the controls);
- ``a=<strength>``: the projection scaled, ``h - a P_B h`` (robustness of M4c; default 1);
- ``on=<centre>`` (M4c): applied on top of another centre (a name without ':', e.g. A's ``gn`` / ``gnw0.3``): the
  projection or pullback acts on ``h - g_base``.
"""

import torch

from jlm import OUT
from jlm import centres
from jlm.centres import PARAMETRIC, Batch, CellRef
from jlm.pullback import CACHE

M4 = OUT / "priors" / "m4"
RIDGE = 1e-4
SPLITS = ("fit", "val", "val2", "val3", "bench")

_TABLE: dict = {}
_ROWS: dict[int, torch.Tensor] = {}  # layer -> reading rows of the table's tokens [n, d]
_EIG: dict[int, tuple[torch.Tensor, torch.Tensor]] = {}
_ITEMS: dict[str, dict] = {}  # family -> {item id: entry}


def table() -> dict:
    if not _TABLE:
        _TABLE.update(torch.load(M4 / "table.pt", weights_only=False))
        _TABLE["pos"] = {t: k for k, t in enumerate(_TABLE["ids"])}
    return _TABLE


def rows(layer: int) -> torch.Tensor:
    """``J_l^T W_U[t] / ||J_l^T W_U[t]||`` for every token of the table (the cos reading directions)."""
    if layer not in _ROWS:
        from jlm.lens import load_maps

        J = load_maps("jlens", [layer])[layer]
        t = table()
        _ROWS[layer] = (t["w_u"] @ J) / t["denom"][layer][:, None]
    return _ROWS[layer]


def eig(layer: int) -> tuple[torch.Tensor, torch.Tensor]:
    if layer not in _EIG:
        obj = torch.load(CACHE / f"pb-eig-{table()['lens_key']}-cos-L{layer:03d}.pt")
        _EIG[layer] = obj["evals"].float(), obj["evecs"].float()
    return _EIG[layer]


def items(family: str) -> dict:
    if family not in _ITEMS:
        _ITEMS[family] = {}
        for s in SPLITS:
            p = M4 / f"{family}-{s}.pt"
            if p.exists():
                obj = torch.load(p, weights_only=False)
                for i, v in obj["items"].items():
                    v["layers"] = obj["layers"]
                    _ITEMS[family][i] = v
    return _ITEMS[family]


def background(entry: dict, layer: int, at: int, q: float, source: str) -> dict[int, float]:
    """Token -> occupancy share >= q over the source's cells."""
    top = entry["top"]
    if source == "layer":
        top = top[entry["layers"].index(layer) : entry["layers"].index(layer) + 1]
    elif source == "causal":
        top = top[:, :at] if at >= 4 else top[:, :0]  # m4_background.MIN_PREFIX: no causal B from fewer positions
    n = top.shape[0] * top.shape[1]
    if n == 0:
        return {}
    ids, counts = top.flatten().unique(return_counts=True)
    s = counts.float() / n
    keep = s >= q
    return dict(zip(ids[keep].tolist(), s[keep].tolist()))


class PromptBackground:
    """``h - beta * pullback(w_B)`` (``project=False``) or ``h - P_B h`` (``project=True``), B per prompt."""

    def __init__(self, q: float, beta: float = 1.0, project: bool = False, x: bool = False, rand: bool = False,
                 source: str = "all", rank: int | None = None, name: str = "", frame: bool = False) -> None:
        self.q, self.beta, self.project, self.x, self.rand, self.source, self.rank = q, beta, project, x, rand, source, rank
        self.frame, self.base, self.strength, self.own = frame, None, 1.0, None  # own: None | "own" | "ownshuf"
        self.name = name
        what = "projection onto the reading span of" if project else f"{beta:g} x the pullback of"
        self.doc = (f"h minus the {what} the prompt's own uncentred background (top-10 tokens at share >= {q:g} of its "
                    f"{source} cells{', prompt tokens excluded' if x else ''}{', random frequency-matched list' if rand else ''})")
        self.n_fallback, self.sizes = 0, []

    def fit(self, ref, family: str, groups=None, ctx=None) -> None:
        self.family = family
        if self.base is not None:
            self.base.fit(ref, family, groups)
        floor = table().get("fmin", table()["qmin"]) if self.frame and self.source == "all" else table()["qmin"]
        if self.own is None and self.q < floor:
            raise ValueError(f"m4: q {self.q} below the precompute's threshold {floor}")

    def weights(self, cell: CellRef) -> dict[int, float]:
        entry = items(self.family).get(cell.item)
        if entry is None:
            raise KeyError(f"m4: no background for {cell.item}; run experiments/m4_background.py on its bank")
        if self.own is not None:
            ids = self._own_ids(cell.item)
            if self.own == "ownrand":
                ids = [table()["rand_own"][t] for t in ids]
            return {t: 1.0 for t in ids}
        B = background(entry, cell.layer, len(cell.context) - 1, self.q, self.source)
        if self.frame:
            cls = table()["cls"]
            B = {t: s for t, s in B.items() if cls.get(t, "word") != "word"}
        if self.x:
            drop = set(entry["prompt_ids"])
            B = {t: s for t, s in B.items() if t not in drop}
        if self.rand:
            rm = table()["rand"]
            B = {rm[t]: s for t, s in B.items()}
        return B

    def _own_ids(self, item: str) -> list[int]:
        its = items(self.family)
        if self.own == "ownshuf":
            ids = sorted(its)
            item = ids[(ids.index(item) + len(ids) // 2) % len(ids)]  # a fixed derangement (len >= 2)
        return its[item]["own_ids"]

    def transform(self, batch: Batch) -> torch.Tensor:
        t, L = table(), batch.layer
        R = rows(L)
        out, memo = [], {}
        H = batch.H if self.base is None else centres.apply(self.base, batch)
        for c, h in zip(batch.cells, H):
            key = (c.item, len(c.context) if self.source == "causal" else 0)
            if key not in memo:
                B = self.weights(c)
                self.sizes.append(len(B))
                k = [t["pos"][i] for i in B]
                if not k:
                    memo[key] = None
                elif self.project:
                    U, S, _ = torch.linalg.svd(R[k].double().T, full_matrices=False)
                    memo[key] = U[:, S > 1e-6 * S[0]].float()
                else:
                    w = torch.tensor(list(B.values()))
                    b = w @ R[k] - (w.sum() / t["vocab"]) * t["r_all"][L]
                    lam, Q = eig(L)
                    r = lam.numel() if self.rank is None else self.rank
                    lam, Q = lam[:r], Q[:, :r]
                    memo[key] = self.beta * (((b @ Q) / (lam + RIDGE * lam.mean())) @ Q.T)
            m = memo[key]
            if m is None:
                out.append(h)
            elif self.project:
                out.append(h - self.strength * (m @ (m.T @ h)))
            else:
                out.append(h - m)
        return torch.stack(out)

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return 0, False


def _make(project: bool):
    def make(args: str) -> PromptBackground:
        parts = args.split(":")
        q = float(parts[0])
        rest = parts[1:]
        beta = 1.0
        if not project:
            beta, rest = float(rest[0]), rest[1:]
        kw = {"x": False, "rand": False, "source": "all", "rank": None, "frame": False}
        base, strength, own = None, 1.0, None
        for p in rest:
            if p.startswith("on="):
                base = p[3:]
            elif p.startswith("a="):
                strength = float(p[2:])
            elif p in ("own", "ownshuf", "ownrand"):
                own = p
            elif p in ("x", "rand", "frame"):
                kw[p] = True
            elif p in ("layer", "causal"):
                kw["source"] = p
            elif p.startswith("r") and p[1:].isdigit():
                kw["rank"] = int(p[1:])
            else:
                raise ValueError(f"m4: unknown option {p!r} in {args!r}")
        c = PromptBackground(q, beta, project, name=f"{'m4p' if project else 'm4'}:{args}", **kw)
        c.strength, c.own = strength, own
        if base is not None:
            c.base = centres.make(base)
            c.doc += f", on top of {base} ({c.base.doc})"
        return c

    return make


PARAMETRIC["m4"] = _make(False)
PARAMETRIC["m4p"] = _make(True)


# M4d: S14c's bench-free chat-read list projected out of M1's whitened constant (``on=gcr``).
from jlm.centres import CENTRES  # noqa: E402

CENTRES["gcr"] = lambda: _gcr()


def _gcr():
    from jlm.mu import S14

    c = S14.make("chatread:64:mean=gnw0.3:a=1")
    c.name = "gcr"
    return c


# M4g: the finalist S14bL as a base for the frame projection (``on=b14bL``).
CENTRES["b14bL"] = lambda: centres.make("sched:40:kmx64+s14:template:64:mean=knnxd8l:a=0.5")


# M14: M4h (the whitened generic constant, then the fixed chat-punctuation subspace) as a base (``on=gcp``).
CENTRES["gcp"] = lambda: centres.make("s14:chatpunct:64:mean=gnw0.3:a=1")


# M19: fit a centre as the DM render's (``dmr:<centre>``): umot's mention bank is a chat render built from the DM pairs,
# so the generic constant must come from the chat pool (A's M1 picks the pool by family; the render is visible from the
# prompt, so this is not a label).
class AsDMRender:
    def __init__(self, inner: str) -> None:
        self.inner = centres.make(inner)
        self.name, self.doc = f"dmr:{inner}", f"{self.inner.doc} (fitted as the DM chat render)"
        self.needs_ctx = getattr(self.inner, "needs_ctx", False)

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.inner.fit(ref, "directed_modulation", groups, ctx=ctx) if self.needs_ctx else self.inner.fit(ref, "directed_modulation", groups)

    def transform(self, batch: Batch) -> torch.Tensor:
        return centres.apply(self.inner, batch)

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return 0, False


PARAMETRIC["dmr"] = AsDMRender


# M23: M1's whitening on the other generic pools at lam 0.3 (aliases without ':' for S14's ``mean=``).
for _pool in ("mwiki", "wshort", "nullp", "uncond"):
    CENTRES[f"gpw{_pool}"] = lambda pool=_pool: centres.make(f"m1:{pool}:0.3")
