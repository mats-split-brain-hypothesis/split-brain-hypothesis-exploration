"""M29 (night-3 B; R5b): a genre library chosen by the cell's state (notes/iteration-anthony/mu-log.md, card M29).

X = default(h - delta_g), delta_g = mu_g - mu_0, with the M23 default ``s14:chatpunct:128:mean=gnw1:a=1`` (affine, so this
is the default's readout shifted by the genre offset) and g(h) the library genre whose offset from the library mean best
aligns with h's: argmax_g cos(h - mu_bar, mu_g - mu_bar). mu_0 = the glosnone constant (A's ``M1.pool_mean``).

Arms ``glib:<lib>[:rand|:oracle|:force=<genre>]``; libraries (captures under ``M1.CAPS``):
- ``desc`` / ``bdesc``: x11 / x13's pools written from the bench families' one-line definitions (``glos-desc-<f>``,
  ``glos-bdesc-<f>``, the five plain families): family-derived, an upper bound for the selection, labelled so;
- ``genre``: pools written from 8 surface genres chosen without the bench (``glos-genre-<g>``, M29's capture).
``rand``: a random genre per cell (seeded); ``oracle``: the read family's own pool (a family label: the labelled ceiling);
``force=<g>``: one genre for every cell. Chat renders (UM, DM): the default unchanged (the library is plain-render).
"""

import torch

from jlm import centres
from jlm.centres import PARAMETRIC, Batch, CellRef

PLAIN5 = ("typo", "association", "basic_readout", "multihop", "multilingual")
GENRES = ("misspelled", "list", "definition", "translation", "question", "scene", "riddle", "prose")
LIBS = {"desc": [(f, f"glos-desc-{f}.pt") for f in PLAIN5], "bdesc": [(f, f"glos-bdesc-{f}.pt") for f in PLAIN5],
        "genre": [(g, f"glos-genre-{g}.pt") for g in GENRES]}
DEFAULT = "s14:chatpunct:128:mean=gnw1:a=1"


class GenreLibrary:
    def __init__(self, lib: str, mode: str = "select", force: str | None = None) -> None:
        self.lib, self.mode, self.force = lib, mode, force
        self.name = f"glib:{lib}" + ("" if mode == "select" else f":{mode}" if mode != "force" else f":force={force}")
        self.doc = f"the M23 default shifted by the offset of the {lib} library's genre chosen per cell ({mode})"
        self.n_fallback, self.picked = 0, {}

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.family = family
        self.base = centres.make(DEFAULT)
        self.base.fit(ref, family, groups)
        self._mu: dict = {}

    def means(self, layer: int):
        if layer not in self._mu:
            from jlm.mu import M1

            names = [n for n, _ in LIBS[self.lib]]
            M = torch.stack([M1._capture_rows(f)[layer].mean(0) for _, f in LIBS[self.lib]])
            self._mu[layer] = (names, M, M1.pool_mean("glosnone", self.family, layer))
        return self._mu[layer]

    def transform(self, batch: Batch) -> torch.Tensor:
        from jlm.mu import M1

        if M1.render(self.family) == "chat":
            return centres.apply(self.base, batch)
        names, M, mu0 = self.means(batch.layer)
        n = len(batch.H)
        if self.mode == "oracle":
            pick = torch.full((n,), names.index(self.family) if self.family in names else 0)
        elif self.mode == "force":
            pick = torch.full((n,), names.index(self.force))
        elif self.mode == "rand":
            pick = torch.randint(len(names), (n,), generator=torch.Generator().manual_seed(batch.layer))
        else:
            bar = M.mean(0)
            sim = torch.nn.functional.normalize(batch.H.float() - bar, dim=1) @ torch.nn.functional.normalize(M - bar, dim=1).T
            pick = sim.argmax(1)
        for k in pick.tolist():
            self.picked[names[k]] = self.picked.get(names[k], 0) + 1
        shifted = Batch(batch.layer, batch.cells, batch.H - (M[pick] - mu0), batch.items, batch.ctx)
        return centres.apply(self.base, shifted)

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return 0, False


def make(args: str) -> GenreLibrary:
    parts = args.split(":")
    lib, mode, force = parts[0], "select", None
    for p in parts[1:]:
        if p in ("rand", "oracle"):
            mode = p
        elif p.startswith("force="):
            mode, force = "force", p[6:]
    return GenreLibrary(lib, mode, force)


PARAMETRIC["glib"] = make
