"""Free scorers for the hidden-intermediate families (chain_intermediates, brew_intermediates) on token bags.

The bench judges these with an LLM; this is OUR free proxy on a cell's top 10, never a WorkspaceBench score.

chain: Qwen3.6's tokenizer has no multi-digit number token, so an intermediate n is credited through its single-token
forms: the digit (n < 10), the English number word ("eleven", "twenty") and the Chinese numeral (十一), each with or
without a leading space and in any case. A digit form is dropped when that digit is a token of the prompt (the start
23 puts "2" and "3" in the prompt), so a readout cannot pass by echoing an operand. Headline cell: the render's last
token, the bench's ``cells=last`` (the assistant onset). ``near``: the same rule with the intermediates shifted by
d in {-3..3} \\ {0} (a shift landing on the start, the answer or another intermediate is skipped), averaged over d; the
bench's ``null_top1_near`` in token form. It understates chance: the J-lens shows the same round Chinese numerals
(一百, 三十, 二十 ...) at nearly every item's last token, and a shift turns 30 into 27-33, which it rarely shows.

brew: the intermediate colour (the first stir) credited by its colour token. Every colour is named in the prompt's
table, so there is no leak exclusion; ``near`` here is the bench's own control: the same rule on each off-trajectory
colour, averaged, and ``stir_region`` (the start colour not yet read, nothing computable). Headline cells: the three
emission cells (``emit_asst``, ``emit_think``, ``emit_colon``).

Both: an item passes when the rule hits at any headline cell at any layer (the bench's any-layer rule). ``null`` (the
one ``lift`` subtracts) is the matched null: each item scored against another item's intermediates, over
``N_DERANGE`` seeded derangements, so the values keep the bank's own mix (round numbers, common colours) and a lens's
favourite tokens score the same on both sides. ``start`` and ``answer``: the same rule on the given value and the reply.
"""

from collections import defaultdict
from collections.abc import Iterable
from typing import Any

import numpy as np

from jlm.banks import Bank

FAMILIES = ("chain_intermediates", "brew_intermediates")
EMIT = ("emit_asst", "emit_think", "emit_colon")
SHIFTS = (-3, -2, -1, 1, 2, 3)
N_DERANGE = 20
_WORDS = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
          "seventeen eighteen nineteen").split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
_CN = "零一二三四五六七八九"


