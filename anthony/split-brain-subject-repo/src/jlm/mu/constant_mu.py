"""Constant-mu exploration (x1-x11, notes/predictions.md; dashboard page "Constant μ exploration"): centres that
need no family data, or only a few examples or one glossary entry.

- ``pos``: same-absolute-position mean (x1).
- ``cpt[c][+]:<word>:<alpha>``: one abstract word's carrier direction (x1); ``dict:<mode>:<alpha>``: a word per
  cell from the global dictionary (x2, x3, x5, x7).
- ``gen``, ``genx``, ``genk:<k>``, ``genfam``: the model's own same-kind prompts, written from the item itself or
  from k other items (x8-x10, experiments/x8_gen_refs.py).
- ``glos:<word|desc>``, ``glosx:desc``: texts the model wrote from one glossary entry (x11,
  experiments/x11_glossary_refs.py).

Moved here from ``centres.py`` unchanged in behaviour when the iteration branch's study-module layout was merged
(2026-10-11); arm names and stored readouts are the same.
"""

import json
from collections import defaultdict
from collections.abc import Hashable
from pathlib import Path

import torch
from umot.capture import ItemCapture

from jlm import OUT
from jlm.centres import CENTRES, PARAMETRIC, Batch, CellRef, FamilyMean, KeyedMean


class PosMean(KeyedMean):
    """Mean over reference cells at the same absolute position, clamped to the reference's
    deepest position, else the reference-wide mean. Qwen is a RoPE model, so there is no
    positional embedding to subtract from ``h``; this is the subtractable analogue, the
    position-correlated corpus mean E[h | position]. The fair cousin of umot's carpos: with a
    neutral corpus reference (``pos@corpus``) no prompt content can enter ``mu``."""

    def __init__(self, min_cells: int = 8) -> None:
        super().__init__(
            "pos",
            f"mean over reference cells at the same absolute position (>= {min_cells} cells, else the reference mean)",
            min_cells=min_cells,
            fallback=FamilyMean(),
        )
        self.cap = 0

    def key(self, cell: CellRef) -> Hashable:
        return (cell.family, min(len(cell.context) - 1, self.cap))

    def fit(self, ref: list[ItemCapture], family: str, groups: dict[str, str] | None = None, ctx=None) -> None:
        self.cap = max(i for it in ref for i in it.idx)
        super().fit(ref, family, groups)


#: Carrier capture for ConceptCentre (experiments/capture_mu_refs.py). Ids are ``word::k``.
CARRIERS = OUT / "captures" / "carriers.pt"

#: Words captured only as the contrast pool: unrelated to every family's category.
NEUTRAL_WORDS = ("giraffe", "violin", "glacier")


def _mean(items: list[ItemCapture], layer: int) -> torch.Tensor:
    rows = [it.acts[layer][k].float() for it in items if layer in it.acts for k in range(len(it.idx))]
    return torch.stack(rows).mean(0)


def _ref_norms(ref: list[ItemCapture], layer: int) -> torch.Tensor:
    return torch.stack([it.acts[layer][k].float().norm() for it in ref if layer in it.acts for k in range(len(it.idx))]).mean()


