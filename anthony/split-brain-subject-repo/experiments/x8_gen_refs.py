"""x8 stage 1: the model writes its own reference set — 8 same-kind prompts per val item.

  python experiments/x8_gen_refs.py --family typo --split val --device cuda [--n 8]

For each item the pinned 27B sees ONLY the item's rendered prompt (what the lens reads; never a
target or the family name) and writes N short texts "of exactly the same kind". Generations that
reuse the prompt's final word (the read token's word) are dropped, the rest are truncated to N,
captured under the plain render at their final token (the plain families' read cell), and stored
as ``out/captures/gen-<family>-<split>.pt`` with ids ``<item>::g<k>``. Stage 2 scores
``mu(item) = mean of the item's generated states`` (jlm.mu.constant_mu.GenMean, arm ``gen@self``).

Chat families (2026-10-11): the example is what the user wrote (user_modeling: the user message;
directed_modulation: the instruction with its quoted sentence), and each generated text is put back
into a copy of the item's own read spec, so it is rendered and read exactly as the item is (UM: the
user message replaced, read from the last sentence start; DM: the instruction replaced and its quoted
sentence teacher-forced as the reply, every token read). A DM generation with no quoted sentence is
dropped.
"""

import argparse
import dataclasses
import re

import torch
from umot.provenance import PINS, Provenance, write_artefact

from jlm import OUT, banks, hfdata
from jlm.capture import MODEL, load_backend

MAX_NEW = 400
GEN_PROMPT = """Here is a short text:

{text}

Write {n} more short texts of exactly the same kind: same task, same shape, same style, the same
way of ending. Vary the content; do not reuse the distinctive words of the example. Write each
text on its own line, numbered 1. to {n}., with nothing else."""


STOPWORDS = {"the", "a", "an", "of", "to", "in", "is", "was", "for", "with", "and", "or", "as", "at", "by", "on"}


def last_word(text: str) -> str:
    """The prompt's final content word, banned from generations so the reference set cannot
    smuggle in the item's own latent carrier; function-word endings ban nothing."""
    words = re.findall(r"[\w']+", text)
    if not words:
        return ""
    w = words[-1].casefold()
    return "" if w in STOPWORDS or len(w) < 3 else w


def parse(gen: str, n: int, ban: str) -> list[str]:
    out = []
    for line in gen.splitlines():
        t = re.sub(r"^\s*\d+[.)]\s*", "", line).strip()
        if not t or re.match(r"^\s*\d+[.)]?\s*$", line) or t.startswith(("Here", "Sure")):
            continue
        if ban and ban in t.casefold():
            continue
        out.append(t)
    return out[:n]


QUOTED = re.compile(r'["\u201c]([^"\u201c\u201d]{3,})["\u201d]')


def example_text(spec) -> str:
    """What the generator sees: the plain prompt, the UM user message or the DM instruction."""
    if spec.render == "chat_context":
        return next(m["content"] for m in reversed(spec.messages) if m["role"] == "user")
    return spec.text or ""


def chat_spec(spec, text: str, rid: str):
    """The item's read spec with ``text`` in place of what the user wrote (None: a DM text with no quoted
    sentence to teacher-force)."""
    if spec.render == "chat_context":
        msgs = [dict(m, content=text) if m["role"] == "user" else m for m in spec.messages]
        return dataclasses.replace(spec, id=rid, messages=msgs)
    if spec.render == "chat_dm":
        quoted = QUOTED.findall(text)
        if not quoted:
            return None
        s = quoted[-1].strip()
        return dataclasses.replace(spec, id=rid, text=text, assistant=s, positions={"kind": "suffix_text", "text": s})
    raise ValueError(f"no chat rendering for {spec.render!r}")


def gen_bank(backend, bank, n: int) -> None:
    """Write ``n`` same-kind references per item of ``bank`` and capture them at their final token."""
    from umot import capture as ucap
    from umot.capture import READER_LAYER

    dest = OUT / "captures" / f"gen-{bank.family}-{bank.split}.pt"
    if dest.exists():
        print(f"{dest} exists, skipping")
        return
    tok = backend.tokenizer
    layers = sorted({*banks.specs(bank)[0].layers, READER_LAYER})
    items_out, short, texts_out = [], 0, {}
    plan = {s.id: s for s in banks.specs(bank)}
    for it in bank.items:
        spec = plan[it["id"]]
        chat = spec.render in ("chat_context", "chat_dm")
        text = example_text(spec) if chat else (it.get("prompt") or "")
        msg = GEN_PROMPT.format(text=text, n=n + 4)  # ask for spares; filter then cap
        ids = tok.apply_chat_template([{"role": "user", "content": msg}], tokenize=True,
                                      add_generation_prompt=True, enable_thinking=False)
        ids = list(ids["input_ids"] if hasattr(ids, "keys") else ids)
        gen = backend.model.generate(torch.tensor([ids]).to(backend.model.device),
                                     max_new_tokens=MAX_NEW, do_sample=False, pad_token_id=tok.eos_token_id)[0][len(ids):]
        texts = parse(tok.decode(gen, skip_special_tokens=True), n, last_word(text))
        if len(texts) < 4:
            short += 1
        texts_out[it["id"]] = texts
        for k, t in enumerate(texts):
            if chat:
                s = chat_spec(spec, t, f"{it['id']}::g{k}")
                if s is not None:
                    got = ucap.capture_spec(backend, s, layers)
                    if got.idx:
                        items_out.append(got)
                continue
            g_ids = tok(t, add_special_tokens=False)["input_ids"][:64]
            if len(g_ids) < 3:
                continue
            acts = backend.capture(g_ids, layers, [len(g_ids) - 1])
            items_out.append(ucap.ItemCapture(
                id=f"{it['id']}::g{k}", ids=list(g_ids),
                decoded=[tok.decode([i]) for i in g_ids],
                positions=[len(g_ids) - 1], idx=[len(g_ids) - 1],
                acts={L: acts[L].to(torch.bfloat16) for L in layers},
            ))
    ucap.save(items_out, dest)
    write_artefact(
        dest.with_suffix(".provenance.json"),
        Provenance(model=MODEL, model_revision=PINS[MODEL], dataset=f"jlm/{bank.name}",
                   extra={"n_asked": n, "generator": "self (greedy, thinking off)",
                          "filter": "drop generations containing the prompt's last content word",
                          "render": banks.specs(bank)[0].render, "texts": texts_out}),
        {"items": len({i.id.split('::')[0] for i in items_out}), "refs": len(items_out), "short_items": short},
    )
    print(f"{dest}: {len(items_out)} reference states, {short} short items", flush=True)
    hfdata.share([dest, dest.with_suffix(".provenance.json")])  # to the shared dataset (no-op if unset)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--family")
    ap.add_argument("--split", default="val")
    ap.add_argument("--banks", default="", help="family/split,... in one model load")
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()
    torch.set_grad_enabled(False)
    todo = [tuple(b.split("/")) for b in args.banks.split(",")] if args.banks else [(args.family, args.split)]
    backend = load_backend(args.device)
    for family, split in todo:
        gen_bank(backend, banks.load(family, split), args.n)


if __name__ == "__main__":
    main()