def english(n: int) -> str | None:
    if 0 <= n < 20:
        return _WORDS[n]
    if n < 100 and n % 10 == 0:
        return _TENS[n // 10]
    return None  # "twenty-one" is never one token


def chinese(n: int) -> str | None:
    if not 0 <= n < 100:
        return None
    if n < 10:
        return _CN[n]
    tens, ones = divmod(n, 10)
    return ("" if tens == 1 else _CN[tens]) + "十" + (_CN[ones] if ones else "")


def _single_ids(tokenizer, form: str) -> set[int]:
    """Vocabulary ids that spell ``form`` whole: with or without a leading space, lower / Capitalised."""
    out = set()
    for f in {form, form.capitalize()}:
        for s in (f, " " + f):
            ids = tokenizer(s, add_special_tokens=False)["input_ids"]
            if len(ids) == 1:
                out.add(ids[0])
    return out


class Scorer:
    """Per bank: accepted ids (for ranks), exclusions, the headline pass rule and its controls."""

    def __init__(self, bank: Bank, tokenizer, display, prompt_ids: dict[str, list[int]]):
        self.bank, self.family = bank, bank.family
        self.items = bank.by_id()
        self.tok, self.display = tokenizer, display
        self.prompt_ids = {i: set(v) for i, v in prompt_ids.items()}
        self.accepted = {i: sorted(self._ids(i, self._targets(it))) for i, it in self.items.items()}
        self.conf = {i: "" if ids else "unreachable" for i, ids in self.accepted.items()}
        self._names = {i: set(self.display(ids)) for i, ids in self.accepted.items()}

    # -- forms
    def _targets(self, it: dict[str, Any]) -> list:
        return list(it["intermediates"])

    def _ids(self, item_id: str, values: Iterable) -> set[int]:
        out: set[int] = set()
        for v in values:
            if self.family == "brew_intermediates":
                out |= _single_ids(self.tok, str(v))
                continue
            n = int(v)
            if 0 <= n < 10:
                out |= {i for i in _single_ids(self.tok, str(n)) if i not in self.prompt_ids[item_id]}
            for f in (english(n), chinese(n)):
                if f:
                    out |= _single_ids(self.tok, f)
        return out

    # -- cells
    def headline(self, rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        rows = list(rows)
        if self.family == "brew_intermediates":
            return [r for r in rows if self.items[r["id"]]["regions"].get(str(r["pos"])) in EMIT]
        last: dict[str, int] = defaultdict(lambda: -1)
        for r in rows:
            last[r["id"]] = max(last[r["id"]], r["pos"])
        return [r for r in rows if r["pos"] == last[r["id"]]]

    def region(self, rows: Iterable[dict[str, Any]], name: str) -> list[dict[str, Any]]:
        return [r for r in rows if self.items[r["id"]].get("regions", {}).get(str(r["pos"])) == name]

    @staticmethod
    def _hits(rows: Iterable[dict[str, Any]], names: dict[str, set[str]]) -> dict[str, bool]:
        hit = {i: False for i in names}
        for r in rows:
            if not hit[r["id"]] and names[r["id"]] and any(t in names[r["id"]] for t in r["tokens"]):
                hit[r["id"]] = True
        return hit

    def passes(self, rows: Iterable[dict[str, Any]]) -> dict[str, bool]:
        """Item id -> the intermediate is in a headline cell's top 10 at some layer."""
        return self._hits(self.headline(rows), self._names)

    def all_cells(self, rows: Iterable[dict[str, Any]]) -> dict[str, bool]:
        """The same rule over every read cell (chain: the question span; brew: all 24 pins)."""
        return self._hits(rows, self._names)

    # -- controls
    def _derangements(self) -> list[dict[str, set[str]]]:
        """The matched null: per draw, each item scored against ANOTHER item's intermediates (a seeded derangement),
        values equal to the item's own start, answer or intermediates dropped. The values keep the bank's own mix
        (round numbers, common colours), so pass - null is item-specific signal, not a lens's favourite tokens."""
        if not hasattr(self, "_der"):
            ids = list(self.items)
            rng = np.random.default_rng(0)
            draws = []
            for _ in range(N_DERANGE):
                while True:
                    perm = rng.permutation(len(ids))
                    if not (perm == np.arange(len(ids))).any():
                        break
                tab = {}
                for k, i in enumerate(ids):
                    it, other = self.items[i], self.items[ids[perm[k]]]
                    own = {it["start"], it["answer"], *it["intermediates"]}
                    tab[i] = set(self.display(sorted(self._ids(i, [v for v in other["intermediates"] if v not in own]))))
                draws.append(tab)
            self._der = draws
        return self._der

    def _control_names(self) -> list[dict[str, set[str]]]:
        """One name table per near-miss draw: chain, the intermediates shifted by d; brew, each off-trajectory colour."""
        if not hasattr(self, "_ctrl"):
            draws = []
            if self.family == "chain_intermediates":
                for d in SHIFTS:
                    tab = {}
                    for i, it in self.items.items():
                        bad = {it["start"], it["answer"], *it["intermediates"]}
                        vals = [v + d for v in it["intermediates"] if v + d not in bad and v + d >= 0]
                        tab[i] = set(self.display(sorted(self._ids(i, vals))))
                    draws.append(tab)
            else:
                k = max(len(it["off_trajectory"]) for it in self.items.values())
                for j in range(k):
                    draws.append({i: set(self.display(sorted(self._ids(i, it["off_trajectory"][j : j + 1]))))
                                  if j < len(it["off_trajectory"]) else set() for i, it in self.items.items()})
            self._ctrl = draws
        return self._ctrl

    def null_rate(self, rows: Iterable[dict[str, Any]], ids: list[str], draws=None) -> float | None:
        """Mean over control draws (default: the derangements) of the headline pass rate, each over the items the
        draw can score."""
        head = self.headline(rows)
        rates = []
        for tab in draws if draws is not None else self._derangements():
            h = self._hits(head, tab)
            ok = [i for i in ids if tab[i]]
            if ok:
                rates.append(float(np.mean([h[i] for i in ok])))
        return float(np.mean(rates)) if rates else None

    def extras(self, rows: list[dict[str, Any]], ids: list[str]) -> dict[str, Any]:
        """Controls and diagnostics for one arm's rows."""
        mean = lambda d: float(np.mean([d[i] for i in ids])) if ids else None  # noqa: E731
        out = {"pass": mean(self.passes(rows)), "null": self.null_rate(rows, ids),
               "near": self.null_rate(rows, ids, self._control_names()), "all_cells": mean(self.all_cells(rows))}
        out["lift"] = None if out["null"] is None or out["pass"] is None else out["pass"] - out["null"]
        for role in ("start", "answer"):  # diagnostics: the given number / colour, and the reply
            tab = {i: set(self.display(sorted(self._ids(i, [it[role]])))) for i, it in self.items.items()}
            ok = [i for i in ids if tab[i]]
            h = self._hits(self.headline(rows), tab)
            out[role] = float(np.mean([h[i] for i in ok])) if ok else None
        if self.family == "brew_intermediates":
            out["stir_region"] = mean(self._hits(self.region(rows, "stir"), self._names))
        else:
            for d in sorted({it["depth"] for it in self.items.values()}):
                sub = [i for i in ids if self.items[i]["depth"] == d]
                p = self.passes(rows)
                out[f"depth{d}"] = {"n": len(sub), "pass": float(np.mean([p[i] for i in sub])) if sub else None}
        return out
