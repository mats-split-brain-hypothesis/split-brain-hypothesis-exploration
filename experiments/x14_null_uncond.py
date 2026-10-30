"""x14 C and D: reference states from minimal prompts (null) and from the model's own unconditional text (uncond).

  python experiments/x14_null_uncond.py --device cuda [--families ...]

null: 16 minimal inputs, read the way the family's items are read: plain families, 16 one-word prompts at their
final token; user_modeling, 16 neutral one-line user messages in its chat template; directed_modulation, the copy
instruction around 16 neutral sentences, teacher-forced. uncond: 64 texts the model samples from an empty context
(only <|endoftext|>), their first line, rendered the same way (directed_modulation copies the text's first sentence).
Writes out/captures/{null,uncond}-<family>.pt (constant_mu.FileMean averages them into one μ per layer).
"""

import argparse
import re
import zlib

import torch
from umot.provenance import PINS, Provenance, write_artefact

from jlm import OUT, banks, hfdata
from jlm.capture import MODEL, load_backend
from x8_gen_refs import chat_spec

FAMILIES = ["typo", "association", "basic_readout", "multihop", "multilingual", "user_modeling", "directed_modulation"]
NULL_PLAIN = [".", "The", "It", "And", "A", "This", "So", "Then", "But", "Yes", "Here", "Now", "Well", "OK", "Hi", "There"]
NULL_MESSAGES = ["Hello.", "Thanks.", "Hi there.", "Good morning.", "Can you help me?", "Okay.", "Thank you.", "Hey.",
                 "Please continue.", "Sounds good.", "Got it.", "Sure.", "Alright.", "Great, thanks.", "Hello again.", "Noted."]
NULL_SENTENCES = ["The meeting is on Tuesday.", "The door was left open.", "She read the report twice.",
                  "The train arrived on time.", "We moved the table to the corner.", "The file was saved last night.",
                  "He walked to the station.", "The results are on the second page.", "They painted the fence white.",
                  "The package came this morning.", "The lights were turned off at ten.", "The bus stops at the corner.",
                  "Our team finished the project early.", "The window faces the garden.", "The shop closes at six.",
                  "The letter was signed by both of them."]


def spec_for(template, text: str, rid: str):
    """``text`` rendered and read as the family reads its items (None: nothing to read)."""
    if template.render == "chat_dm":
        sent = re.split(r"(?<=[.?!])\s", text.strip(), maxsplit=1)[0].replace('"', "'")
        return chat_spec(template, f'Now write exactly this sentence: "{sent}"', rid)
    return chat_spec(template, text, rid)


def capture(backend, family: str, texts: list[str], kind: str) -> list:
    from umot import capture as ucap
    from umot.capture import READER_LAYER

    tok = backend.tokenizer
    template = banks.specs(banks.load(family, "val"))[0]
    layers = sorted({*template.layers, READER_LAYER})
    items = []
    for k, t in enumerate(texts):
        rid = f"{kind}-{family}::{k}"
        if template.render in ("chat_context", "chat_dm"):
            s = spec_for(template, t, rid)
            if s is not None and (got := ucap.capture_spec(backend, s, layers)).idx:
                items.append(got)
            continue
        g = tok(t, add_special_tokens=False)["input_ids"][:64]
        if not g:
            continue
        acts = backend.capture(g, layers, [len(g) - 1])
        items.append(ucap.ItemCapture(id=rid, ids=list(g), decoded=[tok.decode([i]) for i in g], positions=[len(g) - 1],
                                      idx=[len(g) - 1], acts={L: acts[L].to(torch.bfloat16) for L in layers}))
    return items


def unconditional(backend, n: int = 64) -> list[str]:
    tok = backend.tokenizer
    start = torch.tensor([[tok.convert_tokens_to_ids("<|endoftext|>")]]).to(backend.model.device)
    texts: list[str] = []
    call = 0
    while len(texts) < n and call < 32:
        torch.manual_seed(zlib.crc32(f"uncond:{call}".encode()))
        outs = backend.model.generate(start, max_new_tokens=48, do_sample=True, temperature=1.0, top_p=0.95,
                                      num_return_sequences=8, pad_token_id=tok.eos_token_id)
        for o in outs:
            t = tok.decode(o[1:], skip_special_tokens=True).strip().split("\n")[0].strip()
            if len(tok(t, add_special_tokens=False)["input_ids"]) >= 3 and t not in texts:
                texts.append(t)
        call += 1
    return texts[:n]


def main() -> None:
    from umot import capture as ucap

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--families", default=",".join(FAMILIES))
    args = ap.parse_args()
    torch.set_grad_enabled(False)
    backend = load_backend(args.device)
    free = unconditional(backend)
    print(f"uncond: {len(free)} texts, e.g. {free[:3]}", flush=True)
    for family in args.families.split(","):
        render = banks.specs(banks.load(family, "val"))[0].render
        null = NULL_MESSAGES if render == "chat_context" else NULL_SENTENCES if render == "chat_dm" else NULL_PLAIN
        for kind, texts in (("null", null), ("uncond", free)):
            dest = OUT / "captures" / f"{kind}-{family}.pt"
            if dest.exists():
                print(f"{dest} exists, skipping")
                continue
            items = capture(backend, family, texts, kind)
            ucap.save(items, dest)
            write_artefact(dest.with_suffix(".provenance.json"),
                           Provenance(model=MODEL, model_revision=PINS[MODEL], dataset=f"jlm/{kind}/{family}",
                                      extra={"render": render, "texts": texts}), {"refs": len(items)})
            print(f"{kind}/{family}: {len(items)} reference reads", flush=True)
            hfdata.share([dest, dest.with_suffix(".provenance.json")])  # to the shared dataset (no-op if unset)


if __name__ == "__main__":
    main()
