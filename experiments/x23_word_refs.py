"""x23 C, step 2: texts written from each named word, read in the family's render.

  python experiments/x23_word_refs.py --device cuda [--kinds ctx,topic]

Per kind (``ctx``, ``topic``) and format (``plain``: the five plain families share one render; ``user_modeling``;
``directed_modulation``): one set per distinct word named for that format's items (x23-words.json). x11's word prompt,
with the chat family's format line as in x12; 32 texts per word (16 if a kind names more than 300 distinct words,
the rule registered with x23). Sampling is batched across words: 8 words x 4 calls of 8 texts per batch, one seed per
batch (crc32 of "x23", the kind, the format and the batch's words). Writes out/captures/x23-<kind>-<format>.pt (ids
``<word>::<k>``, read like x11's sets) and its provenance with every text.
"""

import argparse
import json
import zlib

import torch
from umot.provenance import PINS, Provenance, write_artefact
from x8_gen_refs import chat_spec
from x11_glossary_refs import BATCH, FORMAT, MAX_NEW, PROMPTS, TEMPERATURE, parse

from jlm import OUT, banks, hfdata
from jlm.capture import MODEL, load_backend
from jlm.mu.constant_mu import X23_WORDS

PLAIN = ("typo", "association", "basic_readout", "multihop", "multilingual")
WORDS_PER_BATCH = 8


def words_by_format(kind: str) -> dict[str, list[str]]:
    named = json.loads(X23_WORDS.read_text())[kind]
    out: dict[str, set] = {"plain": set(), "user_modeling": set(), "directed_modulation": set()}
    for f in (*PLAIN, "user_modeling", "directed_modulation"):
        ids = {it["id"] for s in ("fit", "val") for it in banks.load(f, s).items}
        out["plain" if f in PLAIN else f] |= {w for i, w in named.items() if i in ids and w}
    return {k: sorted(v) for k, v in out.items()}


def write(backend, words: list[str], fmt: str, kind: str, n: int) -> dict[str, list[str]]:
    tok = backend.tokenizer
    tok.padding_side = "left"
    calls = -(-n // BATCH)
    texts: dict[str, list[str]] = {}
    for b in range(0, len(words), WORDS_PER_BATCH):
        chunk = words[b : b + WORDS_PER_BATCH]
        msgs = []
        for w in chunk:
            msg = PROMPTS["word"].format(k=BATCH, word=w, desc="")
            if fmt != "plain":
                msg = msg.replace("\n\nWrite each text", f" {FORMAT[fmt]}\n\nWrite each text")
            m = tok.apply_chat_template([{"role": "user", "content": msg}], tokenize=False, add_generation_prompt=True,
                                        enable_thinking=False)
            msgs += [m] * calls
        enc = tok(msgs, return_tensors="pt", padding=True, add_special_tokens=False).to(backend.model.device)
        torch.manual_seed(zlib.crc32(f"x23:{kind}:{fmt}:{','.join(chunk)}".encode()))
        gen = backend.model.generate(**enc, max_new_tokens=MAX_NEW, do_sample=True, temperature=TEMPERATURE, top_p=0.95,
                                     pad_token_id=tok.pad_token_id or tok.eos_token_id)[:, enc["input_ids"].shape[1]:]
        for j, w in enumerate(chunk):
            got: list[str] = []
            for g in gen[j * calls : (j + 1) * calls]:
                got += [t for t in parse(tok.decode(g, skip_special_tokens=True)) if t not in got]
            texts[w] = got[:n]
        print(f"  {kind}/{fmt}: {b + len(chunk)}/{len(words)} words", flush=True)
    return texts


def capture(backend, texts: dict[str, list[str]], fmt: str) -> list:
    from umot.capture import READER_LAYER

    from umot import capture as ucap

    tok = backend.tokenizer
    template = banks.specs(banks.load("typo" if fmt == "plain" else fmt, "val"))[0]
    layers = sorted({*template.layers, READER_LAYER})
    items = []
    for w, ts in texts.items():
        for k, t in enumerate(ts):
            rid = f"{w}::{k}"
            if fmt != "plain":
                s = chat_spec(template, t, rid)
                if s is not None and (got := ucap.capture_spec(backend, s, layers)).idx:
                    items.append(got)
                continue
            g = tok(t, add_special_tokens=False)["input_ids"][:64]
            if len(g) < 3:
                continue
            acts = backend.capture(g, layers, [len(g) - 1])
            items.append(ucap.ItemCapture(id=rid, ids=list(g), decoded=[tok.decode([i]) for i in g], positions=[len(g) - 1],
                                          idx=[len(g) - 1], acts={L: acts[L].to(torch.bfloat16) for L in layers}))
    return items


def reusable(fmt: str, n: int, words: set[str]) -> tuple[list, dict[str, list[str]]]:
    """Captured texts of ``words`` already written for this format by an earlier kind with the same ``n`` (x23b reuses
    x23's: same prompt and generator, another seed)."""
    from umot import capture as ucap

    items, texts = [], {}
    for prov in sorted((OUT / "captures").glob(f"x23-*-{fmt}.provenance.json")):
        extra = json.loads(prov.read_text())["provenance"]["extra"]
        have = {w: t for w, t in extra.get("texts", {}).items() if w in words and w not in texts}
        if extra.get("n") != n or not have:
            continue
        items += [it for it in ucap.load(prov.with_name(prov.name.replace(".provenance.json", ".pt")))
                  if it.id.rsplit("::", 1)[0] in have]
        texts |= have
    return items, texts


def main() -> None:
    from umot import capture as ucap

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--kinds", default="ctx,topic")
    args = ap.parse_args()
    torch.set_grad_enabled(False)
    backend = load_backend(args.device)
    for kind in args.kinds.split(","):
        by_fmt = words_by_format(kind)
        distinct = len({w for ws in by_fmt.values() for w in ws})
        n = 32 if distinct <= 300 else 16
        print(f"{kind}: {distinct} distinct words ({', '.join(f'{f} {len(w)}' for f, w in by_fmt.items())}); {n} texts each",
              flush=True)
        for fmt, words in by_fmt.items():
            dest = OUT / "captures" / f"x23-{kind}-{fmt}.pt"
            if dest.exists():
                print(f"{dest} exists, skipping")
                continue
            old_items, old_texts = reusable(fmt, n, set(words))
            new = [w for w in words if w not in old_texts]
            texts = write(backend, new, fmt, kind, n) if new else {}
            items = [it for it in old_items if it.id.rsplit("::", 1)[0] in set(words)] + capture(backend, texts, fmt)
            ucap.save(items, dest)
            write_artefact(dest.with_suffix(".provenance.json"),
                           Provenance(model=MODEL, model_revision=PINS[MODEL], dataset=f"jlm/x23/{kind}/{fmt}",
                                      extra={"prompt": PROMPTS["word"], "format": FORMAT.get(fmt, ""), "n": n,
                                             "temperature": TEMPERATURE, "words": words,
                                             "reused": sorted(set(words) - set(new)), "texts": {**old_texts, **texts}}),
                           {"refs": len(items), "words": len(words), "new_words": len(new)})
            print(f"{kind}/{fmt}: {len(words)} words ({len(new)} new), {len(items)} refs", flush=True)
            hfdata.share([dest, dest.with_suffix(".provenance.json")])  # to the shared dataset (no-op if unset)


if __name__ == "__main__":
    main()
