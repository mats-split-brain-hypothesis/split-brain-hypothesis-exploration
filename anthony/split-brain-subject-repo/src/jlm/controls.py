"""Free controls against a g that scores by surfacing the prompt (notes/iteration-anthony/research-loop.md, "Controls").

- **Prompt forms**: an item's prompt-content tokens, as normalised display forms (``score.normalise``). Template
  tokens (forms in at least half of the bank's renders: chat markers, role names, the bench's instruction
  words) are left out, so what remains is the item's own content.
- **Echo**: the share of a cell's top 10 that are prompt forms. A gain that comes with more echo is suspect.
- **Masked readout** (written by ``jlm.read`` with ``mask_ids``): the top 10 after every vocabulary id whose form
  is a prompt form is removed. On strict-scored items it cannot remove a target (leaky items are not scored),
  so it can only *raise* strict pass; it matters where a judge credits prompt words and their variants, and on
  families whose targets the prompt may state (user_modeling, directed_modulation).

Echo and masking do not catch a g that surfaces *associates* of the prompt (association's targets are exactly
that); the mention control, shuffled g and the next-token baseline address that.

- **Semantic vocabulary** (``non_semantic_ids``; written by ``jlm.read`` as the arm's ``sem/`` files): J++'s Readout
  Filtering (Ayonrinde & Lindsey 2026, ``lens_evals.readout_evals.readout_eval_items.non_semantic_token_ids`` @
  safety-research/jpp_lens 93f02cd), so our numbers can be set beside theirs. Every id whose decoded string has no
  letter or digit (whitespace, punctuation, LM-head padding rows decoding to "") is removed from the vocabulary,
  except the ids the bank scores (its accepted ids), so no target becomes unrankable. Not a control on g: it changes
  the readout every arm is scored on, and the full-vocabulary readout stays the default.
"""

from collections import Counter, defaultdict
from collections.abc import Iterable
from typing import Any

from jlm.score import normalise

TEMPLATE_SHARE = 0.5


def prompt_forms(decoded: dict[str, list[str]], display: dict[str, list[str]] | None = None) -> dict[str, frozenset[str]]:
    """Item -> its prompt-content forms. ``decoded`` is each item's render as display tokens (``lens.display(ids)``)."""
    per = {i: {f for t in toks if (f := normalise(t).strip())} for i, toks in decoded.items()}
    n = Counter(f for fs in per.values() for f in fs)
    common = {f for f, k in n.items() if len(per) > 1 and k >= TEMPLATE_SHARE * len(per)}
    return {i: frozenset(fs - common) for i, fs in per.items()}


def mask_ids(forms: dict[str, frozenset[str]], vocab_display: list[str]) -> dict[str, list[int]]:
    """Item -> every vocabulary id whose form is one of its prompt forms (all casings and space variants)."""
    by_form: dict[str, list[int]] = defaultdict(list)
    for i, t in enumerate(vocab_display):
        if f := normalise(t).strip():
            by_form[f].append(i)
    return {item: sorted({i for f in fs for i in by_form.get(f, [])}) for item, fs in forms.items()}


def non_semantic_ids(tokenizer, vocab: int, spared: Iterable[int] = ()) -> list[int]:
    """J++'s exclusion list: ids in ``range(vocab)`` (the LM-head width) whose decode has no letter or digit, minus
    ``spared``. Special ids are kept, as in J++ (they decode word-like)."""
    keep = set(spared)
    decoded = tokenizer.batch_decode([[i] for i in range(vocab)])
    return [i for i, t in enumerate(decoded) if i not in keep and not any(ch.isalnum() for ch in t)]


#: Readout-composition classes (``token_class``), in display order: the first two are J++'s non-semantic ids.
TOKEN_CLASSES = ("space", "punct", "control", "word")


def token_class(text: str, special: bool) -> str:
    """The class of a vocabulary id from its decode: ``space`` (empty or only whitespace / newlines) and ``punct`` (no
    letter or digit otherwise: punctuation, symbols, markup) are what J++'s Readout Filtering removes; ``control`` (a
    special / added token such as chat markers, or a decode with a broken UTF-8 byte, U+FFFD) is unreadable as a word
    whether or not J++ keeps it; ``word`` is the rest (letters or digits)."""
    if special or "�" in text:
        return "control"
    if not any(ch.isalnum() for ch in text):
        return "space" if not text.strip() else "punct"
    return "word"


def echo(row: dict[str, Any], forms: frozenset[str]) -> float:
    """Share of the row's top tokens that are prompt forms."""
    toks = row["tokens"]
    return sum(normalise(t).strip() in forms for t in toks) / max(1, len(toks))


def echo_by_item(rows: Iterable[dict[str, Any]], forms: dict[str, frozenset[str]]) -> dict[str, float]:
    """Item -> mean echo over its cells and layers."""
    s: dict[str, list[float]] = defaultdict(lambda: [0.0, 0])
    for r in rows:
        acc = s[r["id"]]
        acc[0] += echo(r, forms.get(r["id"], frozenset()))
        acc[1] += 1
    return {i: a / n for i, (a, n) in s.items()}
