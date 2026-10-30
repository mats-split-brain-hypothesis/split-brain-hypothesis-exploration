"""Reference captures for the corpus- and concept-based centres, in one model load (80 GB GPU).

  python experiments/capture_mu_refs.py --device cuda [--n-passages 256] [--n-sents 256]

Writes, in umot's ``ItemCapture`` format, at the typo plan's layers plus umot's reader layer:

  out/captures/corpus-wiki.pt   wikitext-103-raw VALIDATION paragraphs (x101's corpus, pin and
                                detokenisation; passage starts, not x101's mid-passage windows,
                                so absolute position means a position in a fresh text), first
                                SEQ tokens of each, captured at EVERY position. The reference
                                for ``pos@corpus`` and (from position 8 on) ``fam@corpus8`` /
                                ``tok@corpus8``.
  out/captures/sents-wiki.pt    standalone wikitext sentences (6..40 tokens), captured at the
                                final token: "similar, neutral contexts" for reads at the end
                                of a short text (``fam@sents``).
  out/captures/carriers.pt      each concept word in the CARRIER templates, captured at the
                                word's last token: the abstract-word direction for ``cpt:<word>``
                                (README: "bunch of typos -> typo"); ids are ``word::k``.
"""

import argparse
import re

import torch
from umot.capture import ItemCapture
from umot.provenance import PINS, Provenance, write_artefact

from jlm import OUT, banks
from jlm.capture import MODEL, load_backend
from jlm.mu.constant_mu import NEUTRAL_WORDS

SEED = 0
SEQ = 64
MIN_PASSAGE_TOKENS = 16
SENT_TOKENS = (6, 40)

#: Concept words per family (the family's label, one bit) plus the neutral contrast pool.
CONCEPT_WORDS = ("typo", "misspelling", "spelling", "error")
WORDS = CONCEPT_WORDS + NEUTRAL_WORDS


def carrier_texts(word: str) -> list[str]:
    a = "an" if word[0] in "aeiou" else "a"
    return [
        word,
        f"the {word}",
        f"This sentence contains {a} {word}.",
        f"I noticed {a} {word} in the text.",
        f"Think about the concept of {a} {word}.",
    ]


def wikitext_detok(s: str) -> str:
    """x101's standard wikitext detokenisation (jle/experiments/x101_generic_mean.py)."""
    s = s.replace("s '", "s'")
    s = re.sub(r"/' [0-9]/", r"/'[0-9]/", s)
    s = s.replace(" @-@ ", "-").replace(" @,@ ", ",").replace(" @.@ ", ".")
    s = s.replace(" : ", ": ").replace(" ; ", "; ").replace(" . ", ". ")
    s = s.replace(" ! ", "! ").replace(" ? ", "? ").replace(" , ", ", ")
    s = re.sub(r"\(\s*([^\)]*?)\s*\)", r"(\1)", s)
    s = re.sub(r"\[\s*([^\]]*?)\s*\]", r"[\1]", s)
    s = re.sub(r"{\s*([^}]*?)\s*}", r"{\1}", s)
    s = re.sub(r"\"\s*([^\"]*?)\s*\"", r'"\1"', s)
    s = re.sub(r"'\s*([^']*?)\s*'", r"'\1'", s)
    s = s.replace("= = = =", "====").replace("= = =", "===").replace("= =", "==")
    s = s.replace(" " + chr(176) + " ", chr(176)).replace(" \n", "\n").replace("\n ", "\n")
    s = s.replace(" N ", " 1 ").replace(" 's", "'s")
    if s.endswith(" ."):
        s = s[:-2] + "."
    return s


def wikitext_paragraphs() -> list[str]:
    import datasets

    from jlm import wikitext

    ds = datasets.load_dataset(
        "Salesforce/wikitext", "wikitext-103-raw-v1", split="validation", revision=wikitext.REVISION
    )
    return [wikitext_detok(t.strip()) for t in ds["text"] if t.strip() and not t.strip().startswith("=")]


def shuffled(xs: list, tag: str) -> list:
    import random

    xs = list(xs)
    random.Random(f"jlm-mu-refs:{tag}:{SEED}").shuffle(xs)
    return xs


