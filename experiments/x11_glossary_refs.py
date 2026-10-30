"""x11: synthetic reference sets seeded by a GLOSSARY ENTRY of the workspace situation, not by examples.

  python experiments/x11_glossary_refs.py --device cuda [--variants word,desc] [--n 64]

Per family, the pinned 27B writes ``n`` short texts from one glossary entry alone (it never sees
a bank item): ``word`` gives it only the glossary word (the family's frame word), ``desc`` the word
plus a one-line definition of the situation. Each text is captured under the plain render at its
final token (the plain families' read cell) and stored as
``out/captures/glos-<variant>-<family>.pt``. ``constant_mu.GlossaryMean`` averages them into one
constant mu per layer and family (arm ``glos:<variant>@self``; ``glosx:<variant>`` = another
family's entry, the specificity control).

Chat families (2026-10-11): user_modeling and directed_modulation read inside a chat template, so a
text has to fit their render to be read at all. The prompt adds one format line (the same for both
variants and for the control), and each text is rendered and read exactly as the family's items are
(x8_gen_refs.chat_spec on the family's first val spec: UM user message, DM instruction with the quoted
sentence teacher-forced). Their control ``glosx:desc`` is the partner family's entry written in THIS
family's format (``glos-desc-<partner>@<family>.pt``), so it differs from ``glos:desc`` in the entry
only; the plain families' control reuses the partner's plain texts, which is the same thing there.
"""

import argparse
import json
import re
import zlib

import torch
from umot.provenance import PINS, Provenance, write_artefact

from jlm import OUT, banks, hfdata
from jlm.capture import MODEL, load_backend
from x8_gen_refs import chat_spec

BATCH = 8  # texts per call; calls are sampled with a fixed seed each, so the set is reproducible
TEMPERATURE = 0.9
MAX_NEW = 600

#: One glossary entry per plain family: the frame word (data/abstract_concepts.json
#: family_word_v2) and a one-line definition of the workspace situation at the read cell.
GLOSSARY = {
    "typo": ("typo", "a short sentence whose last word is misspelled"),
    "association": ("association", "a short scene description that strongly evokes one concept, "
                                   "place, event or activity without ever naming it, cut off mid-sentence"),
    "basic_readout": ("completion", "a short prompt that stops right before an obvious one-word answer "
                                    "(a fact, a number, or a name)"),
    "multihop": ("inference", "a 'Fact:' sentence that refers to something only indirectly and stops "
                              "right before an answer that requires first working out what it refers to"),
    "multilingual": ("translation", "a short prompt in a language other than English that stops right "
                                    "before a one-word answer"),
    "user_modeling": ("user", "a message in which a person lets slip something about who they are (gender, age, "
                              "job, nationality, religion, ...) without stating it, followed by a request"),
    "directed_modulation": ("instruction", "a request to keep one particular thing in mind while writing out a given "
                                           "sentence exactly"),
}

#: The chat families' render, in one line added to both variants' prompts (and the control's).
FORMAT = {
    "user_modeling": "Each text is a message a person sends to an AI assistant.",
    "directed_modulation": "Each text is a request to an AI assistant that ends with a sentence in double quotes "
                           "for the assistant to write out exactly.",
}
#: The control's entry for each chat family (the plain families' cycle is centres' GLOSSARY_SWAP).
CHAT_SWAP = {"user_modeling": "directed_modulation", "directed_modulation": "user_modeling"}

PROMPTS = {
    "word": "Write {k} varied short texts. Each one is an example of: {word}.\n\n"
            "Write each text on its own line, numbered 1. to {k}., with nothing else.",
    "desc": "Write {k} varied short texts. Each one is an example of: {word} — {desc}.\n\n"
            "Write each text on its own line, numbered 1. to {k}., with nothing else.",
    # x14 B: no entry at all, the control for "the situation" vs "model-written short text"
    "none": "Write {k} varied short texts.\n\n"
            "Write each text on its own line, numbered 1. to {k}., with nothing else.",
}
#: x13: entries the model wrote from the bench's own family descriptions (experiments/x13_blind_glossary.py), used
#: with --blind as the variants bword / bdesc (prompt as word / desc; seeds salted by the variant name).
BLIND = OUT / "captures" / "glossary-blind.json"


def parse(gen: str) -> list[str]:
    out = []
    for line in gen.splitlines():
        m = re.match(r"^\s*\d+[.)]\s*(.+)$", line)
        if m and m.group(1).strip():
            out.append(m.group(1).strip())
    return out


