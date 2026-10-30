"""S14 token sets beyond ``template`` (mu-log, card S14), in ``data/template_tokens/<name>.json``:

- ``chatonly``: the chat template's special tokens, then the most frequent tokens of the chat corpus (no_robots rendered
  as the bench renders), in frequency order. No bench data at all: no decoded family means, no hand list.
- ``randfreq<seed>``: the card's control. Each token of ``template`` (in order) replaced by a random token of similar
  chat-corpus frequency (unigram rank within a factor 1.25 either side, +-8, widened where the head is used up; specials and zero-count tokens matched among
  the zero-count tokens), never a token of ``template`` or a target.

  python experiments/s14_token_sets.py [--top 256] [--seed 0]

Bases from ``precompute_pullback.py --template-tokens chatonly`` (pod); read as ``s14:chatonly:<k>[:fam]``.
"""

import argparse
import json
import random

import torch
from build_priors import CHAT_SPECIAL, TEMPLATE_DIR, target_ids, tokenizer, vocab_display
from umot.provenance import PINS

from jlm.lens import MODEL
from jlm.pullback import PRIORS


def write(name: str, ids: list[int], vocab: list[str], sources: list[str], extra: dict) -> None:
    toks = [{"id": i, "text": vocab[i], "sources": [s]} for i, s in zip(ids, sources)]
    path = TEMPLATE_DIR / f"{name}.json"
    path.write_text(json.dumps({"name": name, "model": MODEL, "model_revision": PINS[MODEL], "n": len(toks), **extra,
                                "tokens": toks}, indent=1, ensure_ascii=False) + "\n")
    print(f"{path}: {len(toks)} tokens; first 24: {[t['text'] for t in toks[:24]]}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--top", type=int, default=256)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    tok = tokenizer()
    vocab = vocab_display(tok)
    excluded = target_ids(vocab)
    counts = torch.load(PRIORS / "unigram-norobots.pt", weights_only=False)["counts"][: len(vocab)]
    # chatonly
    ids, src = [], []
    for t in CHAT_SPECIAL:
        ids.append(tok.convert_tokens_to_ids(t)); src.append("special")
    for i in counts.argsort(descending=True).tolist():
        if len(ids) >= args.top:
            break
        if i not in ids and i not in excluded:
            ids.append(i); src.append("chat unigram")
    write("chatonly", ids, vocab, src, {"excluded_targets": len(excluded), "source": "no_robots chat renders, frequency order"})
    # randfreq: frequency-matched random replacements of template
    T = [t["id"] for t in json.loads((TEMPLATE_DIR / "template.json").read_text())["tokens"]]
    order = counts.argsort(descending=True)
    rank = torch.empty_like(order); rank[order] = torch.arange(len(order))
    zero = [i for i in range(len(vocab)) if counts[i] <= 1 and i not in excluded and i not in T]
    rng = random.Random(args.seed)
    used, out, src = set(T), [], []
    for t in T:
        r = int(rank[t])
        if counts[t] <= 1:
            pool = zero
        else:
            pool, w = [], 8
            while not pool:  # the head of the vocabulary is mostly template tokens or targets: widen until free
                lo, hi = max(0, int(r / 1.25) - w), int(r * 1.25) + w
                pool = [i for i in order[lo:hi].tolist() if i not in used and i not in excluded and counts[i] > 1]
                w *= 2
        i = rng.choice([p for p in pool if p not in used])
        used.add(i); out.append(i); src.append(f"matches {vocab[t]!r} (rank {r})")
    write(f"randfreq{args.seed}", out, vocab, src, {"excluded_targets": len(excluded), "control_of": "template", "seed": args.seed})


if __name__ == "__main__":
    main()
