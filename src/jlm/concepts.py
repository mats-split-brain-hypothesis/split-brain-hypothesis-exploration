"""The abstract-concept dictionary (``data/abstract_concepts.json``): global-workspace content
categories over the bench's data, and the per-family / per-stratum word maps.

A word is a category label (one bit of label information), never an item's target; stratum words
come from bank metadata fields (``subfamily``, ``attr_class``), which classify the latent without
naming it. The "no crystal ball" rule is kept by what is read here: ids and stratum fields only.
"""

import json
from functools import lru_cache
from typing import Any

from jlm import REPO_ROOT

PATH = REPO_ROOT / "data" / "abstract_concepts.json"


@lru_cache(maxsize=1)
def load() -> dict[str, Any]:
    return json.loads(PATH.read_text())


def family_word(family: str) -> str:
    return load()["family_word"][family]


def derangement_word(family: str) -> str:
    return load()["derangement"][family]


def stratum_words(family: str, items: list[dict[str, Any]]) -> dict[str, str]:
    """Item id -> stratum word, from the family's bank-metadata field; {} when it has none."""
    field = load()["stratum_field"].get(family)
    if not field:
        return {}
    words = load()["stratum_word"][family]
    return {it["id"]: words[it[field]] for it in items if it.get(field) in words}