class ConceptCentre:
    """``mu = [ref mean +] alpha * s_l * v_l``: the README's abstract-word centre ("bunch of
    typos -> typo"). ``v_l`` is the unit mean state at the word's last token over a few neutral
    carrier phrases (never an item's target; the word is the family's label, one bit). ``s_l``
    is the reference cells' mean state norm, so ``alpha`` is in units of a typical ``||h||``
    (the family mean has ``||mu||/||h||`` = 0.81-0.98). ``contrast`` subtracts the
    :data:`NEUTRAL_WORDS`' mean in the same carriers, removing the carriers' own template prior
    (the README's steering-vector reading); ``plus_ref`` adds the reference mean, so
    ``cptc+:typo:0.5@sents`` reads "sentence-end mean + half-norm typo direction"."""

    def __init__(self, word: str, alpha: float, *, contrast: bool, plus_ref: bool, carriers: Path = CARRIERS) -> None:
        self.word, self.alpha, self.contrast, self.plus_ref = word, alpha, contrast, plus_ref
        self.carriers = carriers
        self.name = f"cpt{'c' if contrast else ''}{'+' if plus_ref else ''}:{word}:{alpha:g}"
        self.doc = (
            f"alpha={alpha:g} x ref mean-norm x unit '{word}' carrier direction"
            + (", neutral-word contrast" if contrast else "")
            + (", added to the ref mean" if plus_ref else "")
        )
        self.base = FamilyMean() if plus_ref else None

    def fit(self, ref: list[ItemCapture], family: str, groups: dict[str, str] | None = None, ctx=None) -> None:
        from umot import capture as ucap

        items = ucap.load(self.carriers)
        mine = [it for it in items if it.id.split("::")[0] == self.word]
        pool = [it for it in items if it.id.split("::")[0] in NEUTRAL_WORDS and not it.id.startswith(f"{self.word}::")]
        if not mine:
            raise ValueError(f"no carriers for {self.word!r} in {self.carriers}")
        if self.contrast and not pool:
            raise ValueError(f"no neutral-word carriers in {self.carriers}")
        layers = sorted(set.intersection(*(set(it.acts) for it in mine)))
        self.v: dict[int, torch.Tensor] = {}
        self.s: dict[int, torch.Tensor] = {}
        for L in layers:
            v = _mean(mine, L)
            if self.contrast:
                v = v - _mean(pool, L)
            self.v[L] = v / v.norm()
            self.s[L] = _ref_norms(ref, L)
        if self.base is not None:
            self.base.fit(ref, family, groups)

    def __call__(self, cell: CellRef) -> torch.Tensor:
        mu = self.alpha * self.s[cell.layer] * self.v[cell.layer]
        return mu + self.base(cell) if self.base is not None else mu

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return (self.base.support(cell)[0], False) if self.base is not None else (0, False)


#: Carrier capture for the full dictionary (experiments/capture_mu_refs.py --dict).
DICT_CARRIERS = OUT / "captures" / "carriers-dict.pt"


