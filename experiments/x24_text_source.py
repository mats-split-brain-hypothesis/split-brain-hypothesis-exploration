"""x24: why does model-written text work as mu? Reference sets that separate source, length, style and read position.

x14 B's model-written short texts (glos:none) give +0.176 pooled plain; standalone wikitext sentences (fam@sents) give
+0.015. Four sets per plain family, read under the plain render, each a constant mu through ``glos:<variant>@self``:

- ``wshort``: wikitext sentences of 10..18 tokens (length-matched to glos:none), at the final token.
- ``mwiki``: model-written in the style of an encyclopedia article (x11's generator), at the final token.
- ``mcut`` / ``wcut``: glos:none's texts / wshort's sentences without their last word, at the token before it.

  python experiments/x24_text_source.py --device cuda
"""

import argparse
import functools
import json
import re

import torch
from capture_mu_refs import cap_text, shuffled, wikitext_paragraphs
from umot.provenance import PINS, Provenance, write_artefact
from x11_glossary_refs import PROMPTS, generate

from jlm import OUT, banks, hfdata
from jlm.capture import MODEL, load_backend

PLAIN = ["typo", "association", "basic_readout", "multihop", "multilingual"]
N = 64
SHORT = (10, 18)  # tokens; glos:none's 10-90 % range is 11..17
PROMPTS["mwiki"] = ("Write {k} varied short sentences in the style of an encyclopedia article.\n\n"
                    "Write each text on its own line, numbered 1. to {k}., with nothing else.")


@functools.cache
def paragraphs() -> list[str]:
    return wikitext_paragraphs()


def short_sents(tok, family: str) -> list[str]:
    """``N`` wikitext sentences of SHORT tokens, ending in . ! or ?, from a per-family seeded shuffle."""
    out = []
    for p in shuffled(paragraphs(), f"wshort:{family}"):
        for s in re.split(r"(?<=[.!?])\s+", p):
            n = len(tok(s, add_special_tokens=False)["input_ids"])
            if s and s[-1] in ".!?" and SHORT[0] <= n <= SHORT[1] and s not in out:
                out.append(s)
        if len(out) >= N:
            return out[:N]
    return out


def cut(text: str) -> str:
    """The text without its last word (and the punctuation after it)."""
    return text.rstrip().rsplit(" ", 1)[0].rstrip(" ,;:-")


def capture(backend, variant: str, family: str, texts: list[str], layers: list[int]) -> list:
    tok = backend.tokenizer
    items = []
    for k, t in enumerate(texts):
        n = len(tok(t, add_special_tokens=False)["input_ids"][:64])
        if n >= 3:
            items.append(cap_text(backend, f"glos-{variant}-{family}::{k}", t, layers, idx=[n - 1]))
    return items


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--families", default=",".join(PLAIN))
    args = ap.parse_args()
    torch.set_grad_enabled(False)
    from umot.capture import READER_LAYER

    from umot import capture as ucap

    backend = load_backend(args.device)
    tok = backend.tokenizer
    for family in args.families.split(","):
        layers = sorted({*banks.specs(banks.load(family, "val"))[0].layers, READER_LAYER})
        none = json.loads((OUT / "captures" / f"glos-none-{family}.provenance.json").read_text())["provenance"]["extra"]["texts"]
        wshort = short_sents(tok, family)
        sets = {"wshort": wshort, "wcut": [cut(s) for s in wshort], "mcut": [cut(t) for t in none],
                "mwiki": generate(backend, "mwiki", family, N)}
        for variant, texts in sets.items():
            dest = OUT / "captures" / f"glos-{variant}-{family}.pt"
            if dest.exists():
                print(f"{dest} exists, skipping")
                continue
            items = capture(backend, variant, family, texts, layers)
            ucap.save(items, dest)
            lens = sorted(len(it.ids) for it in items)
            write_artefact(dest.with_suffix(".provenance.json"),
                           Provenance(model=MODEL, model_revision=PINS[MODEL], dataset=f"jlm/x24/{variant}/{family}",
                                      extra={"variant": variant, "read_as": family, "short_tokens": SHORT,
                                             "prompt": PROMPTS["mwiki"] if variant == "mwiki" else "", "texts": texts}),
                           {"refs": len(items), "tokens_median": lens[len(lens) // 2]})
            print(f"{variant}/{family}: {len(items)} refs, median {lens[len(lens) // 2]} tokens; e.g. {texts[:2]}", flush=True)
            hfdata.share([dest, dest.with_suffix(".provenance.json")])  # to the shared dataset (no-op if unset)


if __name__ == "__main__":
    main()
