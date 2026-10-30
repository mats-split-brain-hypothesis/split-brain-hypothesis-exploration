"""English glosses for non-English readout tokens, from the one-time table ``data/gloss/en.json``
(``experiments/build_gloss.py``: Haiku 5.5 over every non-English token of the vocabulary, built once). The dashboard
only reads it, never calls an API. A reading aid from an unpinned model, never used in scoring."""

import json
from pathlib import Path

import streamlit as st

TABLE = Path(__file__).resolve().parents[1] / "data" / "gloss" / "en.json"


@st.cache_resource
def table() -> dict[str, str]:
    try:
        return json.loads(TABLE.read_text())["gloss"]
    except (OSError, ValueError, KeyError):
        return {}


def gloss(text: str) -> str | None:
    """English for a decoded token's text, or None (English already, unknown, or no table)."""
    g = table().get(text.strip())
    return g if g and g != "?" else None
