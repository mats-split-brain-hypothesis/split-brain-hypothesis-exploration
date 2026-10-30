"""Study S5: subtract the category word's own direction (notes/iteration-anthony/studies/S5.md).

The word states come from ``experiments/s5_words.py`` (``out/ctx/corpus-s5words.pt``): ``v_w`` = the state at a word's
last token in three neutral templates, averaged; ``v_0`` = the same for neutral words. The word direction is
``u_w = unit(v_w - v_0)`` per layer (several words: the unit of the mean of their directions). On top of the family mean,

    g = mu_fam + a ||h - mu_fam|| u_w        (a signed; a > 0 removes more of the word, a < 0 adds it back)

so the scale is relative to what the family mean leaves, one hyperparameter chosen on fit.

| centre | words |
|---|---|
| ``s5cat<a>`` | the family's category words (``CATEGORY`` below): the method |
| ``s5oth<a>`` | control: the next family's category words (an unrelated category) |
| ``s5rnd<a>`` | control: random everyday words |
| ``s5lang<a>`` | mechanism diagnostic, not a method: the item's language name (a target unit on multilingual_mt) on the two multilingual families, ``fam`` elsewhere |

``<a>``: m30, m15, p15, p30, p60 = -0.30, -0.15, +0.15, +0.30, +0.60.
"""

import json
from functools import lru_cache
from pathlib import Path

import torch

from jlm import REPO_ROOT
from jlm.centres import CENTRES, Batch, FamilyMean
from jlm.context import ContextStore, corpus_path

OWNER = "Anthony"  # dashboard pickers list these centres under "Anthony's centres" (catalog.owner)


# Fixed before any run (no targets, no item content); experiments/s5_words.py captures their states.
CATEGORY = {
    "typo": ["typo", "misspelling"], "typo_mt": ["typo", "error"],
    "association": ["association", "connection"],
    "basic_readout": ["fact", "answer"], "basic_readout_mt": ["fact", "answer"],
    "multihop": ["question", "answer"], "multihop_mt": ["question", "answer"],
    "multilingual": ["language", "translation"], "multilingual_mt": ["language", "translation"],
    "user_modeling": ["person", "user"], "directed_modulation": ["thought", "mind"],
}
RANDOM = ["table", "river", "window", "orange", "music", "garden"]
NEUTRAL = ["thing", "something", "stuff"]
LANGUAGES = {"de": "German", "fr": "French", "es": "Spanish", "it": "Italian", "pt": "Portuguese", "ru": "Russian",
             "zh": "Chinese", "ja": "Japanese", "ko": "Korean", "ar": "Arabic", "hi": "Hindi", "tr": "Turkish",
             "vi": "Vietnamese", "id": "Indonesian", "th": "Thai", "nl": "Dutch", "pl": "Polish", "sv": "Swedish",
             "fi": "Finnish", "el": "Greek", "he": "Hebrew", "uk": "Ukrainian", "cs": "Czech", "hu": "Hungarian",
             "ro": "Romanian", "fa": "Persian", "bn": "Bengali", "ms": "Malay", "sw": "Swahili", "tl": "Tagalog",
             "da": "Danish", "no": "Norwegian", "en": "English"}

SCALES = {"m30": -0.30, "m15": -0.15, "p15": 0.15, "p30": 0.30, "p60": 0.60}
FAMILIES = list(CATEGORY)


@lru_cache(maxsize=2)
def word_states(path: str) -> dict:
    """word -> layer -> [d] mean state at the word's last token over the templates."""
    store = ContextStore(Path(path))
    by: dict = {}
    for tid, row in store.items.items():
        w = tid.rsplit("|", 1)[0]
        for L, A in row.acts.items():
            by.setdefault(w, {}).setdefault(L, []).append(A[-1].float())
    return {w: {L: torch.stack(v).mean(0) for L, v in per.items()} for w, per in by.items()}


@lru_cache(maxsize=1)
def item_lang() -> dict:
    """item id -> English language name, for the multilingual dev banks (diagnostic arm only)."""
    out = {}
    for fam in ("multilingual", "multilingual_mt"):
        for p in (REPO_ROOT / "data" / "dev" / fam).glob("*.json"):
            for it in json.loads(p.read_text()).get("items", []):
                lang = it.get("lang")
                if lang:
                    out[it.get("id") or it["name"]] = LANGUAGES.get(lang, lang)
    return out


class WordDirection:
    def __init__(self, kind: str, tag: str, path=None) -> None:
        self.kind, self.a = kind, SCALES[tag]
        self.name = f"s5{kind}{tag}"
        self.doc = f"family mean plus {self.a:+g} ||h - mu_fam|| along the {kind} word direction"
        self.path = str(path or corpus_path("s5words"))
        self.fam = FamilyMean()
        self.n_fallback = 0

    def words(self, family: str, item: str) -> list[str]:
        if self.kind == "cat":
            return CATEGORY[family]
        if self.kind == "oth":
            return CATEGORY[FAMILIES[(FAMILIES.index(family) + 1) % len(FAMILIES)]]
        if self.kind == "rnd":
            return RANDOM
        lang = item_lang().get(item) if family in ("multilingual", "multilingual_mt") else None
        return [lang] if lang else []

    def direction(self, words: tuple[str, ...], layer: int) -> torch.Tensor | None:
        S = word_states(self.path)
        if not words or any(w not in S for w in words):
            return None
        base = torch.stack([S[w][layer] for w in NEUTRAL]).mean(0)
        d = torch.stack([S[w][layer] - base for w in words]).mean(0)
        return d / d.norm()

    def fit(self, ref, family, groups=None, ctx=None) -> None:
        self.fam.fit(ref, family, groups)

    def transform(self, batch: Batch) -> torch.Tensor:
        G = torch.stack([self.fam(c) for c in batch.cells])
        R = batch.H - G
        for j, c in enumerate(batch.cells):
            u = self.direction(tuple(self.words(c.family, c.item)), batch.layer)
            if u is None:
                self.n_fallback += 1
                continue
            G[j] = G[j] + self.a * R[j].norm() * u
        return batch.H - G

    def support(self, cell) -> tuple[int, bool]:
        return self.fam.support(cell)


for _kind in ("cat", "oth", "rnd", "lang"):
    for _tag in SCALES:
        CENTRES[f"s5{_kind}{_tag}"] = (lambda k, t: lambda: WordDirection(k, t))(_kind, _tag)
