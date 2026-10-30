"""A free proxy for the multi-token families on token bags: distinctive-piece match.

On a token bag the bench's regex contract cannot credit a multi-token form (no single token
spells it); the bench routes bags through an LLM summarizer first. This proxy instead credits a
form when one of its DISTINCTIVE pieces is among a cell's top-10 tokens. A form's pieces come
from the Qwen3.6-27B tokenizer (with and without a leading space; a leading article dropped).
A piece is distinctive when it has at least ``MIN_PIECE`` characters once spaces are stripped
and does NOT occur among the item's own prompt tokens. That rules out echoing the prompt: typo_mt's
misspelling shares " interpret" with "interpretability", and every Arabic prompt has " ال".
Single-token forms (e.g. "Arabic") count whole.

Units and forms come from the bench's ``regex.scored_units`` (the creditable forms only), and the
item rule is the bench's: an item passes at a layer when every REQUIRED unit hits there, at any
layer. A piece is weaker evidence than the form: calibrate against the summarizer path
before trusting it (``experiments/agreement.py``).
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from wsbench.multitoken import regex

from jlm.banks import Bank

ARTICLES = ("the ", "a ", "an ")
MIN_PIECE = 3  # a piece shorter than this (after stripping spaces) is too generic to count


@dataclass(frozen=True)
class Unit:
    role: str
    required: bool
    pieces: frozenset[str]  # display strings of accepted tokens
    ids: frozenset[int]


def _strip_article(form: str) -> str:
    low = form.lower()
    for a in ARTICLES:
        if low.startswith(a) and len(form) > len(a):
            return form[len(a):]
    return form


def units_of(bank: Bank, tokenizer: Any, display) -> dict[str, list[Unit]]:
    """Per item, its scored units with distinctive-piece token ids and display strings."""
    contract = regex.contract_for(bank.header, str(bank.header.get("family", bank.family)))
    out: dict[str, list[Unit]] = {}
    for it in bank.items:
        prompt_ids = tokenizer(it.get("prompt", ""), add_special_tokens=False)["input_ids"]
        in_prompt = {t.strip().casefold() for t in display(prompt_ids)}  # spacing and case ignored
        units = []
        for u in regex.scored_units(it, contract):
            ids: set[int] = set()
            for f in (f for forms in u.forms.values() for f in forms):
                f = _strip_article(f)
                for variant in (f, " " + f):
                    toks = tokenizer(variant, add_special_tokens=False)["input_ids"]
                    if len(toks) == 1:
                        ids.add(toks[0])
                        continue
                    for t, name in zip(toks, display(toks), strict=True):
                        if name.strip().casefold() not in in_prompt and len(name.strip()) >= MIN_PIECE:
                            ids.add(t)
            units.append(Unit(u.role, u.required, frozenset(display(sorted(ids))), frozenset(ids)))
        out[it["id"]] = units
    return out


def item_passes(rows: Iterable[dict[str, Any]], units: dict[str, list[Unit]]) -> dict[str, bool]:
    """Item -> some layer where every required unit has a distinctive piece in a top-10."""
    hits: dict[tuple[str, int], set[str]] = defaultdict(set)
    for r in rows:
        toks = set(r["tokens"])
        for u in units.get(r["id"], []):
            if toks & u.pieces:
                hits[r["id"], r["layer"]].add(u.role)
    out = {i: False for i in units}
    for (i, _layer), roles in hits.items():
        req = {u.role for u in units[i] if u.required}
        if req and req <= roles:
            out[i] = True
    return out


def reachable(units: dict[str, list[Unit]]) -> dict[str, bool]:
    """An item is scorable when every required unit has at least one accepted piece."""
    return {i: all(u.ids for u in us if u.required) and any(u.required for u in us) for i, us in units.items()}
