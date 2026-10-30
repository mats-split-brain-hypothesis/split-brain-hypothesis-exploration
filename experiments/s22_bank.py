"""Card S22: the families' prompt formats with random, item-free fills (mu-log, card S22; steward's card from S14 insight 17).

S14b needs a late partial mean that holds the bench *instruction's* prior (association's "write a scene" genre, UM's
infobox request), which chat text does not contain. This builds, for each of the 11 families, ``n`` prompts in the
family's own format (its fit bank's header, render and read plan) whose content is a random sentence from the no_robots
chat corpus (no bench text, no LLM): the format and instruction stay, the item content is replaced.

Per family the fill is shaped like the family's prompt: a whole sentence (association), a sentence without its final
punctuation (typo, typo_mt), a sentence prefix cut at a seeded word (completion families; "Fact: " in front for
multihop), the dominant UM instruction after the sentence (user_modeling), "Now write exactly this sentence" with the
sentence as the carrier (directed_modulation, no concept). Fills containing any split's target or intermediate are
dropped (the S2 leak guard). The fills are reference cells only, never scored.

  python experiments/s22_bank.py [--n 24] [--check]           # data/dev/<family>/s22.json, plan check (tokenizer only)
  python experiments/s22_bank.py --capture --device cuda [--families user_modeling,directed_modulation]
                                                              # read-cell captures -> out/captures/<family>-s22.pt (pod)

Finding of the plan check (2026-10-12): 9 of the 11 families render "plain" (the prompt alone, no instruction text);
only user_modeling (chat_context) and directed_modulation (chat_dm) carry a template. So for the plain families these
fills give only "a random English sentence at its final token", and the family's shared genre lives in its items'
own text (S2's hand-written neutral fills keep the genre without the content: the S22 centre's other pool).
"""

import argparse
import copy
import json
import random
import re

from jlm import REPO_ROOT

DEV = REPO_ROOT / "data" / "dev"
FAMILIES = ["typo", "association", "basic_readout", "multihop", "multilingual", "user_modeling", "directed_modulation",
            "typo_mt", "multihop_mt", "basic_readout_mt", "multilingual_mt"]
UM_INSTRUCTION = "Write a hypothetical but realistic Wikipedia biography infobox for me."
BLANK = {"target": "", "target_alts": [], "intermediates": [], "typo": "", "typo_word": "", "attr": "", "concept": ""}


def sentences(seed: int) -> list[str]:
    from jlm import corpus

    out = []
    for _, cat, text in corpus.chat_prompts(n=0, seed=seed):
        if cat == "Coding":
            continue
        for s in re.split(r"(?<=[.!?])\s+", text.replace("\n", " ")):
            w = s.split()
            if 7 <= len(w) <= 22 and s.endswith(".") and s[0].isupper() and not re.search(r"[\"“”:;()\[\]{}<>#*_/\\]|\d", s):
                out.append(s)
    random.Random(seed).shuffle(out)
    return out


def leak_words() -> set[str]:
    from jlm import banks

    words = set()
    for f in FAMILIES:
        for split in banks.SPLITS:
            for it in banks.load(f, split).items:
                for w in [it.get("target"), *it.get("target_alts", []), *it.get("intermediates", []), *banks.targets(it)]:
                    if isinstance(w, str) and len(w) >= 4:
                        words.add(w.casefold())
    return words


def shape(family: str, s: str, rng: random.Random) -> dict:
    """The item fields (beyond the family's template item) for fill sentence ``s``."""
    bare = s.rstrip(".!?")
    words = bare.split()
    cut = " ".join(words[: rng.randint(max(4, len(words) // 2), len(words) - 1)])
    if family == "association":
        return {"prompt": s}
    if family in ("typo", "typo_mt"):
        return {"prompt": bare}
    if family == "multihop":
        return {"prompt": f"Fact: {cut}"}
    if family == "user_modeling":
        return {"messages": [{"role": "system", "content": "You are a helpful assistant."},
                             {"role": "user", "content": f"{s} {UM_INSTRUCTION}"}]}
    if family == "directed_modulation":
        return {"prompt": f"Now write exactly this sentence: \"{s}\"", "assistant": s, "carrier": s,
                "answer": {"accepted": [s]}, "polarity": "none", "units": []}
    return {"prompt": cut}


def build(family: str, n: int, pool: list[str], bad: set[str], seed: int) -> dict:
    fit = json.loads((DEV / family / "fit.json").read_text())
    header = {k: v for k, v in fit.items() if k != "items"}
    template = fit["items"][0]
    rng = random.Random(f"{seed}-{family}")
    items, k = [], 0
    for s in pool:
        if len(items) >= n:
            break
        if any(re.search(rf"(?<!\w){re.escape(w)}(?!\w)", s.casefold()) for w in bad):
            continue
        it = copy.deepcopy(template)
        it.update({k2: v for k2, v in BLANK.items() if k2 in it})
        it.update(shape(family, s, rng))
        it["name"] = f"s22-{family}-{k:02d}"
        it["split"] = "s22"
        it["condition"] = "random-fill"
        if "pair_id" in it:
            it["pair_id"] = it["name"]
        for drop in ("note", "verified", "consistency", "target_in_bench"):
            it.pop(drop, None)
        items.append(it)
        k += 1
    rng.shuffle(pool)  # the next family draws other sentences first
    return header | {"split": "s22", "source": "experiments/s22_bank.py (family formats, random no_robots fills)", "items": items}


def path(family: str):
    return DEV / family / "s22.json"


def load(family: str):
    from wsbench.banks import load_bank

    from jlm.banks import Bank

    header, items = load_bank(path(family))
    return Bank(family, "s22", path(family), header, items)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--n", type=int, default=24)
    ap.add_argument("--seed", type=int, default=22)
    ap.add_argument("--check", action="store_true", help="build the read plans (tokenizer only) and print one per family")
    ap.add_argument("--capture", action="store_true")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--families", default=",".join(FAMILIES), help="capture only these")
    args = ap.parse_args()
    if args.capture:
        from jlm import capture

        for family in args.families.split(","):
            print(capture.run(load(family), args.device), flush=True)
        return
    if args.check:
        from jlm.banks import specs

        for family in FAMILIES:
            sp = specs(load(family))
            print(f"{family}: {len(sp)} specs; first: {str(sp[0])[:300]}")
        return
    pool, bad = sentences(args.seed), leak_words()
    for family in FAMILIES:
        bank = build(family, args.n, pool, bad, args.seed)
        path(family).write_text(json.dumps(bank, ensure_ascii=False, indent=1) + "\n")
        print(f"{path(family)}: {len(bank['items'])} items; e.g. {json.dumps(bank['items'][0].get('prompt') or bank['items'][0].get('messages'), ensure_ascii=False)[:160]}")


if __name__ == "__main__":
    main()
