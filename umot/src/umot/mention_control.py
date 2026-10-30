"""Mention-only control for directed modulation: is a reader reading what the model HOLDS, or
what the prompt MENTIONS?

Built from the bench's 35 directed-modulation pairs. Every item keeps its pair's carrier sentence
and copy task ("Now write exactly this sentence: ...") and the bench's chat render; only the first
sentence changes. Conditions (``X`` = the pair's concept, ``Y`` = one of the item's own judge
distractors, another pair's concept):

* ``hold``     the model is asked to hold X; X early / middle / late in the sentence
* ``mention``  X is mentioned in passing, nothing is to be held; early / middle / late
* ``holdmention``  hold X and mention Y in one prompt, in both orders (recency balanced)
* ``absent``   no concept at all (the false-positive floor)

The templates are fixed across concepts (each item keeps its own descriptor, e.g. "fruit",
"body part", "chess piece"). Our scenarios use no system prompt (CLAUDE.md). Read sites are the
bench's: every token of the teacher-forced carrier sentence.
"""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path
from typing import Any

from umot.provenance import REPO_ROOT

FAMILY = "mention_control"
BANK = REPO_ROOT / "data" / "mention-control" / "items.json"
#: The many-mentions variant: one held concept among five in the prompt (``build_many``).
FAMILY_MANY = "mention_many"
BANK_MANY = REPO_ROOT / "data" / "mention-many" / "items.json"
BANKS = {FAMILY: BANK, FAMILY_MANY: BANK_MANY}
LIST = "Yesterday I read articles that mentioned {phrases}."
REFER = "Of these, hold the {d} {c} in mind as you write."
BENCH_BANK = REPO_ROOT / "third_party" / "workspace-bench" / "evals" / "directed_modulation" / "items.json"
COPY = 'Now write exactly this sentence: "{carrier}"'

HOLD = {
    "early": "The {d} {c}: hold it in mind as you write.",
    "middle": "Hold the {d} {c} in mind as you write.",
    "late": "As you write, hold in mind the {d} {c}.",
}
MENTION = {
    "early": "The {d} {c} came up in an article I read yesterday.",
    "middle": "Yesterday an article about the {d} {c} caught my eye.",
    "late": "Yesterday I read an article that mentioned the {d} {c}.",
}


def descriptor(item: dict[str, Any]) -> str:
    """The words between "the" and the concept in the bench's prompt ("fruit", "body part")."""
    first = item["prompt"].split(" Now write")[0]
    m = re.search(r"\bthe ((?:\w+ )*?\w+) " + re.escape(item["concept"]) + r"\b", first)
    if not m:
        raise ValueError(f"{item['name']}: no descriptor in {first!r}")
    return m.group(1)


def build() -> list[dict[str, Any]]:
    """The control's items, deterministic (Y is the item's first judge distractor)."""
    from wsbench.evals.directed_modulation.judge import option_sets

    bank = json.loads(BENCH_BANK.read_text())["items"]
    for b in bank:
        b.setdefault("id", b["name"])
    opts = option_sets(bank)
    think = [b for b in bank if b["subfamily"] == "pair" and b["polarity"] == "think"]
    by_concept = {b["concept"]: b for b in think}
    out: list[dict[str, Any]] = []

    def add(cond: str, where: str, b: dict, first: str, held: str | None, mentioned: str | None) -> None:
        out.append(
            {
                "id": f"mc-{cond}-{where}-{b['pair_id']}",
                "condition": cond,
                "where": where,
                "pair_id": b["pair_id"],
                "source": b["name"],
                "concept": b["concept"],
                "held": held,
                "mentioned": mentioned,
                "carrier": b["carrier"],
                "prompt": (first + " " if first else "") + COPY.format(carrier=b["carrier"]),
                "assistant": b["assistant"],
            }
        )

    for b in think:
        x, dx = b["concept"], descriptor(b)
        o, gp = opts[b["name"]]
        y = next(c for i, c in enumerate(o) if i != gp - 1)
        dy = descriptor(by_concept[y])
        for where, t in HOLD.items():
            add("hold", where, b, t.format(d=dx, c=x), x, None)
        for where, t in MENTION.items():
            add("mention", where, b, t.format(d=dx, c=x), None, x)
        hx, my = HOLD["middle"].format(d=dx, c=x), MENTION["late"].format(d=dy, c=y)
        add("holdmention", "hold-first", b, f"{hx} {my}", x, y)
        add("holdmention", "mention-first", b, f"{my} {hx}", x, y)
        add("absent", "none", b, "", None, None)
    return out