def generate(backend, variant: str, family: str, n: int, fmt: str = "", glossary: dict | None = None) -> list[str]:
    """``n`` texts from ``family``'s entry (``glossary``, default GLOSSARY); ``fmt`` names the chat family whose
    format line is added. Variants bword / bdesc use the word / desc prompt (x13)."""
    tok = backend.tokenizer
    word, desc = (glossary or GLOSSARY)[family]
    msg = PROMPTS[variant.removeprefix("b") if variant in ("bword", "bdesc") else variant].format(k=BATCH, word=word, desc=desc)
    if fmt:
        msg = msg.replace("\n\nWrite each text", f" {FORMAT[fmt]}\n\nWrite each text")
    ids = tok.apply_chat_template([{"role": "user", "content": msg}], tokenize=True,
                                  add_generation_prompt=True, enable_thinking=False)
    ids = torch.tensor([list(ids["input_ids"] if hasattr(ids, "keys") else ids)]).to(backend.model.device)
    texts: list[str] = []
    call = 0
    while len(texts) < n and call < 4 * n // BATCH:
        torch.manual_seed(zlib.crc32(f"{variant}:{family}:{call}".encode() if not fmt or fmt == family
                                     else f"{variant}:{family}@{fmt}:{call}".encode()))
        out = backend.model.generate(ids, max_new_tokens=MAX_NEW, do_sample=True, temperature=TEMPERATURE,
                                     top_p=0.95, pad_token_id=tok.eos_token_id)[0][ids.shape[1]:]
        texts += [t for t in parse(tok.decode(out, skip_special_tokens=True)) if t not in texts]
        call += 1
    return texts[:n]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--variants", default="word,desc")
    ap.add_argument("--families", default=",".join(GLOSSARY))
    ap.add_argument("--n", type=int, default=64)
    ap.add_argument("--blind", action="store_true", help="x13: the model-written entries in glossary-blind.json, "
                                                           "as variants bword / bdesc")
    args = ap.parse_args()
    glossary = GLOSSARY
    if args.blind:
        glossary = {f: tuple(e) for f, e in json.loads(BLIND.read_text())["entries"].items()}
        if args.variants == "word,desc":
            args.variants = "bword,bdesc"
    torch.set_grad_enabled(False)
    from umot import capture as ucap
    from umot.capture import READER_LAYER

    backend = load_backend(args.device)
    tok = backend.tokenizer
    jobs = [(v, f, f) for v in args.variants.split(",") for f in args.families.split(",")]
    jobs += [("desc", CHAT_SWAP[f], f) for f in args.families.split(",") if f in CHAT_SWAP
             and "desc" in args.variants.split(",")]
    for variant, entry, family in jobs:  # texts from ``entry``'s glossary entry, read as ``family`` reads
        name = entry if entry == family else f"{entry}@{family}"
        dest = OUT / "captures" / f"glos-{variant}-{name}.pt"
        if dest.exists():
            print(f"{dest} exists, skipping")
            continue
        template = banks.specs(banks.load(family, "val"))[0]
        layers = sorted({*template.layers, READER_LAYER})
        chat = family in FORMAT
        texts = generate(backend, variant, entry, args.n, fmt=family if chat else "", glossary=glossary)
        items = []
        for k, t in enumerate(texts):
            rid = f"glos-{variant}-{name}::{k}"
            if chat:
                s = chat_spec(template, t, rid)
                if s is not None:
                    got = ucap.capture_spec(backend, s, layers)
                    if got.idx:
                        items.append(got)
                continue
            g = tok(t, add_special_tokens=False)["input_ids"][:64]
            if len(g) < 3:
                continue
            acts = backend.capture(g, layers, [len(g) - 1])
            items.append(ucap.ItemCapture(id=rid, ids=list(g),
                                          decoded=[tok.decode([i]) for i in g], positions=[len(g) - 1],
                                          idx=[len(g) - 1], acts={L: acts[L].to(torch.bfloat16) for L in layers}))
        ucap.save(items, dest)
        write_artefact(
            dest.with_suffix(".provenance.json"),
            Provenance(model=MODEL, model_revision=PINS[MODEL], dataset=f"jlm/glossary/{variant}/{name}",
                       extra={"entry": ("", "") if variant == "none" else glossary[entry], "read_as": family,
                              "format": FORMAT.get(family, ""), "blind": args.blind,
                              "prompt": PROMPTS[variant.removeprefix("b") if variant in ("bword", "bdesc") else variant], "batch": BATCH, "temperature": TEMPERATURE, "texts": texts}),
            {"refs": len(items)},
        )
        print(f"{variant}/{name}: {len(items)} refs; e.g. {texts[:2]}", flush=True)
        hfdata.share([dest, dest.with_suffix(".provenance.json")])  # to the shared dataset (no-op if unset)

if __name__ == "__main__":
    main()