class DictCentre:
    """Per-cell abstract-word mu from the global dictionary (``data/abstract_concepts.json``):
    ``mu = alpha x s_l x v_hat(word(cell))``, the x1 construction with the word chosen per cell.

    Modes: ``fam`` = the family's word; ``strat`` = the item's bank stratum word (``subfamily``,
    ``attr_class``; category metadata, never a target), else the family's; ``derang`` = a fixed
    WRONG family's word (the specificity control); ``free`` = label-free, the dictionary word
    whose neutral-contrast carrier direction best matches the cell's own state (cosine after
    subtracting the sentence-end corpus mean, the one centre here that reads ``h``);
    ``llm`` = the word the pinned model itself judged fittest for the item's text
    (experiments/label_concepts.py; sees the prompt and the dictionary, never targets or the
    family name; unlabelled items fall back to the family's word, counted in ``n_fallback``).
    """

    def __init__(self, mode: str, alpha: float, *, carriers: Path = DICT_CARRIERS, sents: "Path | None" = None) -> None:
        self.plus_ref = mode.endswith("+")  # mu = ref mean + alpha x s x v (x5's out-of-the-box composition)
        base_mode = mode.removesuffix("+")
        if base_mode not in ("fam", "fam2", "strat", "derang", "free", "llm"):
            raise ValueError(f"dict mode {mode!r}")
        self.mode, self.alpha, self.carriers = base_mode, alpha, carriers
        self.sents = sents
        self.name = f"dict:{mode}:{alpha:g}"
        self.doc = f"alpha={alpha:g} x ref mean-norm x unit carrier direction, word per cell by {base_mode!r}" + (
            ", added to the ref mean" if self.plus_ref else ""
        )
        self.strata: dict[str, str] = {}
        self.labels: dict[str, str] = {}
        self.base = FamilyMean() if self.plus_ref else None
        self.n_fallback = 0

    def set_bank(self, family: str, items: list[dict]) -> None:
        """Stratum metadata for ``strat`` and judged labels for ``llm`` (ids and category
        words only, never targets)."""
        import json

        from jlm import concepts

        self.strata = concepts.stratum_words(family, items)
        if self.mode == "llm":
            for p in sorted((OUT / "concept-labels").glob(f"{family}-*.json")):
                self.labels.update(json.loads(p.read_text()))

    def fit(self, ref: list[ItemCapture], family: str, groups: dict[str, str] | None = None, ctx=None) -> None:
        from umot import capture as ucap

        from jlm import concepts
        from jlm.capture import REFS

        cfg = concepts.load()
        items = ucap.load(self.carriers)
        by_word: dict[str, list[ItemCapture]] = defaultdict(list)
        for it in items:
            by_word[it.id.split("::")[0]].append(it)
        words = [w for w in cfg["dictionary"] if w in by_word]
        neutral = [it for w in cfg["neutral"] for it in by_word.get(w, [])]
        if not words:
            raise ValueError(f"no dictionary carriers in {self.carriers}")
        layers = sorted(set.intersection(*(set(it.acts) for it in items)))
        self.v = {w: {} for w in words}  # word -> layer -> unit [d]
        self.vc = {w: {} for w in words}  # the neutral-contrast direction (selection only)
        self.s: dict[int, torch.Tensor] = {}
        for L in layers:
            n_mean = _mean(neutral, L)
            for w in words:
                v = _mean(by_word[w], L)
                self.v[w][L] = v / v.norm()
                c = v - n_mean
                self.vc[w][L] = c / c.norm()
            self.s[L] = _ref_norms(ref, L)
        self.words, self.family = words, family
        if self.mode == "free":
            sents = ucap.load(self.sents or REFS["sents"])
            self.m = {L: _mean(sents, L) for L in layers}
        if self.base is not None:
            self.base.fit(ref, family, groups)
        self.picked: dict = defaultdict(int)  # word -> cells, for reporting

    def word_of(self, cell: CellRef, h: torch.Tensor | None = None) -> str:
        from jlm import concepts

        if self.mode == "fam":
            return concepts.family_word(cell.family)
        if self.mode == "fam2":
            return concepts.load()["family_word_v2"][cell.family]
        if self.mode == "derang":
            return concepts.derangement_word(cell.family)
        if self.mode == "strat":
            return self.strata.get(cell.item) or concepts.family_word(cell.family)
        if self.mode == "llm":
            w = self.labels.get(cell.item, "?")
            if w in self.v:
                return w
            self.n_fallback += 1
            return concepts.family_word(cell.family)
        if h is None:
            raise ValueError(f"{cell.item} L{cell.layer}: dict:free needs the cell's state")
        x = h - self.m[cell.layer]
        x = x / x.norm()
        return max(self.words, key=lambda w: float(x @ self.vc[w][cell.layer]))

    def mu(self, cell: CellRef, h: torch.Tensor | None = None) -> torch.Tensor:
        w = self.word_of(cell, h)
        self.picked[w] += 1
        mu = self.alpha * self.s[cell.layer] * self.v[w][cell.layer]
        return mu + self.base(cell) if self.base is not None else mu

    def __call__(self, cell: CellRef) -> torch.Tensor:  # every mode but ``free``, which needs the state
        return self.mu(cell)

    def transform(self, batch: Batch) -> torch.Tensor:
        # ``free`` picks its word from the cell's own state; the other modes ignore it
        return batch.H - torch.stack([self.mu(c, batch.H[k]) for k, c in enumerate(batch.cells)])

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return (self.base.support(cell)[0], False) if self.base is not None else (0, False)


class GenMean:
    """Per-item mean over the item's SELF-GENERATED reference states (x8,
    experiments/x8_gen_refs.py): the model wrote ~8 prompts "of the same kind" from the item's
    visible context (never a target), captured at the matched read cell. mu(cell) = the mean of
    that item's reference states at the layer. Label-free and dataset-free; the practical
    approximation of the family mean. Items without references fall back to the reference-wide
    mean (counted in ``n_fallback``)."""

    name, doc = "gen", "mean of the item's self-generated same-kind reference states (x8)"
    mode = "own"

    def __init__(self) -> None:
        self.n_fallback = 0

    def fit(self, ref: list[ItemCapture], family: str, groups: dict[str, str] | None = None, ctx=None) -> None:
        from umot import capture as ucap

        paths = sorted((OUT / "captures").glob(f"gen-{family}-*.pt"))
        if not paths:
            raise FileNotFoundError(f"no gen-{family}-*.pt: run experiments/x8_gen_refs.py for this family")
        items = [it for p in paths for it in ucap.load(p)]  # indexed by item id, so any split reads
        # references of the items being fitted on only (@self: the read bank), so genx / genk / genfam draw their
        # example items from the bank itself, as x9 / x10 registered them, not from another split's generations
        keep = {it.id for it in ref}
        by_item: dict[str, list[ItemCapture]] = defaultdict(list)
        for it in items:
            iid = it.id.split("::")[0]
            if iid in keep:
                by_item[iid].append(it)
        if not by_item:
            raise ValueError(f"no generated references for any of the {len(keep)} reference items of {family}")
        layers = sorted({L for it in items for L in it.acts})
        self.n_refs = {iid: sum(len(g.idx) for g in gens) for iid, gens in by_item.items()}
        self.mu = {
            (iid, L): torch.stack([g.acts[L][k].float() for g in gens if L in g.acts for k in range(len(g.idx))]).mean(0)
            for iid, gens in by_item.items()
            for L in layers
        }
        self.wide = {L: torch.stack([v for (i, l), v in self.mu.items() if l == L]).mean(0) for L in layers}
        self.ids = sorted(by_item)
        self.n_items = len(self.ids)
        self.n_fallback = 0

    def sources(self, cell: CellRef) -> list[str] | None:
        """The items whose references make this cell's mu (None: not covered, use the pool)."""
        return [cell.item] if (cell.item, cell.layer) in self.mu else None

    def lookup(self, cell: CellRef) -> torch.Tensor | None:
        return self.mu.get((cell.item, cell.layer))

    def __call__(self, cell: CellRef) -> torch.Tensor:
        got = self.lookup(cell)
        if got is not None:
            return got
        self.n_fallback += 1
        return self.wide[cell.layer]

    def support(self, cell: CellRef) -> tuple[int, bool]:
        src = self.sources(cell)
        if src is None:
            return sum(self.n_refs.values()), True
        return sum(self.n_refs[s] for s in src), False


