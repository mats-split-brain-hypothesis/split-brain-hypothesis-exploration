"""Other forms of each target word, for the "strict + forms" scorer: a one-time, reviewed lookup table.

  python experiments/build_forms.py --dry-run        # count targets and batches, no calls
  python experiments/build_forms.py                  # every single-token family; resumes from the existing tables
  python experiments/build_forms.py --family typo
  python experiments/build_forms.py --clean          # apply the review rules below to the tables, list what changed
  python experiments/build_forms.py --numbers        # add the digit <-> number-word forms to the tables in place

One pass of Haiku 5.5 (the development judge model, via OpenRouter; key from umot/.env) over each family's distinct
target sets in its fit, val and bench banks, with one item's prompt as the sense. Rule: inflections in every family
(swimming -> swim, swims, swam, swum; cow -> cows; narrow -> narrower, narrowest), and in association also words
derived from the target that name the same thing (swimming -> swimmer; mining -> miner, mine). Proper nouns get none.
Writes ``data/forms/<family>.json``: ``{"meta": {...}, "forms": {target key: [forms]}}``, the key being the item's
normalised accepted forms joined by "|" (``jlm.forms.key``). The table is reviewed by hand after a build and may be
edited; a rebuild keeps every key it already holds. Scoring only reads it (``jlm.forms``); it never calls an API.

The draft is not used as it comes back. ``--clean`` applies the review (2026-10-11): outside association a form stays
only when it is the target (or its stem) plus a regular inflectional ending (an -er or -est comparative only when its
pair is there too: ``narrower`` with ``narrowest``, never an agent noun like ``boxer``) or is in ``IRREGULAR``; number
targets get no forms beyond their number rule (below); and the ``REJECT`` lists drop other senses, translations and
associations by hand.

Numbers (2026-10-12): a number target also accepts its other spelling, digit <-> English word (``9`` <-> ``nine``,
0-20 and the tens to 90; ``NUMBER_WORDS``), deterministic, no model. A key with both a digit and a word takes the
digit's word only, so the bench's ``9|ten`` gains ``nine``, not ``10``. ``--numbers`` adds these to the existing
tables in place (keeping every hand edit); ``--clean`` keeps them.
"""

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

from build_gloss import key

from jlm import banks, forms, score
from jlm.judge import DEV_JUDGE, MULTI_TOKEN

FAMILIES = ("basic_readout", "association", "multihop", "multilingual", "typo", "directed_modulation", "user_modeling")
BATCH = 40
WORD = re.compile(r"[a-z]+")
INFLECT = """Include the inflections of the word: singular and plural of a noun (man -> men; cow -> cows), the forms of a verb
(swim -> swims, swam, swum, swimming), comparative and superlative of an adjective (narrow -> narrower, narrowest).
If the word is itself an inflected form, include its base form and the base's other inflections
(swimming -> swim, swims, swam, swum)."""
RELATED = """Also include words derived from it that name the same thing, activity or idea, with their inflections
(swimming -> swimmer, swimmers; mining -> miner, miners, mine; promotion -> promote, promoted, promotes, promoting).
Do not include words that are only associated with it (swimming -> pool is wrong)."""
PROMPT = """Each line below is `index<TAB>word<TAB>context`. The word is the accepted answer to a test item, and the context
is the item's prompt, which shows the sense. List the other forms of the word that should also count as the answer.
{rule}
Give nothing for a proper noun (a country, city, person, month, weekday or language): []. Leave out the word itself,
other senses of the word, spelling variants, possessives, and anything with a space, hyphen or apostrophe.
Reply with only a JSON object mapping each index (as a string) to a list of lowercase words.

"""


