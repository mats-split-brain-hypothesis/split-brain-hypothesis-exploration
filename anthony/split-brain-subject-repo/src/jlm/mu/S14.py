"""S14 readout-aware subspace removal: ``g = P_B h`` with ``B`` the span of the lens's reading directions of a fixed
template-token set (notes/iteration-anthony/mu-log.md, card S14).

``B_l`` = orthonormal basis of ``{J_l^T W_U[t] : t in T}`` (over the cos denominators), ``T`` the first ``k`` tokens of
an ordered token set from ``data/template_tokens.json`` (``experiments/build_priors.py --template-tokens``: chat special
tokens, the tokens shared by the decoded family means, the most frequent chat-corpus tokens; never a target). The
bases are precomputed per layer by ``experiments/precompute_pullback.py --template-tokens`` under ``out/lens``.

- ``s14t<k>``: ``g = B B^T h`` (remove what the lens would read as the template; no reference cells at all).
- ``s14fam<k>``: ``g = mu_fam + B B^T (h - mu_fam)`` (pco's form with ``B`` in place of the family's PCs).
- ``s14r<k>`` / ``s14famr<k>``: controls, a random k-dimensional subspace (seeded per layer) in place of ``B``.

Parametric form ``s14:<set>:<k>[:fam][:rand][:<readout>][:mean=<centre>][:a=<alpha>]`` for other token sets built with
``--template-tokens --name``. ``mean=<centre>`` (any centre without ':' or '+', e.g. ``kmx64``) replaces the family mean
of ``:fam``, and ``a=<alpha>`` scales it (S14b): ``h - g = (I - P_B)(h - alpha g_mean(h))``. ``o=<gamma>`` over-removes
the subspace (S14o): ``h - g = (I - (1 + gamma) P_B) X``, so the template tokens' cos scores go negative instead of 0.
"""

import torch

from jlm import pullback
from jlm import centres
from jlm.centres import CENTRES, PARAMETRIC, Batch, CellRef, FamilyMean

OWNER = "Anthony"
CANDIDATES = ()


class TemplateSubspace:
    def __init__(self, k: int, token_set: str = "template", with_fam: bool = False, random: bool = False,
                 readout: str = "cos", seed: int = 0, name: str | None = None, mean: str = "fam", alpha: float = 1.0) -> None:
        self.k, self.token_set, self.with_fam, self.random, self.readout, self.seed = k, token_set, with_fam, random, readout, seed
        self.mean, self.alpha, self.over = mean, alpha, 0.0
        self.name = name or f"s14:{token_set}:{k}" + (":fam" if with_fam else "") + (":rand" if random else "")
        what = f"a random {k}-dim subspace" if random else f"the span of the lens's reading directions of the first {k} '{token_set}' tokens"
        self.doc = ((f"{alpha:g} x {mean} plus " if with_fam else "") + f"h's component in {what} removed"
                    + ("" if random else f" ({readout} map, precomputed basis)"))
        self.n_fallback = 0
        self.key = pullback.default_key()

    @property
    def needs_ctx(self) -> bool:
        return self.with_fam and getattr(self._base(), "needs_ctx", False)

    def _base(self):
        if not hasattr(self, "_base_centre"):
            self._base_centre = FamilyMean() if self.mean == "fam" else centres.make(self.mean)
        return self._base_centre

    def set_bank(self, family: str, items) -> None:
        if self.with_fam and hasattr(self._base(), "set_bank"):
            self._base().set_bank(family, items)

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.fam = None
        if self.with_fam:
            self.fam = self._base()
            self.fam.fit(ref, family, groups, ctx=ctx if getattr(self.fam, "needs_ctx", False) else None) \
                if self.mean != "fam" else self.fam.fit(ref, family, groups)
        self.d = next(iter(ref[0].acts.values())).shape[1]
        self._basis: dict[int, torch.Tensor] = {}

    def basis(self, layer: int) -> torch.Tensor:
        if layer not in self._basis:
            if self.random:
                g = torch.Generator().manual_seed(self.seed * 1000 + layer)
                self._basis[layer] = torch.linalg.qr(torch.randn(self.d, self.k, generator=g))[0]
            else:
                self._basis[layer] = pullback.load_tbasis(self.key, self.readout, self.token_set, self.k, layer).float()
        return self._basis[layer]

    def transform(self, batch: Batch) -> torch.Tensor:
        B = self.basis(batch.layer)
        X = batch.H if self.fam is None else batch.H - self.alpha * (batch.H - centres.apply(self.fam, batch))
        return X - (1.0 + self.over) * (X @ B) @ B.T

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return self.fam.support(cell) if self.fam is not None else (0, False)


