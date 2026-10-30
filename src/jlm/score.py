"""The free scorers: jle's strict match (single-token families) and target rank.

Strict: a cell hits when one of its top-10 display tokens equals an accepted form after one
leading space is stripped and the string casefolded; whole tokens only. An item passes when any
of its cells hits at any layer. Scored items are jle's confirmatory subset (x89): reachable (a
target is a single word; it may still take several tokens, and then the item cannot pass), not
leaky (no prompt token spells a target; not applied to directed_modulation, whose prompt names
the concept by design), and for basic_readout not the implicit items. These are OUR numbers, a lower bound on the bench judge,
never "WorkspaceBench scores".

``extra`` (every scorer below): more accepted forms per target set, keyed by ``form_key`` of the item's own forms
(``jlm.forms``: inflections, the "strict + forms" score). Without it, the bench's strict rule.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

import numpy as np

from jlm.banks import Bank, targets

SEED = 0
RANK_CAP = 32767
NAMED_IN_PROMPT = {"directed_modulation"}  # the instruction names the concept: no leak exclusion  # jle's rank for a cell with no accepted vocabulary id
N_BOOT = 10_000


def normalise(piece: str) -> str:
    return (piece.removeprefix(" ")).casefold()


Extra = Mapping[str, Iterable[str]]


def form_key(forms: Iterable[str]) -> str:
    return "|".join(sorted(forms))


def accepted_forms(item: dict[str, Any], extra: Extra | None = None) -> frozenset[str]:
    base = frozenset(normalise(t) for t in targets(item) if t)
    return base | frozenset(extra.get(form_key(base), ())) if extra else base


def accepted_ids(vocab_display: list[str], bank: Bank, extra: Extra | None = None) -> dict[str, list[int]]:
    """Per item, the vocabulary ids whose display string normalises to an accepted form."""
    by_form: dict[str, list[int]] = defaultdict(list)
    for i, t in enumerate(vocab_display):
        by_form[normalise(t)].append(i)
    return {it["id"]: sorted({i for f in accepted_forms(it, extra) for i in by_form.get(f, [])}) for it in bank.items}


def confirmatory(bank: Bank, accepted: dict[str, list[int]], prompt_tokens: dict[str, list[str]],
                 extra: Extra | None = None) -> dict[str, str]:
    """Item id -> "" if scored, else the reason it is excluded. With ``extra``, a prompt token spelling any added
    form is a leak too; reachability stays the bench's (its own target is a single word)."""
    out = {}
    for it in bank.items:
        own = accepted_forms(it)
        forms = accepted_forms(it, extra)
        if not any(f and " " not in f for f in own):
            out[it["id"]] = "unreachable"
        elif bank.family not in NAMED_IN_PROMPT and any(normalise(t) in forms for t in prompt_tokens[it["id"]]):
            out[it["id"]] = "leak"
        elif bank.family == "basic_readout" and it.get("subfamily") == "implicit":
            out[it["id"]] = "implicit"
        else:
            out[it["id"]] = ""
    return out


def strict_items(rows: Iterable[dict[str, Any]], bank: Bank, extra: Extra | None = None) -> dict[str, bool]:
    """Item id -> passes (any cell at any layer has an accepted top-10 token)."""
    forms = {it["id"]: accepted_forms(it, extra) for it in bank.items}
    hit: dict[str, bool] = {it["id"]: False for it in bank.items}
    for r in rows:
        if not hit[r["id"]] and any(normalise(t) in forms[r["id"]] for t in r["tokens"]):
            hit[r["id"]] = True
    return hit


def best_rank(ranks: Iterable[dict[str, Any]]) -> dict[str, int]:
    """Item id -> best (lowest) target rank over its cells and layers; ``RANK_CAP`` when no
    vocabulary token spells a target."""
    out: dict[str, int] = {}
    for r in ranks:
        k = r["rank"] if r["rank"] >= 0 else RANK_CAP
        out[r["id"]] = min(out.get(r["id"], k), k)
    return out


def rate(passes: dict[str, bool], ids: list[str]) -> dict[str, Any]:
    """Pass rate over ``ids`` with a seeded item-bootstrap 95 % interval."""
    x = np.array([passes[i] for i in ids], dtype=float)
    if not len(x):
        return {"n": 0, "value": None, "ci95": None}
    rng = np.random.default_rng(SEED)
    boot = x[rng.integers(0, len(x), (N_BOOT, len(x)))].mean(1)
    return {"n": len(x), "value": float(x.mean()), "ci95": [float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))]}


def paired(a: dict[str, bool], b: dict[str, bool], ids: list[str]) -> dict[str, Any]:
    """Rate(a) - rate(b) over ``ids``, paired item bootstrap 95 % interval."""
    d = np.array([float(a[i]) - float(b[i]) for i in ids])
    if not len(d):
        return {"n": 0, "diff": None, "ci95": None}
    rng = np.random.default_rng(SEED)
    boot = d[rng.integers(0, len(d), (N_BOOT, len(d)))].mean(1)
    return {"n": len(d), "diff": float(d.mean()), "ci95": [float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))]}
