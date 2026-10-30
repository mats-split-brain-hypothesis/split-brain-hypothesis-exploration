"""jle x101's wikitext sample, kept here since jle/ moved back to its own repo (jlens-edits-1).

Seeded windows of wikitext-103-raw validation (not the lens's fit split), at most 2 per passage, after the standard
wikitext detokenisation. Byte-identical to x101's ``sample_ids(corpus_passages("wikitext"), ...)``.
"""

import random
import re
from typing import Any

REPO = "Salesforce/wikitext"
REVISION = "b08601e04326c79dfdd32d625aee71d232d685c3"  # jle's pin


def detok(s: str) -> str:
    """The standard wikitext detokenisation (as used for wikitext perplexity evaluations)."""
    s = s.replace("s '", "s'")
    s = re.sub(r"/' [0-9]/", r"/'[0-9]/", s)
    s = s.replace(" @-@ ", "-").replace(" @,@ ", ",").replace(" @.@ ", ".")
    s = s.replace(" : ", ": ").replace(" ; ", "; ").replace(" . ", ". ").replace(" ! ", "! ").replace(" ? ", "? ").replace(" , ", ", ")
    s = re.sub(r"\(\s*([^\)]*?)\s*\)", r"(\1)", s)
    s = re.sub(r"\[\s*([^\]]*?)\s*\]", r"[\1]", s)
    s = re.sub(r"{\s*([^}]*?)\s*}", r"{\1}", s)
    s = re.sub(r"\"\s*([^\"]*?)\s*\"", r'"\1"', s)
    s = re.sub(r"'\s*([^']*?)\s*'", r"'\1'", s)
    s = s.replace("= = = =", "====").replace("= = =", "===").replace("= =", "==")
    s = s.replace(" " + chr(176) + " ", chr(176)).replace(" \n", "\n").replace("\n ", "\n")
    s = s.replace(" N ", " 1 ").replace(" 's", "'s")
    if s.endswith(" ."):
        s = s[:-2] + "."
    return s


def passages() -> list[str]:
    """Paragraphs of wikitext-103-raw validation: non-empty lines that are not section headings, detokenised."""
    import datasets

    ds = datasets.load_dataset(REPO, "wikitext-103-raw-v1", split="validation", revision=REVISION)
    return [detok(t.strip()) for t in ds["text"] if t.strip() and not t.strip().startswith("=")]


def sample_ids(passages: list[str], tok: Any, n_docs: int, seq: int, seed: int, max_win: int = 2) -> list[list[int]]:
    """n_docs token windows: passages in a seeded order, each cut into non-overlapping windows of seq tokens (at most
    max_win per passage, so that no long text dominates), until n_docs windows are taken."""
    order = list(range(len(passages)))
    random.Random(f"x101:{seed}").shuffle(order)
    out = []
    for k in order:
        ids = tok(passages[k], add_special_tokens=False)["input_ids"]
        for w in range(min(len(ids) // seq, max_win)):
            out.append(ids[w * seq : (w + 1) * seq])
            if len(out) == n_docs:
                return out
    raise AssertionError(f"only {len(out)} windows of {seq} tokens")