class GenOtherMean(GenMean):
    """x9 control for x8: the references of ANOTHER item of the family (a fixed derangement:
    the next item id in sorted order). Keeps synthetic same-kind prompts, breaks item matching."""

    name, doc, mode = "genx", "mean of another item's self-generated references (x9 control)", "other"

    def sources(self, cell: CellRef) -> list[str] | None:
        if cell.item not in self.ids:
            return None
        return [self.ids[(self.ids.index(cell.item) + 1) % self.n_items]]

    def lookup(self, cell: CellRef) -> torch.Tensor | None:
        src = self.sources(cell)
        return None if src is None else self.mu[(src[0], cell.layer)]


class GenSeedsMean(GenMean):
    """x10: the references of the k NEXT items in sorted id order (never the item's own): a
    synthetic family mean seeded from k example prompts. k=1 is ``genx``; k = all is ``genfam``."""

    mode = "seeds"

    def __init__(self, k: int) -> None:
        super().__init__()
        self.k = k
        self.name = f"genk:{k}"
        self.doc = f"mean of the self-generated references of {k} other items (x10 seed curve)"

    def sources(self, cell: CellRef) -> list[str] | None:
        if cell.item not in self.ids:
            return None
        j = self.ids.index(cell.item)
        return [self.ids[(j + s) % self.n_items] for s in range(1, min(self.k, self.n_items - 1) + 1)]

    def lookup(self, cell: CellRef) -> torch.Tensor | None:
        src = self.sources(cell)
        return None if src is None else torch.stack([self.mu[(s, cell.layer)] for s in src]).mean(0)


class GenFamilyMean(GenMean):
    """x9 control for x8: every OTHER item's self-generated references pooled (item-weighted, own
    item excluded) — a synthetic, dataset-free family mean."""

    name, doc, mode = "genfam", "pooled self-generated references of every other item (x9)", "family"

    def sources(self, cell: CellRef) -> list[str] | None:
        return [i for i in self.ids if i != cell.item]

    def lookup(self, cell: CellRef) -> torch.Tensor | None:
        own = self.mu.get((cell.item, cell.layer))
        if own is None:
            return self.wide[cell.layer]  # no own refs to exclude: the pool of every item
        return (self.wide[cell.layer] * self.n_items - own) / (self.n_items - 1)