def cap_text(backend, iid: str, text: str, layers: list[int], idx: list[int] | None = None) -> ItemCapture:
    """Capture ``text`` under the plain render (the typo families') at ``idx`` (default: all)."""
    ids = backend.tokenizer(text, add_special_tokens=False)["input_ids"][:SEQ]
    idx = list(range(len(ids))) if idx is None else [i for i in idx if i < len(ids)]
    acts = backend.capture(ids, layers, idx)
    return ItemCapture(
        id=iid,
        ids=list(ids),
        decoded=[backend.tokenizer.decode([i]) for i in ids],
        positions=list(idx),
        idx=list(idx),
        acts={L: acts[L].to(torch.bfloat16) for L in layers},
    )


def word_last_idx(tokenizer, text: str, word: str) -> int:
    enc = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
    end = text.rindex(word) + len(word)
    hits = [i for i, (s, e) in enumerate(enc["offset_mapping"]) if s < end and e >= end]
    if not hits:
        hits = [i for i, (s, _) in enumerate(enc["offset_mapping"]) if s < end]
    return hits[-1]


def save(items: list[ItemCapture], name: str, dataset: str, extra: dict) -> None:
    from umot import capture as ucap

    path = OUT / "captures" / name
    ucap.save(items, path)
    write_artefact(
        path.with_suffix(".provenance.json"),
        Provenance(model=MODEL, model_revision=PINS[MODEL], dataset=dataset, extra=extra),
        {"items": len(items), "cells": sum(len(i.idx) for i in items)},
    )
    print(f"{path}: {len(items)} items, {sum(len(i.idx) for i in items)} cells", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--n-passages", type=int, default=256)
    ap.add_argument("--n-sents", type=int, default=256)
    ap.add_argument("--dict-carriers", action="store_true",
                    help="capture ONLY the full dictionary's carriers (data/abstract_concepts.json) to carriers-dict.pt")
    args = ap.parse_args()
    torch.set_grad_enabled(False)
    torch.set_float32_matmul_precision("highest")

    spec = banks.specs(banks.load("typo", "fit"))[0]
    from umot.capture import READER_LAYER

    layers = sorted({*spec.layers, READER_LAYER})
    backend = load_backend(args.device)
    tok = backend.tokenizer

    if args.dict_carriers:
        from jlm import concepts

        cfg = concepts.load()
        words = [*cfg["dictionary"], *cfg["neutral"]]
        carriers = [
            cap_text(backend, f"{w}::{k}", text, layers, idx=[word_last_idx(tok, text, w)])
            for w in words
            for k, text in enumerate(carrier_texts(w))
        ]
        save(carriers, "carriers-dict.pt", "jlm carrier templates (full dictionary)",
             {"words": words, "neutral": cfg["neutral"], "templates": carrier_texts("typo"),
              "note": "captured at the word's last token, plain render"})
        return

    paras = [p for p in wikitext_paragraphs() if len(tok(p, add_special_tokens=False)["input_ids"]) >= MIN_PASSAGE_TOKENS]
    take = shuffled(paras, "corpus")[: args.n_passages]
    corpus = [cap_text(backend, f"wiki-{k:04d}", t, layers) for k, t in enumerate(take)]
    save(corpus, "corpus-wiki.pt", "Salesforce/wikitext-103-raw-v1/validation",
         {"seq": SEQ, "n_passages": len(corpus), "seed": SEED, "note": "passage starts, every position"})

    sents = []
    for p in shuffled(paras, "sents"):
        for s in re.split(r"(?<=[.!?])\s+", p):
            n = len(tok(s, add_special_tokens=False)["input_ids"])
            if s and s[-1] in ".!?" and SENT_TOKENS[0] <= n <= SENT_TOKENS[1]:
                sents.append(s)
        if len(sents) >= args.n_sents:
            break
    items = [cap_text(backend, f"sent-{k:04d}", s, layers, idx=[len(tok(s, add_special_tokens=False)['input_ids']) - 1])
             for k, s in enumerate(sents[: args.n_sents])]
    save(items, "sents-wiki.pt", "Salesforce/wikitext-103-raw-v1/validation",
         {"tokens": SENT_TOKENS, "n_sents": len(items), "seed": SEED, "note": "standalone sentences, final token"})

    carriers = [
        cap_text(backend, f"{w}::{k}", text, layers, idx=[word_last_idx(tok, text, w)])
        for w in WORDS
        for k, text in enumerate(carrier_texts(w))
    ]
    save(carriers, "carriers.pt", "jlm carrier templates",
         {"words": WORDS, "neutral": NEUTRAL_WORDS, "templates": carrier_texts("typo"),
          "note": "captured at the word's last token, plain render"})


if __name__ == "__main__":
    main()