def make(args: str):
    parts = args.split(":")
    token_set, k = parts[0], int(parts[1])
    opts = dict(p.split("=", 1) for p in parts[2:] if "=" in p)
    flags = [p for p in parts[2:] if "=" not in p]
    mean, alpha = opts.get("mean", "fam"), float(opts.get("a", 1.0))
    with_fam = "fam" in flags or "mean" in opts
    random, readout = "rand" in flags, "rms" if "rms" in flags else "cos"
    c = TemplateSubspace(k, token_set, with_fam, random, readout, name=f"s14:{args}", mean=mean, alpha=alpha)
    c.over = float(opts.get("o", 0.0))
    return c


PARAMETRIC["s14"] = make
for _k in (16, 64, 128):
    CENTRES[f"s14t{_k}"] = lambda k=_k: TemplateSubspace(k, name=f"s14t{k}")
    CENTRES[f"s14fam{_k}"] = lambda k=_k: TemplateSubspace(k, with_fam=True, name=f"s14fam{k}")
    CENTRES[f"s14r{_k}"] = lambda k=_k: TemplateSubspace(k, random=True, name=f"s14r{k}")
    CENTRES[f"s14famr{_k}"] = lambda k=_k: TemplateSubspace(k, with_fam=True, random=True, name=f"s14famr{k}")


# -- S14n: n-scaling of S14b's reference pool (steward's card) ------------------------------------------------------

class SubsampledClusterMean:
    """kmx<k> fitted on a seeded share of the fit pool's groups (items / DM pairs): ``kmxn:<k>:<frac>:<draw>``. The
    k-means seed stays 0; ``draw`` picks which groups are kept. ``frac = 1`` is kmx<k> itself."""

    def __init__(self, k: int, frac: float, draw: int) -> None:
        from jlm.mu.clusters import ClusterMean

        self.inner = ClusterMean(k, "bench")
        self.frac, self.draw = frac, draw
        self.name = f"kmxn:{k}:{frac:g}:{draw}"
        self.doc = f"{self.inner.doc}, on {frac:.0%} of the fit pool's groups (draw {draw})"
        self.n_fallback = 0

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        import random as _random

        from jlm.mu import clusters

        full = clusters.pool(("bench",), clusters.Pool.bench_fit)
        key = ("bench", "n", self.frac, self.draw)

        def sub() -> "clusters.Pool":
            gs = sorted(set(full.groups))
            keep = set(_random.Random(self.draw).sample(gs, max(1, round(self.frac * len(gs)))))
            rows = torch.tensor([j for j, g in enumerate(full.groups) if g in keep])
            return clusters.Pool({L: X[rows] for L, X in full.X.items()}, [full.groups[j] for j in rows.tolist()],
                                 [full.fams[j] for j in rows.tolist()], [full.toks[j] for j in rows.tolist()],
                                 [full.words[j] for j in rows.tolist()])

        self.inner.key = key
        self.inner.pool = clusters.pool(key, sub)
        self.inner.n_fallback = 0

    def transform(self, batch: Batch) -> torch.Tensor:
        out = self.inner.transform(batch)
        self.n_fallback = self.inner.n_fallback
        return out

    def support(self, cell: CellRef) -> tuple[int, bool]:
        return self.inner.support(cell)


def make_n(args: str) -> SubsampledClusterMean:
    k, frac, draw = args.split(":")
    return SubsampledClusterMean(int(k), float(frac), int(draw))


PARAMETRIC["kmxn"] = make_n
for _pct in (10, 25, 50):
    for _d in range(3):  # plain names, usable inside s14:...:mean=<centre> (whose options split on ':')
        CENTRES[f"kmx64n{_pct}d{_d}"] = lambda p=_pct, d=_d: SubsampledClusterMean(64, p / 100, d)


