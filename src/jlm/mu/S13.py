"""S13 pulled-back continuation prior: ``g = beta * M_l^+ c`` (notes/iteration-anthony/mu-log.md, card S13).

``c`` is a centred log-prior over the vocabulary and ``g`` its least-squares pullback through the readout map
(``jlm.pullback``), precomputed by ``experiments/precompute_pullback.py`` so that reading needs no ``W_U``:

- ``s13uni``: ``c`` = log unigram frequency of a chat-format corpus (``out/priors/unigram-norobots.pt``, built by
  ``experiments/build_priors.py``); one ``g`` per layer, no bench data, no family label.
- ``s13wiki``: the same from wikitext (a control: the prior of prose, not of chat-template cells).
- ``s13nt``: ``c`` = the model's own next-token log-softmax at a reference cell (layer 63 of the context capture,
  through the final norm and ``W_U``), pulled back per cell; ``g`` = the family mean of those pulled-back vectors,
  own group excluded (a ``FamilyMean`` over pulled-back "states": the mean of pullbacks is the pullback of the
  mean, so this is the pullback of the reference pool's average next-token log-prior). Other items only (S6c).
- ``s13ntf``: ``fam + s13nt``: the family mean plus the pulled-back prior of what is left.

Parametric form ``s13:<prior>:<beta>[:<readout>][:r<rank>]`` (``s13:unigram-norobots:0.5``, ``s13:nt:1:rms``,
``s13:unigram-norobots:1:cos:r256``, ``s13:unigram-norobots:2:fam`` = the family mean plus the scaled pullback): ``prior`` names a file under ``out/priors/pullback`` (``nt`` for the per-cell
files), ``beta`` scales ``g``, ``readout`` picks which map's pullback (default cos, the headline readout; the rms arm
may read the cos pullback, any ``g`` is a centre), ``rank`` the pullback's eigen-rank (default ``full``).
"""

import torch
from umot.capture import ItemCapture

from jlm import banks, pullback
from jlm.centres import CENTRES, PARAMETRIC, CellRef, FamilyMean

OWNER = "Anthony"
CANDIDATES = ()


class PulledPrior:
    """One pulled-back vector per layer, scaled: ``g = beta * g_prior[layer]``."""

    def __init__(self, prior: str, beta: float = 1.0, readout: str = "cos", rank: str | int = "full", name: str | None = None,
                 with_fam: bool = False) -> None:
        self.prior, self.beta, self.readout, self.rank, self.with_fam = prior, beta, readout, rank, with_fam
        self.name = name or f"s13:{prior}:{beta:g}" + ("" if readout == "cos" else f":{readout}") + ("" if rank == "full" else f":r{rank}")
        self.doc = (("family mean plus " if with_fam else "") + f"{beta:g} x the pullback of the {prior} log-prior through "
                    f"the {readout} readout map (rank {rank})" + ("" if with_fam else "; no reference cells"))
        self.n_fallback = 0

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        obj = pullback.load_prior(self.prior, self.readout, self.rank)
        self.g = {int(L): v.float() for L, v in obj["layers"].items()}
        self.meta = obj.get("meta", {})
        self.fam = None
        if self.with_fam:
            self.fam = FamilyMean()
            self.fam.fit(ref, family, groups)

    def __call__(self, cell: CellRef) -> torch.Tensor:
        if cell.layer not in self.g:
            raise KeyError(f"{self.name}: no pullback at layer {cell.layer} (have {sorted(self.g)}); rerun the precompute with it")
        g = self.beta * self.g[cell.layer]
        return g + self.fam(cell) if self.fam is not None else g

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return self.fam.support(cell) if self.fam is not None else (0, False)


