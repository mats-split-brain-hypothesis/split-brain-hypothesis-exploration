"""English glosses for every non-English token of the Qwen3.6-27B vocabulary: a one-time lookup table for the dashboard.

  python experiments/build_gloss.py --dry-run         # count tokens and batches, no calls
  python experiments/build_gloss.py --limit 2         # two batches (smoke)
  python experiments/build_gloss.py                   # everything; resumes from the existing table

One pass of Haiku 5.5 (the development judge model, via OpenRouter; key from umot/.env) over every vocabulary token
whose decoded text holds a non-ASCII letter, 300 tokens a call (under $1 for the whole vocabulary). Tokens that end
inside a multi-byte character (no text of their own) are skipped. Writes ``data/gloss/en.json``:
``{"meta": {...}, "gloss": {decoded token text (stripped): English}}``. The dashboard only reads this file; it never
calls an API. The glosses are a reading aid from an unpinned model and are never used in scoring.
"""

import argparse
import json
import os
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

from transformers import AutoTokenizer
from umot.provenance import PINS

from jlm import REPO_ROOT
from jlm.judge import DEV_JUDGE
from jlm.lens import MODEL

OUT = REPO_ROOT / "data" / "gloss" / "en.json"
BATCH = 300
PROMPT = """Each line below is one token from a multilingual LLM tokenizer, written as `index<TAB>token`. Tokens are often
pieces of words. For each, give the closest English translation in at most four words. For a word fragment, give the
likely whole word it starts or ends, marked with "…" (for example "распрост" -> "spread…"). For a name, transliterate it.
For a grammatical particle, say what it does in a word or two (for example "的" -> "(possessive)"). If you cannot tell,
answer "?".
Reply with only a JSON object mapping each index (as a string) to its gloss.

"""


def byte_decoder() -> dict[str, int]:
    bs = list(range(ord("!"), ord("~") + 1)) + list(range(ord("¡"), ord("¬") + 1)) + list(range(ord("®"), ord("ÿ") + 1))
    cs, n = bs[:], 0
    for b in range(256):
        if b not in bs:
            bs.append(b)
            cs.append(256 + n)
            n += 1
    return {chr(c): b for b, c in zip(bs, cs, strict=True)}


def needs(text: str) -> bool:
    return any(ord(ch) > 127 and unicodedata.category(ch).startswith("L") for ch in text)


def vocab_texts() -> list[str]:
    tok = AutoTokenizer.from_pretrained(MODEL, revision=PINS[MODEL], local_files_only=True)
    dec = byte_decoder()
    out = set()
    for t in tok.get_vocab():
        try:
            text = bytes(dec[ch] for ch in t).decode("utf-8").strip()
        except (KeyError, UnicodeDecodeError):  # special tokens; pieces of a multi-byte character
            continue
        if needs(text):
            out.add(text)
    return sorted(out)


def key() -> str:
    if os.environ.get("OPENROUTER_API_KEY"):
        return os.environ["OPENROUTER_API_KEY"]
    for line in (REPO_ROOT / "umot" / ".env").read_text().splitlines():
        k, sep, v = line.strip().partition("=")
        if sep and k.strip() == "OPENROUTER_API_KEY":
            return v.strip().strip("'\"")
    sys.exit("no OPENROUTER_API_KEY (umot/.env)")


def ask(client, texts: list[str]) -> tuple[dict[str, str], float]:
    body = "\n".join(f"{i}\t{t}" for i, t in enumerate(texts))
    cost = 0.0
    for attempt in range(3):  # the odd reply comes back cut short: ask again
        r = client.chat.completions.create(model=DEV_JUDGE, temperature=0, max_tokens=14 * len(texts) + 300,
                                           messages=[{"role": "user", "content": PROMPT + body}],
                                           extra_body={"reasoning": {"enabled": False}})
        cost += float((r.usage.model_extra or {}).get("cost") or 0)
        raw = r.choices[0].message.content or ""
        try:
            got = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
            break
        except ValueError:
            if attempt == 2:
                return {}, cost
    return {texts[int(i)]: str(g).strip() for i, g in got.items() if str(i).isdigit() and int(i) < len(texts)}, cost


def save(table: dict, n_vocab: int, spent: float) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    meta = {"model": DEV_JUDGE, "tokenizer": f"{MODEL}@{PINS[MODEL]}", "built": str(date.today()),
            "non_english_tokens": n_vocab, "glossed": len(table), "spend_usd": round(spent, 4),
            "note": "reading aid from an unpinned model; never used in scoring"}
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps({"meta": meta, "gloss": dict(sorted(table.items()))}, ensure_ascii=False, indent=0))
    tmp.replace(OUT)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, help="at most this many batches")
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args()

    texts = vocab_texts()
    old = json.loads(OUT.read_text()) if OUT.exists() else {"meta": {}, "gloss": {}}
    table, spent = old["gloss"], float(old["meta"].get("spend_usd", 0))
    todo = [t for t in texts if t not in table]
    batches = [todo[k: k + BATCH] for k in range(0, len(todo), BATCH)][: args.limit]
    print(f"{len(texts)} non-English tokens, {len(table)} glossed, {len(todo)} to go: {len(batches)} batches")
    if args.dry_run or not batches:
        return

    from openai import OpenAI

    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key(), timeout=120)
    t0, run_cost, done = time.time(), 0.0, 0
    with ThreadPoolExecutor(args.workers) as pool:
        for fut in as_completed([pool.submit(ask, client, b) for b in batches]):
            got, cost = fut.result()
            table.update(got)
            run_cost += cost
            done += 1
            if done % 20 == 0 or done == len(batches):
                save(table, len(texts), spent + run_cost)
                print(f"  {done}/{len(batches)} batches, {len(table)} glossed, ${run_cost:.3f} this run, "
                      f"{time.time() - t0:.0f} s", flush=True)
    save(table, len(texts), spent + run_cost)
    print(f"done: {len(table)}/{len(texts)} glossed, ${run_cost:.3f} this run (${spent + run_cost:.3f} in all)")


if __name__ == "__main__":
    main()
