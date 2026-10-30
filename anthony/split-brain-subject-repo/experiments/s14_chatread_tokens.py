"""S14c token sets from what the uncentred lens reads on generic chat text (mu-log, card S14c; no bench data).

For a sample of cells of the chat-format corpus (``out/ctx/corpus-chat.pt``: no_robots prompts rendered as the bench
renders, every position), take the uncentred cos readout's top 10 at each grid layer and count tokens. The most
frequent ones are the lens's own generic prior on chat text (template strings, and whatever genre openers it reads
everywhere), found without a bench cell. Fit / val targets are excluded, as for ``template``.

  python experiments/s14_chatread_tokens.py --device cuda [--per-item 16] [--top 256]

Writes ``data/template_tokens/chatread.json`` (all grid layers) and ``chatreadlate.json`` (layers >= 48).
"""

import argparse
import json
import random
from collections import Counter

import torch
from build_priors import TEMPLATE_DIR, target_ids, tokenizer, vocab_display
from umot.provenance import PINS

from jlm import context
from jlm.lens import MODEL, Lens

LAYERS = [20, 24, 28, 32, 36, 40, 44, 48, 52, 56, 60]


def write(name: str, counts: Counter, vocab: list[str], excluded: set[int], top: int, extra: dict) -> None:
    ids = [i for i, _ in counts.most_common() if i not in excluded][:top]
    toks = [{"id": i, "text": vocab[i], "sources": [f"chat readout top-10 count {counts[i]}"]} for i in ids]
    path = TEMPLATE_DIR / f"{name}.json"
    path.write_text(json.dumps({"name": name, "model": MODEL, "model_revision": PINS[MODEL], "n": len(toks),
                                "excluded_targets": len(excluded), **extra, "tokens": toks}, indent=1, ensure_ascii=False) + "\n")
    print(f"{path}: first 40: {[t['text'] for t in toks[:40]]}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--per-item", type=int, default=16, help="random positions per corpus text")
    ap.add_argument("--top", type=int, default=256)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    store = context.ContextStore(context.corpus_path("chat"))
    layers = [L for L in LAYERS if L in store.layers()]
    lens = Lens(layers, args.device)
    rng = random.Random(args.seed)
    cells = [(k, p) for k, it in store.items.items() for p in rng.sample(range(len(it.ids)), min(args.per_item, len(it.ids)))]
    print(f"{len(cells)} corpus cells, layers {layers}")
    allc, late = Counter(), Counter()
    for L in layers:
        for i in range(0, len(cells), 1024):
            H = torch.stack([store.states(k, L)[p] for k, p in cells[i : i + 1024]]).float()
            top = lens.scores(H, L, "cos").topk(10, dim=1).indices.flatten().tolist()
            allc.update(top)
            if L >= 48:
                late.update(top)
    vocab = vocab_display(tokenizer())
    excluded = target_ids(vocab)
    extra = {"source": "uncentred cos top-10 over chat-corpus cells", "n_cells": len(cells), "layers": layers}
    write("chatread", allc, vocab, excluded, args.top, extra)
    write("chatreadlate", late, vocab, excluded, args.top, {**extra, "layers": [L for L in layers if L >= 48]})


if __name__ == "__main__":
    main()
