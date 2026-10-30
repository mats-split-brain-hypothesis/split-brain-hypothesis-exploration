"""Item banks in the bench's ``items.json`` format: the frozen bench, and our dev banks.

A bank is ``(family, split)``. ``bench`` is WorkspaceBench's own file, read in place and never
copied. ``fit`` (fit and select centres) and ``val`` (confirm, LLM-judged) are dev banks under
``data/dev/<family>/<split>.json``, written in the same format so the bench's plan and judges
take them unchanged.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from wsbench import readplan
from wsbench.banks import exact_targets, item_targets, load_bank
from wsbench.registry import REPO_ROOT as WSBENCH_ROOT

from jlm import REPO_ROOT, models

DEV_ROOT = REPO_ROOT / "data" / "dev"
SPLITS = ("fit", "val", "bench")
#: Held-out dev splits read by name only (``typo/val2``), never iterated with SPLITS: they exist for a few families
#: (S24's val2: fresh items, no target shared with the bench, fit, val or each other), so loops over SPLITS skip them.
HELD_OUT = ("val2", "val2b", "val3")


@dataclass(frozen=True)
class Bank:
    family: str
    split: str
    path: Path
    header: dict[str, Any]
    items: list[dict[str, Any]]  # each with ``id`` (the readout id), as wsbench.banks.load_bank sets

    @property
    def name(self) -> str:
        return f"{self.family}/{self.split}"

    def by_id(self) -> dict[str, dict[str, Any]]:
        return {it["id"]: it for it in self.items}


def path_of(family: str, split: str) -> Path:
    if split == "bench":
        return WSBENCH_ROOT / "evals" / family / "items.json"
    if split not in SPLITS + HELD_OUT:
        raise ValueError(f"split {split!r} not in {SPLITS + HELD_OUT}")
    return DEV_ROOT / family / f"{split}.json"


def load(family: str, split: str) -> Bank:
    path = path_of(family, split)
    header, items = load_bank(path)
    return Bank(family, split, path, header, items)


#: Dev families imported from elsewhere, read on their own only: kept out of the pooled references and the screens that
#: iterate every dev family (poetry: the J++ paper's items, half of them WorkspaceBench bench prompts; see
#: experiments/import_jpp_poetry.py). chain / brew intermediates: fresh categories for J++ and our centres alike
#: (experiments/build_intermediates_dev.py), kept out so pooled refs and screens stay as the studies fitted them.
NOT_POOLED = ("poetry", "chain_intermediates", "brew_intermediates")


def dev_families() -> list[str]:
    """The dev families with a ``fit`` bank, those in :data:`NOT_POOLED` left out."""
    return sorted(p.parent.name for p in DEV_ROOT.glob("*/fit.json") if p.parent.name not in NOT_POOLED)


def targets(item: dict[str, Any]) -> list[str]:
    """The bench's target strings for a single-token item (the bank judge's rule)."""
    return exact_targets(item_targets(item))


def specs(bank: Bank) -> list[readplan.ReadSpec]:
    """The bench's read plan (render, positions rule, layers) applied to this bank's items."""
    if bank.split == "bench":
        out = readplan.plan(bank.family)
    else:
        with _plan_reads(bank):
            out = readplan.plan(bank.family)
        if [s.id for s in out] != [it["id"] for it in bank.items]:
            raise RuntimeError(f"{bank.name}: the bench's planner for this family does not read _bank")
    spec = models.current()
    if spec.bench_depth:  # the bench's grid is the 27B's: read the same relative depths in this model
        ref = models.MODELS[models.DEFAULT]
        out = [replace(s, layers=sorted({spec.depth(L, ref) for L in s.layers if spec.depth(L, ref) < spec.final_layer}))
               for s in out]
    return out


@contextmanager
def _plan_reads(bank: Bank) -> Iterator[None]:
    """Point ``readplan``'s bank loader at ``bank`` while planning (the bench is never edited)."""
    orig = readplan._bank

    def _bank(family: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        return (bank.header, bank.items) if family == bank.family else orig(family)

    readplan._bank = _bank
    try:
        yield
    finally:
        readplan._bank = orig
