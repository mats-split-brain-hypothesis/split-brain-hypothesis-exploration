"""Concept families: for every directed-modulation concept, the token ids that count as "the model is
thinking of it", in tiers, so a readout can be scored against more than the exact word.

Tiers (a token is in at most one; the first that claims it wins):

  exact     single-token spellings of the bench's own match forms (" clavicle", "Clavicle" …)
  surface   cut-offs, inflections and typos of the concept, found over the whole vocabulary by rule:
            a prefix of the concept with >= max(4, ⌈len/2⌉) letters (" clav", "clavic"); the plural
            ("clavicles"); edit distance 1 (concept >= 7 letters) or 2 (>= 10), same first
            letter, length within 2. Candidates that are themselves dictionary words (/usr/share/dict/words:
            " brown" for brownie, "monkey" for donkey) are not surface forms
  related   specific associates and single-token translations from data/concept-families/related.json
            (written from the concept alone, before looking at readouts); words that are themselves bank
            concepts are dropped (donkey ↔ mule would credit the wrong item)
  shared    related tokens claimed by two or more concepts (citrus: citron and kumquat): not specific
  piece     the first sub-token of a multi-token form when it is itself a word (" brown" for brownie):
            how the word starts, but ambiguous
  category  the prompt's own descriptor words ("fruit", "body part"): the prompt says them, so they are
            an echo as much as a thought; the mention control has them too

Only the tokenizer and a word list are needed (no model). The output is committed, so rebuilding is only
needed after editing related.json. Output: data/concept-families/families.json.

  python experiments/concept_families.py
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from m1_run import MODEL  # noqa: E402

from umot.provenance import PINS, REPO_ROOT, Provenance, write_artefact  # noqa: E402

BANK = REPO_ROOT / "third_party/workspace-bench/evals/directed_modulation/items.json"
RELATED = REPO_ROOT / "data/concept-families/related.json"
OUT = REPO_ROOT / "data/concept-families/families.json"
LATIN = re.compile(r"^[a-zà-öø-ÿ]+$")
WORDS = Path("/usr/share/dict/words")


def edit1(a: str, b: str, limit: int) -> bool:
    """Damerau-Levenshtein distance <= limit (small strings; banded DP)."""
    if abs(len(a) - len(b)) > limit:
        return False
    prev2, prev = None, list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] != b[j - 1]))
            if prev2 is not None and i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                cur[j] = min(cur[j], prev2[j - 2] + 1)
        if min(cur) > limit:
            return False
        prev2, prev = prev, cur
    return prev[-1] <= limit


def main() -> None:
    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(MODEL, revision=PINS[MODEL])
    bank = json.loads(BANK.read_text())["items"]
    related = json.loads(RELATED.read_text())["related"]
    concepts: dict[str, dict] = {}
    for b in bank:
        if b["concept"] in concepts:
            continue
        m = re.search(r"\bthe ((?:\w+ )*?\w+) " + re.escape(b["concept"]) + r"\b", b["prompt"])
        forms = {f for u in b["units"] if u["role"] == "concept" for f in u["match"]}
        concepts[b["concept"]] = {"forms": forms, "descriptor": m.group(1) if m else ""}
    bank_words = {c.lower() for c in concepts}
    dictionary = {w.strip().lower() for w in WORDS.read_text().splitlines()} if WORDS.exists() else set()
    if not dictionary:
        print(f"warning: {WORDS} missing; surface forms are not filtered against real words")

    # the vocabulary, normalised once
    vocab = {}
    for i in range(len(tok)):
        s = tok.decode([i]).strip().lower()
        if LATIN.match(s):
            vocab[i] = s

    def single(word: str) -> list[int]:
        out = []
        for s in dict.fromkeys([word, " " + word, word.capitalize(), " " + word.capitalize(), word.lower(), " " + word.lower()]):
            t = tok(s, add_special_tokens=False)["input_ids"]
            if len(t) == 1:
                out.append(t[0])
        return out

    fam: dict[str, dict[str, set]] = {}
    unresolved: dict[str, list] = defaultdict(list)
    for c, info in concepts.items():
        cl = c.lower()
        tiers: dict[str, set] = {k: set() for k in ("exact", "surface", "related", "piece", "category")}
        for f in info["forms"]:
            tiers["exact"].update(single(f))
            for s in (f, " " + f):
                t = tok(s, add_special_tokens=False)["input_ids"]
                if len(t) > 1 and len(tok.decode(t[:1]).strip()) >= 3 and tok.decode(t[:1]).strip().lower() in dictionary:
                    tiers["piece"].add(t[0])
        min_prefix = max(4, math.ceil(0.5 * len(cl)))
        lim = 2 if len(cl) >= 10 else 1 if len(cl) >= 7 else 0
        for i, s in vocab.items():
            if s != cl and s in dictionary and s not in (cl + "s", cl + "es"):
                continue  # a real word (brown, monkey), unless an inflection of the concept itself
            if s == cl:
                tiers["surface"].add(i)  # odd spellings of the word itself (e.g. with punctuation)
            elif len(s) >= min_prefix and cl.startswith(s):
                tiers["surface"].add(i)
            elif s in (cl + "s", cl + "es"):
                tiers["surface"].add(i)
            elif lim and s[0] == cl[0] and abs(len(s) - len(cl)) <= 2 and edit1(s, cl, lim):
                tiers["surface"].add(i)
        for w in related.get(c, []):
            if w.lower() in bank_words:
                unresolved[c].append(f"{w} (dropped: another bank concept)")
                continue
            ids = single(w)
            if ids:
                tiers["related"].update(ids)
            else:
                unresolved[c].append(w)
        for w in info["descriptor"].split():
            if len(w) >= 3:
                tiers["category"].update(single(w))
        fam[c] = tiers

    # a token in two concepts' related tiers is not specific: move it to "shared"
    owners: dict[int, set] = defaultdict(set)
    for c, t in fam.items():
        for i in t["related"]:
            owners[i].add(c)
    for c, t in fam.items():
        t["shared"] = {i for i in t["related"] if len(owners[i]) > 1}
        t["related"] -= t["shared"]
        claimed: set = set()
        for k in ("exact", "surface", "related", "shared", "piece", "category"):
            t[k] -= claimed
            claimed |= t[k]

    out = {
        c: {k: [{"id": i, "text": tok.decode([i])} for i in sorted(v)] for k, v in t.items()}
        | {"descriptor": concepts[c]["descriptor"], "unresolved": unresolved.get(c, [])}
        for c, t in fam.items()
    }
    write_artefact(
        OUT,
        Provenance(model=MODEL, model_revision=PINS[MODEL], dataset="wsbench/directed_modulation",
                   extra={"rules": __doc__.split("\n\n")[1], "related": str(RELATED.relative_to(REPO_ROOT))}),
        {"families": out, "word_list": str(WORDS) if dictionary else None},
    )
    for c in list(out)[:6]:
        print(c, {k: [x["text"] for x in out[c][k]][:12] for k in ("exact", "surface", "related", "shared", "piece", "category")})
    print(f"-> {OUT} ({len(out)} concepts)")


if __name__ == "__main__":
    main()