class GenTokenMean(GenFamilyMean):
    """x17: the token-matched synthetic mean. For a read cell with token t: the mean over OTHER items' model-written
    reference cells (x8 / x12 generations, captured at every read token) reading t; fewer than ``min_cells`` such
    cells: the pooled synthetic mean (genfam). The no-dataset counterpart of the same-token mean."""

    name, doc, mode = "gentok", "other items' written references at the same read token, else genfam (x17)", "token"

    def __init__(self, min_cells: int = 3) -> None:
        super().__init__()
        self.min_cells = min_cells

    def fit(self, ref: list[ItemCapture], family: str, groups: dict[str, str] | None = None, ctx=None) -> None:
        from umot import capture as ucap

        super().fit(ref, family, groups, ctx)
        keep = {it.id for it in ref}
        self.tsum: dict = defaultdict(lambda: 0.0)
        self.tn: dict = defaultdict(int)
        self.own: dict = defaultdict(lambda: [0.0, 0])
        for p in sorted((OUT / "captures").glob(f"gen-{family}-*.pt")):
            for g in ucap.load(p):
                iid = g.id.split("::")[0]
                if iid not in keep:
                    continue
                for k in range(len(g.idx)):
                    tok = g.token(k)
                    for L, acts in g.acts.items():
                        h = acts[k].double()
                        self.tsum[L, tok] = self.tsum[L, tok] + h
                        self.tn[L, tok] += 1
                        o = self.own[iid, L, tok]
                        o[0], o[1] = o[0] + h, o[1] + 1
        self.n_token = 0

    def lookup(self, cell: CellRef) -> torch.Tensor | None:
        key = (cell.layer, cell.token)
        o = self.own.get((cell.item, *key), (0.0, 0))
        n = self.tn.get(key, 0) - o[1]
        if n >= self.min_cells:
            self.n_token += 1
            return ((self.tsum[key] - o[0]) / n).float()
        return super().lookup(cell)


#: x11 control: each family read with ANOTHER family's glossary entry (a fixed cycle).
GLOSSARY_SWAP = {"typo": "association", "association": "basic_readout", "basic_readout": "multihop",
                 "multihop": "multilingual", "multilingual": "typo",
                 "user_modeling": "directed_modulation", "directed_modulation": "user_modeling"}


class GlossaryMean:
    """x11: one constant mu per layer, the mean state of texts the model wrote from the family's
    glossary entry alone (experiments/x11_glossary_refs.py; ``word`` = the glossary word, ``desc``
    = word + a one-line definition of the situation). No bank item is seen. ``swap`` reads the
    family with another family's entry (the specificity control)."""

    def __init__(self, variant: str, swap: bool = False) -> None:
        self.variant, self.swap = variant, swap
        self.name = f"glos{'x' if swap else ''}:{variant}"
        self.doc = f"mean of texts written from {'another' if swap else 'the'} family's glossary entry ({variant})"

    def fit(self, ref: list[ItemCapture], family: str, groups: dict[str, str] | None = None, ctx=None) -> None:
        from umot import capture as ucap

        entry = GLOSSARY_SWAP[family] if self.swap else family
        # the chat families' control is the partner's entry written in this family's format (x11_glossary_refs)
        matched = OUT / "captures" / f"glos-{self.variant}-{entry}@{family}.pt"
        plain = OUT / "captures" / f"glos-{self.variant}-{entry}.pt"
        items = ucap.load(matched if self.swap and matched.exists() else plain)
        layers = sorted({L for it in items for L in it.acts})
        self.n = sum(len(it.idx) for it in items)
        self.mu = {L: torch.stack([it.acts[L][k].float() for it in items for k in range(len(it.idx))]).mean(0)
                   for L in layers}

    def __call__(self, cell: CellRef) -> torch.Tensor:
        return self.mu[cell.layer]

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return self.n, False


#: Families whose reference sets the universal (x14 A) centre averages: every WorkspaceBench family we read.
ALL_FAMILIES = ("typo", "association", "basic_readout", "multihop", "multilingual", "user_modeling", "directed_modulation")


def _set_mean(path: Path) -> dict[int, torch.Tensor]:
    """layer -> the mean state over every read cell of one reference capture."""
    from umot import capture as ucap

    items = ucap.load(path)
    layers = sorted({L for it in items for L in it.acts})
    return {L: torch.stack([it.acts[L][k].float() for it in items if L in it.acts for k in range(len(it.idx))]).mean(0)
            for L in layers}


class FileMean:
    """x14 C / D: one constant μ per layer, the mean over a per-family reference capture ``<prefix>-<family>.pt``
    (experiments/x14_null_uncond.py: ``null`` minimal prompts, ``uncond`` the model's unconditional text)."""

    def __init__(self, prefix: str) -> None:
        self.prefix, self.name = prefix, prefix
        self.doc = f"mean state of the {prefix} reference reads in the family's render (x14)"

    def fit(self, ref: list[ItemCapture], family: str, groups: dict[str, str] | None = None, ctx=None) -> None:
        self.mu = _set_mean(OUT / "captures" / f"{self.prefix}-{family}.pt")

    def __call__(self, cell: CellRef) -> torch.Tensor:
        return self.mu[cell.layer]

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return 0, False


