"""x23 C, step 1: the pinned 27B names each input's context in one word (``ctx``) and what it is about (``topic``).

  python experiments/x23_name_context.py --device cuda [--banks typo/fit,...]

It reads what the lens reads, never a target: a plain item's prompt, user_modeling's user message,
directed_modulation's request with its quoted sentence. Greedy, thinking off, batched with left padding. Writes
out/captures/x23-words.json: {"ctx": {item: word}, "topic": {...}, "raw": {kind: {item: reply}}, "prompts": ...}.
experiments/x23_word_refs.py then writes texts from each word; constant_mu.WordMean reads both.
"""

import argparse
import json
import re

import torch
from umot.provenance import PINS, Provenance, write_artefact

from jlm import banks, hfdata
from jlm.capture import MODEL, load_backend
from jlm.mu.constant_mu import ALL_FAMILIES, X23_WORDS

PROMPTS = {
    "ctx": 'Here is a text:\n\n"""{text}"""\n\nIn one word, name the kind of situation this text is in: what is happening '
           "at its end, not what it is about. Answer with the single word only.",
    "topic": 'Here is a text:\n\n"""{text}"""\n\nIn one word, say what this text is about. Answer with the single word only.',
}
#: x23b: rules and / or worked examples, all off-bench situations (none names a bench family's situation).
RULES = ('Here is a text:\n\n"""{text}"""\n\nIn one word, name the kind of task or situation this text is in at its end: '
         "the activity a reader would recognise (for example a recipe, a riddle, a weather report, a love letter, a sports "
         "commentary, a legal disclaimer). Rules: not a word that appears in the text; not what the text is about; not the "
         "missing or next word; no vague word such as suspense, incomplete, completion, truncation or continuation. "
         "Answer with the single word only.")
SHOTS = [
    ("Roses are red, violets are", "rhyme"),
    ("Preheat the oven to 180 degrees, then", "recipe"),
    ("Knock knock. Who's", "joke"),
    ("Dear Mr. Patel, I am writing to complain about", "complaint"),
    ("def factorial(n):\n    if n == 0:\n        return", "code"),
    ("Tonight: cloudy, with a chance of", "forecast"),
    ("What has keys but can't open locks? A", "riddle"),
    ("Goal! And the crowd in the stadium goes", "commentary"),
]
VARIANTS = {"ctx2": (RULES, []), "ctx3": (PROMPTS["ctx"], SHOTS), "ctx4": (RULES, SHOTS)}
WORD = re.compile(r"[^\W\d_]+(?:[-'][^\W\d_]+)*")
BATCH = 32


def text_of(spec) -> str:
    return spec.messages[-1]["content"] if spec.render == "chat_context" else spec.text


def word_of(reply: str) -> str:
    m = WORD.search(reply)
    return m.group(0).lower() if m else ""


def messages(prompt: str, text: str, shots: list[tuple[str, str]]) -> list[dict]:
    """The naming request, after ``shots`` earlier (text, word) turns answered in the same format."""
    out = []
    for t, w in shots:
        out += [{"role": "user", "content": prompt.format(text=t)}, {"role": "assistant", "content": w}]
    return out + [{"role": "user", "content": prompt.format(text=text)}]


def name_all(backend, texts: dict[str, str], prompt: str, shots: list[tuple[str, str]] = ()) -> dict[str, str]:
    tok = backend.tokenizer
    tok.padding_side = "left"
    ids, out = list(texts), {}
    for b in range(0, len(ids), BATCH):
        chunk = ids[b : b + BATCH]
        msgs = [tok.apply_chat_template(messages(prompt, texts[i], list(shots)), tokenize=False,
                                        add_generation_prompt=True, enable_thinking=False) for i in chunk]
        enc = tok(msgs, return_tensors="pt", padding=True, add_special_tokens=False).to(backend.model.device)
        gen = backend.model.generate(**enc, max_new_tokens=8, do_sample=False, pad_token_id=tok.pad_token_id or tok.eos_token_id)
        for i, g in zip(chunk, gen[:, enc["input_ids"].shape[1]:]):
            out[i] = tok.decode(g, skip_special_tokens=True).strip()
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--banks", default=",".join(f"{f}/{s}" for f in ALL_FAMILIES for s in ("fit", "val")))
    ap.add_argument("--kinds", default="ctx,topic", help="ctx, topic (x23) and / or ctx2, ctx3, ctx4 (x23b)")
    args = ap.parse_args()
    torch.set_grad_enabled(False)
    texts = {s.id: text_of(s) for n in args.banks.split(",") for s in banks.specs(banks.load(*n.split("/")))}
    spec = {**{k: (p, []) for k, p in PROMPTS.items()}, **VARIANTS}
    kinds = args.kinds.split(",")
    backend = load_backend(args.device)
    raw = {k: name_all(backend, texts, *spec[k]) for k in kinds}
    words = {k: {i: word_of(r) for i, r in raw[k].items()} for k in kinds}
    old = json.loads(X23_WORDS.read_text()) if X23_WORDS.exists() else {"raw": {}, "prompts": {}}
    store = {**old, **words, "raw": {**old["raw"], **raw},
             "prompts": {**old["prompts"], **{k: {"prompt": spec[k][0], "shots": spec[k][1]} for k in kinds}}}
    X23_WORDS.write_text(json.dumps(store, indent=1, ensure_ascii=False) + "\n")
    write_artefact(X23_WORDS.with_suffix(".provenance.json"),
                   Provenance(model=MODEL, model_revision=PINS[MODEL], dataset=f"jlm banks {args.banks}",
                              extra={"prompts": store["prompts"], "decoding": "greedy, thinking off, 8 new tokens"}),
                   {k: {"items": len(store[k]), "distinct": len(set(store[k].values()))}
                    for k in store if k not in ("raw", "prompts")})
    for k, w in words.items():
        print(f"{k}: {len(w)} items, {len(set(w.values()))} distinct words; most common "
              f"{sorted(set(w.values()), key=list(w.values()).count, reverse=True)[:12]}", flush=True)
    hfdata.share([X23_WORDS, X23_WORDS.with_suffix(".provenance.json")])  # to the shared dataset (no-op if unset)


if __name__ == "__main__":
    main()