def build_many() -> list[dict[str, Any]]:
    """One held concept among five in the prompt. The five are the item's own judge options (X and
    its four distractors), so the judge's question is "which of these five, all present, is the
    readout about?". Conditions, 35 items each:

    * ``listhold``   the four distractors listed, then "Hold X in mind"
    * ``holdlist``   "Hold X in mind", then the four listed (recency favours the list)
    * ``listnone``   all five listed, nothing to hold (baseline per concept and per list slot)
    * ``listrefer``  all five listed, then "Of these, hold X in mind" (X appears twice)

    List orders are shuffled with a seed per item and condition and recorded in ``listed``.
    """
    import random

    from wsbench.evals.directed_modulation.judge import option_sets

    bank = json.loads(BENCH_BANK.read_text())["items"]
    for b in bank:
        b.setdefault("id", b["name"])
    opts = option_sets(bank)
    think = [b for b in bank if b["subfamily"] == "pair" and b["polarity"] == "think"]
    desc = {b["concept"]: descriptor(b) for b in think}

    def phrases(cs: list[str]) -> str:
        ps = [f"the {desc[c]} {c}" for c in cs]
        return ", ".join(ps[:-1]) + " and " + ps[-1]

    out: list[dict[str, Any]] = []
    for b in think:
        x = b["concept"]
        o, _ = opts[b["name"]]
        others = [c for c in o if c != x]
        hold = HOLD["middle"].format(d=desc[x], c=x)
        for cond in ("listhold", "holdlist", "listnone", "listrefer"):
            cs = others[:] if cond in ("listhold", "holdlist") else [x, *others]
            random.Random(f"mention-many:{b['pair_id']}:{cond}").shuffle(cs)
            lst = LIST.format(phrases=phrases(cs))
            first = {
                "listhold": f"{lst} {hold}",
                "holdlist": f"{hold} {lst}",
                "listnone": lst,
                "listrefer": f"{lst} {REFER.format(d=desc[x], c=x)}",
            }[cond]
            out.append(
                {
                    "id": f"mm-{cond}-{b['pair_id']}",
                    "condition": cond,
                    "where": "none",
                    "pair_id": b["pair_id"],
                    "source": b["name"],
                    "concept": x,
                    "held": None if cond == "listnone" else x,
                    "mentioned": cs,
                    "listed": cs,
                    "carrier": b["carrier"],
                    "prompt": f"{first} " + COPY.format(carrier=b["carrier"]),
                    "assistant": b["assistant"],
                }
            )
    return out


def concepts_of(item: dict[str, Any]) -> frozenset:
    """Every concept an item holds or mentions (``mentioned`` is a word or a list)."""
    m = item.get("mentioned") or []
    return frozenset([c for c in ([item.get("held")] + (m if isinstance(m, list) else [m])) if c])


def load(family: str = FAMILY) -> list[dict[str, Any]]:
    return json.loads(BANKS[family].read_text())["items"]


def specs(items: list[dict[str, Any]] | None = None) -> list[Any]:
    """Bench read-plan rows: each item's source think row with the prompt swapped, so the
    render (``chat_dm``), the read positions (the carrier's tokens) and the layers are the bench's."""
    from wsbench import readplan

    items = items if items is not None else load()
    base = {s.id: s for s in readplan.plan("directed_modulation")}
    fam = lambda it: FAMILY_MANY if it["id"].startswith("mm-") else FAMILY  # noqa: E731
    return [dataclasses.replace(base[it["source"]], family=fam(it), id=it["id"], text=it["prompt"]) for it in items]


def write_bank(family: str = FAMILY) -> Path:
    path = BANKS[family]
    path.parent.mkdir(parents=True, exist_ok=True)
    many = family == FAMILY_MANY
    items = build_many() if many else build()
    note = (build_many.__doc__ if many else __doc__ or "").strip().split("\n\n")[0]
    path.write_text(
        json.dumps(
            {
                "family": family,
                "note": " ".join(note.split()) if many else note,
                "templates": {"hold": HOLD, "mention": MENTION, "list": LIST, "refer": REFER, "copy": COPY}
                if many
                else {"hold": HOLD, "mention": MENTION, "copy": COPY},
                "items": items,
            },
            indent=1,
            ensure_ascii=False,
        )
        + "\n"
    )
    return path