class LensFitMean:
    """x20: one constant μ per layer, the mean state over the released J-lens's own fitting cells (wikitext-103 train,
    its first 1000 records of >= 600 characters, 128 tokens, positions 16 .. seq_len - 2; written by
    experiments/x20_fit_distribution.py): the centre the average-derivative reading of J asks for."""

    name, doc = "fitmu", "mean state over the J-lens's own fitting cells (x20)"

    def fit(self, ref: list[ItemCapture], family: str, groups: dict[str, str] | None = None, ctx=None) -> None:
        self.mu = {int(L): m.float() for L, m in torch.load(OUT / "captures" / "fitmu.pt")["mean"].items()}

    def __call__(self, cell: CellRef) -> torch.Tensor:
        return self.mu[cell.layer]

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return 0, False


class SentMean:
    """x23 A: μ = a × the mean of the input's OWN states at positions 1 .. t (``sent``; t the read cell) or 1 .. t-1
    (``sentx``). Position 0, the attention sink, is left out. Needs the bank's context capture (out/ctx)."""

    needs_ctx = True

    def __init__(self, a: float, with_read: bool) -> None:
        self.a, self.with_read = a, with_read
        self.name = f"{'sent' if with_read else 'sentx'}:{a:g}"
        self.doc = f"{a:g} x the mean of the input's own states, positions 1 .. {'t' if with_read else 't-1'} (x23)"
        self.n_fallback = 0

    def fit(self, ref: list[ItemCapture], family: str, groups: dict[str, str] | None = None, ctx=None) -> None:
        pass  # nothing to fit: μ comes from the input itself

    def transform(self, batch: Batch) -> torch.Tensor:
        assert batch.ctx is not None, "sent needs the bank's context capture (experiments/capture_ctx.py)"
        G = torch.zeros_like(batch.H)
        for j, c in enumerate(batch.cells):
            hi = batch.ctx.items[c.item].idx[c.i] + (1 if self.with_read else 0)
            if hi > 1:
                G[j] = self.a * batch.ctx.states(c.item, batch.layer)[1:hi].float().mean(0)
            else:
                self.n_fallback += 1
        return batch.H - G

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return 0, False


def _prefix_key(states: torch.Tensor, t: int) -> torch.Tensor | None:
    """The context key of a read cell at absolute index ``t``: the mean of positions 1 .. t-1 (as ``sentx:1``)."""
    return states[1:t].float().mean(0) if t > 1 else None


class SentNeighbours:
    """x23 B: μ = the mean of the read-cell states of the ``k`` dev fit cells whose own context key (the mean of their
    input's positions 1 .. t-1) is nearest to this cell's (cosine, same layer); the read item excluded. ``pool``:
    ``all`` the 7 single-token families' fit banks, ``others`` all but the read family. The sentence mean is only the
    key that finds similar situations; it is never subtracted."""

    needs_ctx = True

    def __init__(self, k: int, pool: str) -> None:
        assert pool in ("all", "others"), pool
        self.k, self.pool = k, pool
        self.name = f"sentnn:{k}:{pool}"
        self.doc = f"mean of the {k} fit read cells ({pool} families) nearest by context key (x23)"
        self.n_fallback = 0

    def fit(self, ref: list[ItemCapture], family: str, groups: dict[str, str] | None = None, ctx=None) -> None:
        from jlm import banks, capture, context

        fams = [f for f in ALL_FAMILIES if self.pool == "all" or f != family]
        self.keys, self.vals, self.ids = defaultdict(list), defaultdict(list), []
        for f in fams:
            bank = banks.load(f, "fit")
            store = context.ContextStore.of(bank)
            group = {m["id"]: m.get("pair_id") or m["id"] for m in bank.items}  # DM twins share a group
            for it in capture.load(bank):
                for i, t in enumerate(store.items[it.id].idx):
                    if t <= 1:
                        continue
                    self.ids.append(group[it.id])
                    for L, a in it.acts.items():
                        if L in store.items[it.id].acts:
                            self.keys[L].append(_prefix_key(store.states(it.id, L), t))
                            self.vals[L].append(a[i].float())
        self.K = {L: torch.nn.functional.normalize(torch.stack(v), dim=1) for L, v in self.keys.items()}
        self.V = {L: torch.stack(v) for L, v in self.vals.items()}

    def transform(self, batch: Batch) -> torch.Tensor:
        assert batch.ctx is not None, "sentnn needs the bank's context capture (experiments/capture_ctx.py)"
        K, V = self.K[batch.layer], self.V[batch.layer]
        G = torch.zeros_like(batch.H)
        for j, c in enumerate(batch.cells):
            q = _prefix_key(batch.ctx.states(c.item, batch.layer), batch.ctx.items[c.item].idx[c.i])
            if q is None:
                self.n_fallback += 1
                continue
            sim = K @ torch.nn.functional.normalize(q, dim=0)
            sim[[n for n, g in enumerate(self.ids) if g in (c.item, c.group)]] = -2.0  # never the read item or its twin
            G[j] = V[sim.topk(self.k).indices].mean(0)
        return batch.H - G

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return self.k, False


