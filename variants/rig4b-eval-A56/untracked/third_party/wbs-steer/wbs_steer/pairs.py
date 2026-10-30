"""The think / don't-think pairs of WorkspaceBench's directed_modulation family (paper §3.1)."""

import json
from pathlib import Path


def load_pairs(items_path: str | Path) -> list[tuple[dict, dict]]:
    """``[(think, dont_think), ...]``, each a chat prompt ``{"user": ..., "assistant": ...}``.

    Only the ``pair`` subfamily is used (35 pairs); the secret and preference items are left out.
    """
    items = json.loads(Path(items_path).read_text())["items"]
    by_pair: dict[str, dict[str, dict]] = {}
    for it in items:
        if it.get("subfamily") != "pair":
            continue
        by_pair.setdefault(it["pair_id"], {})[it["polarity"]] = {"user": it["prompt"], "assistant": it["assistant"]}
    pairs = []
    for pid in sorted(by_pair):
        p = by_pair[pid]
        if "think" in p and "dont_think" in p:
            pairs.append((p["think"], p["dont_think"]))
    return pairs
