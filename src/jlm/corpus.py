"""Neutral text corpora rendered the way the bench renders its prompts, for priors and label-free pools.

``chat``: HuggingFaceH4/no_robots (10k human-written user requests, ungated, pinned), each prompt rendered as one user
turn through Qwen's chat template with the generation prompt and thinking off (``wsbench.produce.render._chat``), so
that its positions look like the bench's read cells (a chat-template cell, not prose). No bench text, no targets.
``wikitext``: jle x101's seeded windows (``jlm.wikitext``) of wikitext-103 validation (the prose control; J++'s router data).
"""

import random
from typing import Any

CHAT_REPO = "HuggingFaceH4/no_robots"
CHAT_REVISION = "e6f9a4ac5c37faeb744ba9ecf0473184d7f8105b"  # pinned 2026-10-11
CHAT_SPLIT = "train"


def chat_prompts(n: int = 0, seed: int = 0, revision: str = CHAT_REVISION) -> list[tuple[str, str, str]]:
    """``(id, category, prompt)`` for a seeded sample of ``n`` no_robots requests (all 9.5k when n = 0)."""
    import datasets

    ds = datasets.load_dataset(CHAT_REPO, split=CHAT_SPLIT, revision=revision)
    rows = [(f"chat-{r['prompt_id'][:12]}", r["category"], r["prompt"]) for r in ds]
    rows.sort()
    if n:
        rows = random.Random(f"chat:{seed}").sample(rows, min(n, len(rows)))
    return rows


def render_user(tokenizer: Any, text: str) -> list[int]:
    """One user turn plus the generation prompt, as the bench renders (``render._chat``)."""
    out = tokenizer.apply_chat_template([{"role": "user", "content": text}], tokenize=True,
                                        add_generation_prompt=True, enable_thinking=False)
    return list(out["input_ids"] if hasattr(out, "keys") else out)


def chat_renders(tokenizer: Any, n: int = 0, seed: int = 0, max_tokens: int = 0) -> list[tuple[str, list[int]]]:
    """``(id, token ids)`` of the rendered prompts, dropping those longer than ``max_tokens`` (0: keep all)."""
    out = []
    for cid, _, text in chat_prompts(n, seed):
        ids = render_user(tokenizer, text)
        if max_tokens and len(ids) > max_tokens:
            continue
        out.append((cid, ids))
    return out


def wikitext_windows(tokenizer: Any, n: int, seq: int, seed: int = 0) -> list[tuple[str, list[int]]]:
    """jle x101's sample: wikitext-103-raw validation (not the lens's fit split), seeded, <= 2 windows per passage."""
    from jlm import wikitext

    ids = wikitext.sample_ids(wikitext.passages(), tokenizer, n, seq, seed=seed)
    return [(f"wikitext-{k:04d}", w) for k, w in enumerate(ids)]