X23_WORDS = OUT / "captures" / "x23-words.json"


class WordMean:
    """x23 C: the pinned 27B names the input's context in one word (``ctx``) or what it is about (``topic``,
    experiments/x23_name_context.py); μ = the mean of the texts the model wrote from that word, read in the family's
    render (experiments/x23_word_refs.py: out/captures/x23-<kind>-<plain | user_modeling | directed_modulation>.pt,
    ids ``<word>::<k>``)."""

    def __init__(self, kind: str) -> None:
        assert kind in ("ctx", "topic", "ctx2", "ctx3", "ctx4"), kind  # x23 C; x23b
        self.kind, self.name = kind, f"word:{kind}"
        self.doc = f"mean of texts written from the one word the model names for the input ({kind}; x23)"
        self.n_fallback = 0

    def fit(self, ref: list[ItemCapture], family: str, groups: dict[str, str] | None = None, ctx=None) -> None:
        from umot import capture as ucap

        self.word = json.loads(X23_WORDS.read_text())[self.kind]
        render = family if family in ("user_modeling", "directed_modulation") else "plain"
        sums: dict = defaultdict(dict)  # every read cell of every text, as the glossary sets (_set_mean)
        for it in ucap.load(OUT / "captures" / f"x23-{self.kind}-{render}.pt"):
            w = it.id.rsplit("::", 1)[0]
            for L, a in it.acts.items():
                s, n = sums[w].get(L, (0.0, 0))
                sums[w][L] = (s + a.float().sum(0), n + a.shape[0])
        self.mu = {w: {L: s / n for L, (s, n) in by.items()} for w, by in sums.items()}

    def __call__(self, cell: CellRef) -> torch.Tensor:
        mu = self.mu.get(self.word.get(cell.item, ""))
        if mu is None:
            self.n_fallback += 1
            return torch.zeros(next(iter(next(iter(self.mu.values())).values())).shape)
        return mu[cell.layer]

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return 0, self.word.get(cell.item, "") not in self.mu


class GlossaryAll:
    """x14 A: ONE μ per layer for every family, the equal-weight mean of every family's glossary set of a variant
    (``word`` or ``desc``; each set read in its own family's render). Needs no choice of entry at read time."""

    def __init__(self, variant: str) -> None:
        self.variant, self.name = variant, f"glosall:{variant}"
        self.doc = f"mean over all families' glossary sets ({variant}), one μ for every family (x14)"

    def fit(self, ref: list[ItemCapture], family: str, groups: dict[str, str] | None = None, ctx=None) -> None:
        sets = [_set_mean(p) for f in ALL_FAMILIES if (p := OUT / "captures" / f"glos-{self.variant}-{f}.pt").exists()]
        if not sets:
            raise FileNotFoundError(f"no glos-{self.variant}-*.pt captures")
        layers = sorted(set.intersection(*(set(s) for s in sets)))
        self.n = len(sets)
        self.mu = {L: torch.stack([s[L] for s in sets]).mean(0) for L in layers}

    def __call__(self, cell: CellRef) -> torch.Tensor:
        return self.mu[cell.layer]

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return self.n, False


def _corpus_sample(layer_set=None, n: int = 8192, seed: int = 0) -> dict[int, torch.Tensor]:
    """layer -> [n, d] wikitext-103 states (positions 8 on), a seeded sample: the data-free reference of E and F."""
    from jlm import capture

    items = capture.load_ref("corpus8")
    layers = sorted({L for it in items for L in it.acts} if layer_set is None else layer_set)
    rows = [(it, k) for it in items for k in range(len(it.idx))]
    pick = torch.randperm(len(rows), generator=torch.Generator().manual_seed(seed))[:n].tolist()
    return {L: torch.stack([rows[i][0].acts[L][rows[i][1]].float() for i in pick if L in rows[i][0].acts]) for L in layers}


