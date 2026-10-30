"""LLM-judged abstract-concept label per sample: the fittest dictionary word for each item.

  python experiments/label_concepts.py --family typo --split fit --device cuda
  python experiments/label_concepts.py --all-bench --device cuda   # the six x2 families + typo dev

The judge is the pinned Qwen3.6-27B itself (local, greedy, thinking off): it sees ONLY the item's
text and the dictionary (``data/abstract_concepts.json``) — never the target, never the family —
and names the TYPE of latent content the model holds at the end of the text. Labels go to
``out/concept-labels/<family>-<split>.json`` ({id: word}); generations that are not a dictionary
word are recorded and fall back to a prefix match, else ``"?"`` (DictCentre counts them).
"""

import argparse
import json

import torch
from umot.provenance import PINS, Provenance, write_artefact

from jlm import OUT, banks, concepts
from jlm.capture import MODEL, load_backend

LABELS = OUT / "concept-labels"
MAX_NEW = 6
FAMILIES = ("typo", "association", "basic_readout", "multihop", "multilingual", "user_modeling")

PROMPT = """Here is a text an AI model is reading:
---
{text}
---
At the end of this text the model holds one latent piece of content in mind: the thing it would \
say next, or the thing the text implies but never names. Which ONE word from this list best names \
the TYPE of that content?

List: {words}

Answer with exactly one word from the list."""


def item_text(item: dict) -> str:
    if item.get("prompt"):
        return item["prompt"]
    if item.get("messages"):
        return "\n".join(f"[{m['role']}]: {m['content']}" for m in item["messages"])
    raise ValueError(f"{item.get('id')}: no prompt or messages")


def pick(generated: str, words: list[str]) -> str:
    g = generated.strip().split()[0].strip(".,:;\"'").casefold() if generated.strip() else ""
    if g in words:
        return g
    for w in words:
        if g and (g.startswith(w) or w.startswith(g)):
            return w
    return "?"


def label_bank(backend, family: str, split: str, words: list[str]) -> None:
    bank = banks.load(family, split)
    tok = backend.tokenizer
    out: dict[str, str] = {}
    raw: dict[str, str] = {}
    for it in bank.items:
        msg = PROMPT.format(text=item_text(it), words=", ".join(words))
        ids = tok.apply_chat_template(
            [{"role": "user", "content": msg}], tokenize=True, add_generation_prompt=True, enable_thinking=False
        )
        ids = list(ids["input_ids"] if hasattr(ids, "keys") else ids)
        gen = backend.model.generate(
            torch.tensor([ids]).to(backend.model.device), max_new_tokens=MAX_NEW, do_sample=False,
            pad_token_id=tok.eos_token_id,
        )[0][len(ids):]
        raw[it["id"]] = tok.decode(gen, skip_special_tokens=True)
        out[it["id"]] = pick(raw[it["id"]], words)
    path = LABELS / f"{family}-{split}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1))
    write_artefact(
        path.with_suffix(".provenance.json"),
        Provenance(model=MODEL, model_revision=PINS[MODEL], dataset=f"jlm/{bank.name}",
                   extra={"judge": "self (greedy, thinking off)", "max_new_tokens": MAX_NEW}),
        {"items": len(out), "unmatched": sum(1 for w in out.values() if w == "?"),
         "raw_unmatched": {k: raw[k] for k, w in out.items() if w == "?"}},
    )
    from collections import Counter

    print(f"{family}/{split}: {dict(Counter(out.values()).most_common(8))}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--family")
    ap.add_argument("--split")
    ap.add_argument("--all-bench", action="store_true", help=f"{', '.join(FAMILIES)} bench + typo fit/val")
    ap.add_argument("--banks", default="", help="family/split,... in one model load")
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()
    torch.set_grad_enabled(False)
    cfg = concepts.load()["dictionary"]
    base = cfg[: cfg.index("age") + 1]  # x2's registered 30-word list; every existing label used it
    backend = load_backend(args.device)
    if args.banks:
        todo = [tuple(b.split("/")) for b in args.banks.split(",")]
    elif args.all_bench:
        todo = [(f, "bench") for f in FAMILIES] + [("typo", "fit"), ("typo", "val")]
    else:
        todo = [(args.family, args.split)]
    for family, split in todo:
        if (LABELS / f"{family}-{split}.json").exists():
            print(f"{family}/{split}: exists, skipping")
            continue
        words = base + (["instruction", "secret", "thought"] if family == "directed_modulation" else [])
        label_bank(backend, family, split, words)


if __name__ == "__main__":
    main()
