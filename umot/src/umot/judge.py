"""``wsbench`` CLI with our judge-routing fixes; never edits the pinned bench.

    python -m umot.judge judge family=directed_modulation readouts=... out=... \
        judge_model=anthropic/claude-haiku-5.5 limit=3

Fix: some OpenRouter models (Claude Haiku 5.5) take no ``temperature`` at all, and the bench's
``provider.require_parameters`` turns a sent temperature into a 404 ("no endpoints"). For those
models the temperature is dropped, so their verdicts are sampled at the provider default, not
greedy: one more reason the numbers are unpinned. Also loads a gitignored ``.env`` if present.
"""

from __future__ import annotations

import functools
import os
import sys

from umot.provenance import REPO_ROOT

#: OpenRouter models without a ``temperature`` parameter (checked 2026-10-08 against
#: ``supported_parameters`` in https://openrouter.ai/api/v1/models).
NO_TEMPERATURE = frozenset({"anthropic/claude-haiku-5.5"})

#: First-party $ per million tokens (input, output), for the end-of-run cost line. The bench
#: tracks dollars on OpenRouter only; on the Anthropic route it counts tokens and drops them.
ANTHROPIC_PRICES = {"claude-haiku-5-5": (0.10, 0.50), "claude-sonnet-5": (2.0, 10.0)}
_SPENDS: dict[int, tuple[str, object]] = {}


def load_env(path=REPO_ROOT / ".env") -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        key, sep, value = line.strip().partition("=")
        if sep and key and not key.startswith("#"):
            os.environ.setdefault(key, value.strip().strip("'\""))


def patch() -> None:
    from wsbench import llm

    original = llm._openrouter_once

    @functools.wraps(original)
    async def once(*args, model, temperature, **kw):
        if model in NO_TEMPERATURE:
            temperature = None
        return await original(*args, model=model, temperature=temperature, **kw)

    llm._openrouter_once = once

    original_anthropic = llm._anthropic_once

    @functools.wraps(original_anthropic)
    async def anthropic_once(*args, model, spend, **kw):
        _SPENDS[id(spend)] = (model, spend)
        return await original_anthropic(*args, model=model, spend=spend, **kw)

    llm._anthropic_once = anthropic_once


def report_anthropic_usage() -> None:
    """Print token totals and an estimated cost for this run's Anthropic-route calls. Input
    tokens exclude cache reads, which bill at a tenth of the input price."""
    for model, spend in _SPENDS.values():
        tin, tout = spend.input_tokens, spend.output_tokens
        price = ANTHROPIC_PRICES.get(model)
        cost = f" ≈ ${(tin * price[0] + tout * price[1]) / 1e6:.4f}" if price else ""
        print(
            f"anthropic usage {model}: {spend.calls} calls, {tin} in, {tout} out{cost}"
        )


def main(argv: list[str] | None = None) -> int:
    load_env()
    patch()
    from wsbench.cli import main as wsbench_main

    try:
        return wsbench_main(argv if argv is not None else sys.argv[1:])
    finally:
        report_anthropic_usage()


if __name__ == "__main__":
    raise SystemExit(main())