class CorpusPCRemoval:
    """x14 E: read (I - P_k)(h - m): m the wikitext mean, P_k the projection on the top-k principal directions of
    wikitext states (the data-free version of iteration's S7 family PCA). One fixed operation per layer."""

    def __init__(self, k: int) -> None:
        self.k, self.name = k, f"pcw:{k}"
        self.doc = f"remove the wikitext mean and its top {k} principal directions (x14)"

    def fit(self, ref: list[ItemCapture], family: str, groups: dict[str, str] | None = None, ctx=None) -> None:
        self.m, self.v = {}, {}
        for L, X in _corpus_sample().items():
            m = X.mean(0)
            _, _, V = torch.pca_lowrank(X - m, q=min(self.k + 8, *X.shape), center=False)
            self.m[L], self.v[L] = m, V[:, : self.k]

    def transform(self, batch: Batch) -> torch.Tensor:
        x = batch.H - self.m[batch.layer]
        v = self.v[batch.layer]
        return x - (x @ v) @ v.T

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return 8192, False


class MassiveDims:
    """x14 F: the k largest-magnitude dimensions of the wikitext mean state ("massive activations"), set to their
    wikitext mean (``massive``: their per-input variation removed) or to zero (``massivez``: removed)."""

    def __init__(self, k: int, zero: bool) -> None:
        self.k, self.zero = k, zero
        self.name = f"massive{'z' if zero else ''}:{k}"
        self.doc = f"the {k} largest wikitext-mean dimensions set to {'0' if zero else 'their wikitext mean'} (x14)"

    def fit(self, ref: list[ItemCapture], family: str, groups: dict[str, str] | None = None, ctx=None) -> None:
        self.m, self.dims = {}, {}
        for L, X in _corpus_sample().items():
            m = X.mean(0)
            self.m[L], self.dims[L] = m, m.abs().topk(self.k).indices

    def transform(self, batch: Batch) -> torch.Tensor:
        out = batch.H.clone()
        d = self.dims[batch.layer]
        out[:, d] = 0.0 if self.zero else self.m[batch.layer][d]
        return out

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return 8192, False


CENTRES.update({"pos": PosMean, "gen": GenMean, "genx": GenOtherMean, "genfam": GenFamilyMean})
CENTRES.update({"null": lambda: FileMean("null"), "uncond": lambda: FileMean("uncond"), "gentok": GenTokenMean})
CENTRES["fitmu"] = LensFitMean


def _dict(rest: str) -> DictCentre:
    mode, _, a = rest.partition(":")
    return DictCentre(mode, float(a or 1))


def _cpt(contrast: bool, plus_ref: bool):
    def make(rest: str) -> ConceptCentre:
        word, _, a = rest.partition(":")
        return ConceptCentre(word, float(a or 1), contrast=contrast, plus_ref=plus_ref)

    return make


PARAMETRIC.update({
    "genk": lambda rest: GenSeedsMean(int(rest)),
    "glos": lambda rest: GlossaryMean(rest),
    "glosx": lambda rest: GlossaryMean(rest, swap=True),
    "glosb": lambda rest: GlossaryMean("b" + rest),  # x13: the model-written (blind) entries, glos-bword / bdesc
    "glosall": lambda rest: GlossaryAll(rest),
    "pcw": lambda rest: CorpusPCRemoval(int(rest)),
    "massive": lambda rest: MassiveDims(int(rest), zero=False),
    "massivez": lambda rest: MassiveDims(int(rest), zero=True),
    "sent": lambda rest: SentMean(float(rest), with_read=True),  # x23 A
    "sentx": lambda rest: SentMean(float(rest), with_read=False),
    "sentnn": lambda rest: SentNeighbours(int(rest.split(":")[0]), rest.split(":")[1]),  # x23 B: sentnn:8:all
    "word": lambda rest: WordMean(rest),  # x23 C: word:ctx, word:topic
    "dict": _dict,
    "cpt": _cpt(False, False), "cptc": _cpt(True, False), "cpt+": _cpt(False, True), "cptc+": _cpt(True, True),
})