# -- S14bl: the late kNN without same-language neighbours (B's xcheck-S14bx: the multilingual_mt cost is S10's
# -- language subtraction, 58-83 % of the late neighbours share the prompt's language) ------------------------------

_LANG: dict[str, str] = {}
_CODE = {"arabic": "ar", "dutch": "nl", "french": "fr", "german": "de", "indonesian": "id", "italian": "it",
         "japanese": "ja", "korean": "ko", "polish": "pl", "portuguese": "pt", "spanish": "es", "turkish": "tr",
         "ukrainian": "uk", "english": "en"}  # the single-token banks name the language, the _mt banks give its code


def prompt_language(item_id: str) -> str:
    """The language the item's prompt is written in (the bank's ``lang`` field; English when absent). Prompt metadata,
    never the answer: S10 found that neighbours sharing it subtract the language name."""
    if not _LANG:
        from jlm import banks
        from jlm.mu.clusters import FAMILIES

        for f in FAMILIES:
            for split in banks.SPLITS + banks.HELD_OUT:
                try:
                    items = banks.load(f, split).items
                except (FileNotFoundError, ValueError):
                    continue
                for it in items:
                    lang = (it.get("lang") or "en").casefold()
                    _LANG[it.get("id") or it.get("name")] = _CODE.get(lang, lang)
    return _LANG.get(item_id, "en")


def _other_language_class():
    from jlm.mu.S16 import OtherCarrier

    class OtherLanguage(OtherCarrier):
        """knnxs<k> (other carrier) that also drops neighbours whose prompt is in the cell's own non-English language."""

        def __init__(self, k: int) -> None:
            super().__init__(k)
            self.name = f"knnxl{k}"
            self.doc += "; neighbours in the cell's own (non-English) prompt language excluded"

        def fit(self, ref, family, groups=None, ctx=None) -> None:
            super().fit(ref, family, groups, ctx)
            # one language list per source, kept apart on the shared pool (a detected arm and a bank-field arm can run
            # in one process: B's cross-check found the field arm reusing the detected list)
            attr = f"langs_{self.lang_source}"
            if not hasattr(self.pool, attr):
                from jlm import banks, capture
                from jlm.mu.clusters import FAMILIES

                langs = []
                for f in FAMILIES:
                    for it in capture.load(banks.load(f, "fit")):
                        langs += [self.cell_language(it.id)] * len(it.positions)
                assert len(langs) == len(self.pool.groups), "pool row order changed"
                setattr(self.pool, attr, langs)
            self.langs = getattr(self.pool, attr)

        lang_source = "field"

        def cell_language(self, item_id: str) -> str:
            return prompt_language(item_id)

        def _neighbours(self, batch: Batch) -> torch.Tensor:
            from jlm.mu.clusters import unit_space

            L = batch.layer
            X = self.pool.X[L].float()
            U, centre = unit_space(X)
            sims = unit_space(batch.H, centre)[0] @ U.T
            for j, cell in enumerate(batch.cells):
                own = self.pool.rows_of.get(cell.group)
                if own is not None:
                    sims[j, own] = -torch.inf
                it = batch.items[cell.item]
                from jlm.mu.S16 import _carrier_of

                car = _carrier_of(cell.family, cell.item)
                tail = tuple(it.decoded[max(0, it.idx[cell.i] - 5): it.idx[cell.i] + 1])
                lang = self.cell_language(cell.item)
                key = (car, tail, lang)
                memo = self.__dict__.setdefault("_clash_l", {})
                if key not in memo:
                    memo[key] = [r for r, (c, t) in enumerate(self.pool.carriers)
                                 if (car is not None and c == car) or t == tail or (lang != "en" and self.langs[r] == lang)]
                if memo[key]:
                    sims[j, memo[key]] = -torch.inf
            return sims.topk(min(self.k, len(X)), dim=1).indices

    return OtherLanguage


CENTRES["knnxl8"] = lambda: _other_language_class()(8)


# -- S14bL (steward's card): the same exclusion with the language *detected from the prompt's text* (no bank field) --