SUFFIXES = ("s", "es", "ed", "d", "ing", "n")
COMPARATIVE = ("er", "r", "est", "st")
IRREGULAR = {
    "men", "women", "children", "fishermen", "postmen", "policemen", "swam", "swum", "sprang", "sprung", "ran", "grew",
    "knew", "wrote", "written", "brought", "began", "begun", "hid", "hide", "hides", "mistook", "least", "less",
    "farther", "farthest", "further", "furthest", "halves", "octopi", "oases", "isthmi", "rhombi", "nebulae", "femora",
    "patellae", "vortices", "trapezia", "referenda", "mantids", "learnt", "worry", "worries", "dove", "spun", "wove",
    "woven", "sewn", "mice", "geese", "teeth", "feet", "lay", "lain",
}
NUMBERS = {"zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
           "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty", "thirty", "forty",
           "fifty", "sixty", "seventy", "eighty", "ninety", "hundred", "thousand", "million", "billion"}
NUMBER_WORDS = {n: w for n, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen "
                                         "fourteen fifteen sixteen seventeen eighteen nineteen twenty".split())}
NUMBER_WORDS |= {10 * k: w for k, w in zip(range(3, 10), "thirty forty fifty sixty seventy eighty ninety".split(), strict=True)}
NUMBER_DIGITS = {w: str(n) for n, w in NUMBER_WORDS.items()}


def number_forms(bases: list[str]) -> list[str]:
    """A number target's other spelling: the digit's English word, or (with no digit in the key) the word's digit."""
    digits = [b for b in bases if b.isdigit()]
    out = [NUMBER_WORDS[int(d)] for d in digits if int(d) in NUMBER_WORDS] if digits else \
          [NUMBER_DIGITS[b] for b in bases if b in NUMBER_DIGITS]
    return sorted(set(out) - set(bases))


REJECT_ANY = {"rights", "lefts", "olds", "lasts", "downs", "souths", "easts", "firsts", "upper", "uppest", "commons",
              "blacks", "browns", "reds", "greens", "blues", "whites", "pinks", "purples", "yellows"}
FENCE = ["fence", "fenced", "fences"]
REJECT = {  # family -> target key -> forms dropped by hand (other sense, translation, association)
    "association": {
        "moses": ["mosaic"], "tango": ["dance", "dancer", "dancers"], "sunrise": ["rise", "risen", "rises", "rising", "rose"],
        "sunset": ["set", "sets", "setting"], "procession": ["process", "processed", "processes", "processing"],
        "university": ["universal", "universally"], "space": ["spaced", "spacing"], "sewing": ["sewer", "sewers"],
        "postman": ["post", "posted", "posting", "posts"], "vineyard": ["vintner", "vintners"], "sol": ["sonne", "sonnen"],
        "mar": ["meer", "meere", "meeres"], "time": ["timed", "timing"], "well": ["welled", "welling"],
        "free": ["freed", "freeing", "frees"], "desert": ["deserted", "deserting"], "market": ["marketed", "marketing"],
        "game": ["gamed"], "fired": ["fire", "fires"], "fire": ["fired", "firing"], "fencing": FENCE,
        "mining": ["mine"], "laundry": ["launder", "laundered", "launderer", "launderers", "laundering", "launders"],
        "detailing": ["detail", "detailed", "details"], "detective|holmes|sherlock": ["detect", "detected", "detecting",
        "detects"], "diving": ["dove"],
    },
    "basic_readout": {"march": ["marched", "marches", "marching"], "spring": ["sprang", "sprung", "springing"],
                      "poker": ["poke", "poked", "pokes", "poking"]},
    "directed_modulation": {"fencing": FENCE},
    "user_modeling": {"engaged": ["engage", "engages", "engaging"], "fish": ["fished", "fishing"]},
}


def stems(base: str) -> set[str]:
    """The base and the stems its inflections are built on (swimming -> swim, swimm; carry -> carri; stop -> stopp)."""
    out = {base, base + base[-1]}
    if base.endswith("e"):
        out.add(base[:-1])
    if base.endswith("y"):
        out.add(base[:-1] + "i")
    for suf in ("ing", "ed", "es", "s"):  # not -er: a target ``painter`` is no inflection of ``paint``
        s = base[: -len(suf)]
        if base.endswith(suf) and len(s) >= 2:
            out |= {s, s + "e"} | ({s[:-1]} if s[-1] == s[-2] else set()) | ({s[:-1] + "y"} if s.endswith("i") else set())
    return out