def _pulled_items(ref: list[ItemCapture], family: str, readout: str, rank: str | int) -> list[ItemCapture]:
    """The reference items with their states replaced by the pullbacks of their cells' next-token log-softmax."""
    tables: dict[tuple[str, int], dict[int, torch.Tensor]] = {}
    for split in banks.SPLITS:
        try:
            obj = pullback.load_cells(family, split, readout, rank)
        except FileNotFoundError:
            continue
        for row, (item, i) in enumerate(obj["cells"]):
            tables[(item, i)] = {int(L): X[row] for L, X in obj["layers"].items()}
    if not tables:
        raise FileNotFoundError(f"no per-cell pullbacks for {family} ({readout}, rank {rank}); run "
                                f"experiments/precompute_pullback.py --next-token {family}/<split>")
    out = []
    for it in ref:
        rows = [tables.get((it.id, i)) for i in range(len(it.positions))]
        if any(r is None for r in rows):
            continue  # a reference item without a context capture contributes nothing
        layers = sorted(set.intersection(*(set(r) for r in rows)))
        out.append(ItemCapture(it.id, it.ids, it.decoded, it.positions, it.idx,
                               {L: torch.stack([r[L] for r in rows]) for L in layers}))
    if not out:
        raise ValueError(f"none of the {len(ref)} reference items of {family} has per-cell pullbacks")
    return out


class NextTokenPrior:
    """``g = beta * mean over the family's reference cells (own group excluded) of the pulled-back next-token
    log-softmax``; with ``with_fam``, plus the family mean of the states."""

    def __init__(self, beta: float = 1.0, readout: str = "cos", rank: str | int = "full", with_fam: bool = False, name: str | None = None) -> None:
        self.beta, self.readout, self.rank, self.with_fam = beta, readout, rank, with_fam
        self.name = name or f"s13:nt{'f' if with_fam else ''}:{beta:g}" + ("" if readout == "cos" else f":{readout}") + ("" if rank == "full" else f":r{rank}")
        self.doc = (("family mean plus " if with_fam else "") + f"{beta:g} x the family mean (own group excluded) of the "
                    f"pulled-back next-token log-softmax of the reference cells ({readout} map, rank {rank})")
        self.n_fallback = 0

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.inner = FamilyMean()
        self.inner.fit(_pulled_items(ref, family, self.readout, self.rank), family, groups)
        self.fam = None
        if self.with_fam:
            self.fam = FamilyMean()
            self.fam.fit(ref, family, groups)

    def __call__(self, cell: CellRef) -> torch.Tensor:
        g = self.beta * self.inner(cell)
        return g + self.fam(cell) if self.fam is not None else g

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return self.inner.support(cell)


def _parse(args: str):
    """``<prior>:<beta>[:<readout>][:r<rank>][:fam]``."""
    parts = args.split(":")
    prior, beta = parts[0], float(parts[1]) if len(parts) > 1 else 1.0
    readout, rank, with_fam = "cos", "full", False
    for p in parts[2:]:
        if p == "fam":
            with_fam = True
        elif p in ("cos", "rms"):
            readout = p
        elif p.startswith("r") and p[1:].isdigit():
            rank = int(p[1:])
        else:
            raise ValueError(f"s13: unknown option {p!r} in {args!r}")
    return prior, beta, readout, rank, with_fam


def make(args: str):
    prior, beta, readout, rank, with_fam = _parse(args)
    if prior in ("nt", "ntf"):
        return NextTokenPrior(beta, readout, rank, with_fam=prior == "ntf" or with_fam, name=f"s13:{args}")
    return PulledPrior(prior, beta, readout, rank, name=f"s13:{args}", with_fam=with_fam)


PARAMETRIC["s13"] = make
CENTRES["s13uni"] = lambda: PulledPrior("unigram-norobots", name="s13uni")
CENTRES["s13wiki"] = lambda: PulledPrior("unigram-wikitext", name="s13wiki")
CENTRES["s13nt"] = lambda: NextTokenPrior(name="s13nt")
CENTRES["s13ntf"] = lambda: NextTokenPrior(with_fam=True, name="s13ntf")