_SCRIPTS = [("ar", 0x0600, 0x06FF), ("he", 0x0590, 0x05FF), ("el", 0x0370, 0x03FF), ("cyr", 0x0400, 0x04FF),
            ("ko", 0xAC00, 0xD7AF), ("ja", 0x3040, 0x30FF), ("zh", 0x4E00, 0x9FFF), ("th", 0x0E00, 0x0E7F),
            ("hi", 0x0900, 0x097F)]
_FUNCTION_WORDS = {  # a handful of frequent function words per Latin-script language (hand list, no bench text)
    "fr": "le la les de des du et est un une que qui en dans pour pas au ce",
    "es": "el la los las de del y es un una que en por para con se lo",
    "de": "der die das und ist ein eine nicht zu den von mit auf im dem",
    "it": "il lo la gli le di e è un una che in per con non del della",
    "pt": "o a os as de do da e é um uma que em para com não no na",
    "nl": "de het een en is van in op dat niet met voor zijn te",
    "id": "yang dan di ini itu dengan untuk adalah dari ke tidak dalam",
    "tr": "ve bir bu da de için ile olan çok ne gibi daha",
    "pl": "i w na nie się to jest z że do jak co",
    "vi": "của và là có không một những được cho trong người các",
    "fi": "ja on ei se että hän oli kun niin mutta",
    "hu": "a az és hogy nem egy is van meg csak",
    "sw": "na ya wa kwa ni la za katika hii kama",
    "en": "the a an of and is in to that for it on with as was",
}
_FW = {lang: set(ws.split()) for lang, ws in _FUNCTION_WORDS.items()}
_LETTERS = {"pt": "ãõç", "es": "ñ¿¡", "pl": "łąęśźżćń", "tr": "ışğ", "hu": "őű", "de": "ß", "fr": "œêèàùâîôç",
            "fi": "", "vi": "ăđơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ", "it": "", "nl": "ĳ", "id": "", "sw": ""}


def detect_language(text: str) -> str:
    """A label-free guess of a prompt's language: the dominant non-Latin script if any (Cyrillic, Arabic, CJK, ...),
    else the Latin-script language whose function words the prompt uses most (English on a tie or no hit)."""
    import re as _re

    counts = {}
    for ch in text:
        o = ord(ch)
        for name, lo, hi in _SCRIPTS:
            if lo <= o <= hi:
                counts[name] = counts.get(name, 0) + 1
    letters = sum(ch.isalpha() for ch in text) or 1
    if counts and max(counts.values()) >= 0.3 * letters:
        return max(counts, key=counts.get)
    words = set(_re.findall(r"[^\W\d_]+", text.casefold()))
    english = {"a", "an", "die", "de", "in", "is", "to", "on", "as", "was", "it", "the", "and", "of", "for", "with", "that",
               "o", "e", "i", "w", "z", "no", "se", "ne", "do", "na", "van", "lo"}  # English words, or short / shared ones
    chars = set(text.casefold())
    scores = {lang: len((words & fw) - english) + 2 * len(chars & set(_LETTERS.get(lang, ""))) for lang, fw in _FW.items() if lang != "en"}
    best = max(scores, key=scores.get)
    return best if scores[best] >= 2 and scores[best] > len(words & _FW["en"]) else "en"


_DET: dict[str, str] = {}


def detected_language(item_id: str) -> str:
    if not _DET:
        from jlm import banks
        from jlm.mu.clusters import FAMILIES

        for f in FAMILIES:
            for split in banks.SPLITS + banks.HELD_OUT:
                try:
                    items = banks.load(f, split).items
                except (FileNotFoundError, ValueError):
                    continue
                for it in items:
                    text = it.get("prompt") or " ".join(m.get("content", "") for m in it.get("messages", []))
                    _DET[it.get("id") or it.get("name")] = detect_language(text)
    return _DET.get(item_id, "en")


def _detected_language_class():
    base = _other_language_class()

    class DetectedLanguage(base):
        def __init__(self, k: int) -> None:
            super().__init__(k)
            self.name = f"knnxd{k}l"
            self.doc = self.doc.replace("(non-English) prompt language", "(non-English) prompt language detected from its text")

        def cell_language(self, item_id: str) -> str:
            return detected_language(item_id)

        lang_source = "detected"

    return DetectedLanguage


CENTRES["knnxd8l"] = lambda: _detected_language_class()(8)