def inflection(form: str, base: str, forms_: set[str]) -> bool:
    """Whether ``form`` is a regular inflection of ``base`` (a comparative only with its pair), or listed irregular."""
    if form in IRREGULAR:
        return True
    st = stems(base)
    if form in st or any(form == c + s for c in st for s in SUFFIXES):
        return True
    for c in st:
        if form in (c + "er", c + "r"):
            return bool({c + "est", c + "st"} & forms_)
        if form in (c + "est", c + "st"):
            return bool({c + "er", c + "r"} & forms_)
    return False


def clean(family: str, k: str, words: list[str]) -> list[str]:
    bases = k.split("|")
    if any(b.isdigit() or b in NUMBERS for b in bases):  # numbers: their other spelling only
        return number_forms(bases)
    if any(len(b) == 1 for b in bases):  # letters: no forms
        return []
    drop = REJECT_ANY | set(REJECT.get(family, {}).get(k, ()))
    keep = [w for w in words if w not in drop]
    if family != "association":
        keep = [w for w in keep if any(inflection(w, b, set(words)) for b in bases)]
    return keep


def targets(family: str) -> dict[str, str]:
    """Target key -> one item's prompt (the sense), over the family's fit, val and bench banks."""
    out: dict[str, str] = {}
    for split in banks.SPLITS:
        try:
            bank = banks.load(family, split)
        except FileNotFoundError:
            continue
        for it in bank.items:
            base = score.accepted_forms(it)
            if base and not any(" " in f for f in base):
                prompt = it.get("prompt") or str(it.get("messages", ""))[-300:]
                out.setdefault(forms.key(base), " ".join(str(prompt).split())[:240])
    return out


def ask(client, family: str, batch: list[tuple[str, str]]) -> tuple[dict[str, list[str]], float]:
    rule = INFLECT + ("\n" + RELATED if family == "association" else "")
    body = "\n".join(f"{i}\t{k.replace('|', ' / ')}\t{ctx}" for i, (k, ctx) in enumerate(batch))
    cost = 0.0
    for attempt in range(3):
        r = client.chat.completions.create(model=DEV_JUDGE, temperature=0, max_tokens=60 * len(batch) + 300,
                                           messages=[{"role": "user", "content": PROMPT.format(rule=rule) + body}],
                                           extra_body={"reasoning": {"enabled": False}})
        cost += float((r.usage.model_extra or {}).get("cost") or 0)
        raw = r.choices[0].message.content or ""
        try:
            got = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
            break
        except ValueError:
            if attempt == 2:
                return {}, cost
    out = {}
    for i, words in got.items():
        if not (str(i).isdigit() and int(i) < len(batch)) or not isinstance(words, list):
            continue
        k = batch[int(i)][0]
        base = set(k.split("|"))
        out[k] = sorted({w.strip().lower() for w in words if isinstance(w, str)} - base)
        out[k] = [w for w in out[k] if WORD.fullmatch(w)]
    return out, cost


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", choices=FAMILIES)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--clean", action="store_true", help="apply the review rules to the tables (no calls)")
    ap.add_argument("--numbers", action="store_true", help="add digit <-> number-word forms to the tables in place")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    assert not set(FAMILIES) & set(MULTI_TOKEN)

    if args.clean:
        return clean_tables([args.family] if args.family else FAMILIES)
    if args.numbers:
        return add_numbers([args.family] if args.family else FAMILIES)
    jobs, tables = [], {}
    for family in [args.family] if args.family else FAMILIES:
        path = forms.path_of(family)
        tables[family] = json.loads(path.read_text()) if path.exists() else {"meta": {}, "forms": {}}
        todo = [(k, ctx) for k, ctx in targets(family).items() if k not in tables[family]["forms"]]
        jobs += [(family, todo[a: a + BATCH]) for a in range(0, len(todo), BATCH)]
        print(f"{family}: {len(tables[family]['forms'])} in the table, {len(todo)} to go")
    if args.dry_run or not jobs:
        return

    from openai import OpenAI

    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key(), timeout=120)
    t0, spent = time.time(), {f: 0.0 for f in tables}
    with ThreadPoolExecutor(args.workers) as pool:
        futs = {pool.submit(ask, client, f, b): (f, b) for f, b in jobs}
        for fut in as_completed(futs):
            f, b = futs[fut]
            got, cost = fut.result()
            tables[f]["forms"].update(got)
            spent[f] += cost
            if len(got) < len(b):
                print(f"  {f}: {len(b) - len(got)} targets got no reply (rerun to retry)", file=sys.stderr)
    for f, t in tables.items():
        if not spent[f]:
            continue
        t["meta"] = {"model": DEV_JUDGE, "built": str(date.today()),
                     "rule": "inflections" + (" + derived words naming the same thing" if f == "association" else ""),
                     "spend_usd": round(float(t["meta"].get("spend_usd", 0)) + spent[f], 4),
                     "note": "unpinned model's draft, reviewed by hand; edit freely, a rebuild keeps existing keys"}
        t["forms"] = dict(sorted(t["forms"].items()))
        forms.path_of(f).parent.mkdir(parents=True, exist_ok=True)
        forms.path_of(f).write_text(json.dumps(t, ensure_ascii=False, indent=1) + "\n")
    print(f"done in {time.time() - t0:.0f} s, ${sum(spent.values()):.3f}")


