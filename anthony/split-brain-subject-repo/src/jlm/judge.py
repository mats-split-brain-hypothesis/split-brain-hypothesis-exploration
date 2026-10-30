"""The bench's LLM judge on any bank (bench or dev), without editing the bench.

The bench's judges read their bank from a hard-coded path; each judge kind is adapted here by
calling its family runner with our bank (``ADAPTED``): the single-token bank-judge families
(``wsbench.basic``, which take a bank path), user_modeling (its module-level ``load_bank`` is
pointed at our bank for the call), directed_modulation (its module-level ``BANK`` path, likewise)
and the multi-token families (``wsbench.multitoken.family.load_bank``, likewise; token bags go
through the bench's summarizer, then its regex contract). Spend rule (umot/CLAUDE.md): ``dry_run`` first, then ``limit=3``,
then a cost estimate; ask before anything over about $5 or a full arm.

Development judge: **Haiku 5.5 via OpenRouter** (``DEV_JUDGE``, unpinned; results stored under
``judged-claude-haiku-5.5*``, never WorkspaceBench scores), as in umot (user decision 2026-10-08): the pinned Gemini 3.8 Flash is capped at 20 requests per minute on our OpenRouter
account, so it is used for agreement samples and numbers of record only.
"""

import json
import os
from pathlib import Path

from wsbench import registry
from wsbench.judge_config import resolve
from wsbench.registry import JudgeArgs
from wsbench.results import FamilyResult, write_results

from jlm import REPO_ROOT
from jlm.banks import Bank
from umot import judge as umot_judge

DEV_JUDGE = "anthropic/claude-haiku-5.5"
BASIC = ("association", "basic_readout", "multihop", "multilingual", "poetry", "typo")
MULTI_TOKEN = ("typo_mt", "multihop_mt", "basic_readout_mt", "multilingual_mt", "multilingual_multihop", "multilingual_typo")
ADAPTED = (*BASIC, "user_modeling", "directed_modulation", *MULTI_TOKEN)


_PATCHED = False


def _patch_once() -> None:
    """umot's routing fix: drops the temperature OpenRouter rejects for Haiku 5.5."""
    global _PATCHED
    if not _PATCHED:
        umot_judge.patch()
        _PATCHED = True


def _load_env() -> None:
    """Keys from ``umot/.env`` if present (never printed); the environment wins."""
    path = REPO_ROOT / "umot" / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        k, sep, v = line.strip().partition("=")
        if sep and not k.startswith("#"):
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def judge(
    bank: Bank,
    readouts: Path,
    out: Path,
    *,
    judge_model: str | None = None,
    limit: int = 0,
    dry_run: bool = False,
    layers: list[int] | None = None,
    concurrency: int = 16,
    rpm: float = 240,
) -> FamilyResult:
    if bank.family not in ADAPTED:
        raise NotImplementedError(f"{bank.family}: no judge adapter yet (only {ADAPTED})")
    _load_env()
    _patch_once()
    registry.load_all()
    spec = registry.get(bank.family)
    args = JudgeArgs(
        readouts=readouts,
        out=out,
        judge=resolve(spec.judge, flag=judge_model, env=os.environ),
        layers=layers,
        items=None,
        limit=limit,
        allow_missing=False,
        concurrency=concurrency,
        rpm=rpm,
        dry_run=dry_run,
        aux_models=spec.judge.aux_models,
    )
    result = _run(bank, args)
    if not dry_run:
        write_results(out, result)
    return result


def _run(bank: Bank, args: JudgeArgs) -> FamilyResult:
    if bank.family in BASIC:
        from wsbench.basic.family import run_family

        return run_family(args, name=bank.family, bank=bank.path)
    if bank.family in MULTI_TOKEN:
        from wsbench.multitoken import family as mt

        orig_load = mt.load_bank
        mt.load_bank = lambda path: orig_load(bank.path)
        try:
            return mt.run_family(args, name=bank.family)
        finally:
            mt.load_bank = orig_load
    if bank.family == "directed_modulation":
        from wsbench.evals.directed_modulation import judge as dm

        orig_path = dm.BANK
        dm.BANK = bank.path
        try:
            return dm.run(args)
        finally:
            dm.BANK = orig_path
    from wsbench.evals.user_modeling import judge as um

    orig = um.load_bank
    um.load_bank = lambda family: json.loads(bank.path.read_text(encoding="utf-8"))
    try:
        return um.run(args)
    finally:
        um.load_bank = orig
