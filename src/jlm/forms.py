"""The "strict + forms" score: the strict rule (``jlm.score``) with each target's other forms accepted too.

Strict credits a readout token only when it spells the target itself, so ``swims`` fails an item whose target is
``swimming``. Here the accepted forms add a reviewed table, ``data/forms/<family>.json`` (``experiments/build_forms.py``):
inflections in every single-token family, and in association also derived words naming the same thing (swimmer).
Otherwise the rule is strict's: whole tokens, one leading space stripped, casefolded, any cell at any layer. The leak
exclusion uses the added forms too (a prompt spelling ``swim`` drops a ``swimming`` item), so the scored set can be
smaller than strict's; each block records its own n. Target ranks stay on strict's forms (they are written at read time).

Each bank also reports both scores on its reachable items alone (some accepted form is one vocabulary token): on
directed_modulation most concepts take several tokens and can never pass, which a rate over all items hides.
"""

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from jlm import REPO_ROOT, score
from jlm.banks import Bank

ROOT = REPO_ROOT / "data" / "forms"
key = score.form_key


def path_of(family: str) -> Path:
    return ROOT / f"{family}.json"


@cache
def table(family: str) -> dict[str, tuple[str, ...]]:
    """Target key -> its added forms (empty when the family has no table)."""
    p = path_of(family)
    return {k: tuple(v) for k, v in json.loads(p.read_text())["forms"].items()} if p.exists() else {}


def rule(family: str) -> str | None:
    p = path_of(family)
    return json.loads(p.read_text())["meta"].get("rule") if p.exists() else None


@dataclass(frozen=True)
class Scorer:
    """One bank's single-token scorer under one set of accepted forms (``extra`` empty: the bench's strict rule)."""

    bank: Bank
    extra: dict[str, tuple[str, ...]]
    accepted: dict[str, list[int]]  # item -> vocabulary ids spelling an accepted form
    conf: dict[str, str]  # item -> "" if scored, else why not

    @classmethod
    def of(cls, bank: Bank, vocab: list[str], prompt_tokens: dict[str, list[str]],
           extra: dict[str, tuple[str, ...]] | None = None) -> "Scorer":
        extra = extra or {}
        accepted = score.accepted_ids(vocab, bank, extra)
        return cls(bank, extra, accepted, score.confirmatory(bank, accepted, prompt_tokens, extra))

    @property
    def ids(self) -> list[str]:
        return [i for i, why in self.conf.items() if not why]

    @property
    def reachable(self) -> list[str]:
        return [i for i in self.ids if self.accepted[i]]

    @property
    def excluded(self) -> dict[str, int]:
        return {w: sum(1 for x in self.conf.values() if x == w) for w in sorted(set(self.conf.values())) if w}

    def passes(self, rows: list[dict[str, Any]]) -> dict[str, bool]:
        return score.strict_items(rows, self.bank, self.extra)


def arm_fields(strict: Scorer, extended: Scorer, rows: list[dict], masked: list[dict] | None = None,
               sem: list[dict] | None = None) -> tuple[dict[str, Any], dict[str, bool]]:
    """An arm's summary fields for both scores beyond strict's own rate, and its item passes under forms."""
    p = extended.passes(rows)
    block = {"strict": score.rate(p, extended.ids), "reachable": score.rate(p, extended.reachable),
             "strict_masked": score.rate(extended.passes(masked), extended.ids) if masked else None,
             "sem": score.rate(extended.passes(sem), extended.ids) if sem else None}
    return {"strict_reachable": score.rate(strict.passes(rows), strict.reachable), "forms": block}, p


def bank_fields(strict: Scorer, extended: Scorer) -> dict[str, Any]:
    """The bank's summary fields for both scores beyond strict's own (scored sets and counts)."""
    return {"n_reachable": len(strict.reachable),
            "forms": {"rule": rule(extended.bank.family), "table": str(path_of(extended.bank.family).relative_to(REPO_ROOT)),
                      "n_scored": len(extended.ids), "n_reachable": len(extended.reachable),
                      "excluded": extended.excluded, "scored_ids": extended.ids}}


# The strict + forms fields also live in their own file beside the bank summary, ``forms.json``, which code from before
# this score never reads or writes: an evaluate.py run on such a branch rewrites summary.json without these fields, and
# the dashboard (and the next run here) fills them back in from forms.json. An arm read after the last write has none
# until ``evaluate.py --rescore``.
SIDECAR = "forms.json"
ARM_KEYS = ("forms", "strict_reachable")
BANK_KEYS = ("forms", "n_reachable")


def write_sidecar(root: Path, result: dict[str, Any]) -> None:
    """Write the summary's strict + forms fields to ``root/forms.json``, kept on top of what the file already holds for
    the same scored items (arms whose fields the summary lost stay); nothing when the summary has none."""
    if "forms" not in result:
        return
    p = root / SIDECAR
    old = json.loads(p.read_text()) if p.exists() else {}
    if old.get("scored_ids") != result["scored_ids"]:
        old = {}
    doc = {"scored_ids": result["scored_ids"], "bank": {k: result[k] for k in BANK_KEYS if k in result},
           "arms": old.get("arms", {}) | {a: {k: v[k] for k in ARM_KEYS if k in v} for a, v in result["arms"].items()
                                          if "forms" in v},
           "diffs_forms": old.get("diffs_forms", {}) | result.get("diffs_forms", {})}
    tmp = root / (SIDECAR + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    tmp.replace(root / SIDECAR)


def fill_from_sidecar(root: Path, result: dict[str, Any]) -> dict[str, Any]:
    """Fill the strict + forms fields a summary lacks from ``root/forms.json`` (same scored items only); the summary's
    own fields win. Returns ``result``."""
    p = root / SIDECAR
    if not p.exists():
        return result
    doc = json.loads(p.read_text())
    if doc.get("scored_ids") != result.get("scored_ids"):
        return result
    for k, v in doc["bank"].items():
        result.setdefault(k, v)
    for a, fields in doc["arms"].items():
        if a in result["arms"] and "forms" not in result["arms"][a]:
            result["arms"][a] |= fields
    result["diffs_forms"] = {d: v for d, v in doc["diffs_forms"].items() if d.split(" - ")[0] in result["arms"]} | result.get(
        "diffs_forms", {})
    return result