def clean_tables(families) -> None:
    """Apply ``clean`` to each table in place; print the dropped and kept forms that are vocabulary tokens (only those
    can change a score). The draft is kept beside the table as ``<family>.draft.json``."""
    from transformers import AutoTokenizer
    from umot.provenance import PINS
    from wsbench.produce.render import display_tokens

    from jlm.lens import MODEL

    tok = AutoTokenizer.from_pretrained(MODEL, revision=PINS[MODEL])
    vocab = {score.normalise(t) for t in display_tokens(tok, list(range(len(tok))))}
    for f in families:
        path = forms.path_of(f)
        draft = path.with_suffix(".draft.json")
        if not draft.exists():
            draft.write_text(path.read_text())
        t = json.loads(draft.read_text())
        out = {k: clean(f, k, v) for k, v in t["forms"].items()}
        dropped = {k: [w for w in v if w not in out[k] and w in vocab] for k, v in t["forms"].items()}
        kept = {k: [w for w in v if w in vocab] for k, v in out.items()}
        print(f"== {f}: kept {sum(map(len, out.values()))} forms ({sum(map(len, kept.values()))} tokens), dropped "
              f"{sum(len(v) - len(out[k]) for k, v in t['forms'].items())}")
        print("  dropped tokens: " + "; ".join(f"{k}: {','.join(v)}" for k, v in dropped.items() if v))
        print("  kept tokens:    " + "; ".join(f"{k}: {','.join(v)}" for k, v in kept.items() if v))
        t["forms"] = out
        t["meta"]["cleaned"] = "build_forms.py --clean (review rules in the module docstring)"
        path.write_text(json.dumps(t, ensure_ascii=False, indent=1) + "\n")


def add_numbers(families) -> None:
    """Add each number key's other spelling (``number_forms``) to the tables in place, keeping every other form and
    hand edit; print what was added."""
    for f in families:
        path = forms.path_of(f)
        if not path.exists():
            continue
        t = json.loads(path.read_text())
        added = {}
        for k, v in t["forms"].items():
            new = [w for w in number_forms(k.split("|")) if w not in v]
            if new:
                t["forms"][k] = v + new
                added[k] = new
        rule = t["meta"].get("rule", "")
        if added and "numbers" not in rule:
            t["meta"]["rule"] = rule + "; numbers: digit <-> English word"
        print(f"== {f}: {len(added)} number keys gained a form" + (": " + "; ".join(f"{k}: {','.join(v)}" for k, v in added.items()) if added else ""))
        path.write_text(json.dumps(t, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    main()
