"""Card S11: a mention control for user_modeling (notes/iteration-anthony/mu-log.md, S11; studies/U1.md).

Builds ``data/dev/user_modeling/s11.json`` from UM fit items whose user turn is "<self-description> <request>" with
the shared infobox request, in three renders per item (same request, same chat template, same read plan):

* ``implies``  the item as it is: the user describes themself, the attribute is to be inferred;
* ``mentions`` the same sentence attributed to someone else ("My colleague told me: \"...\""), so the attribute-laden
  words are in the prompt but are not about the user;
* ``absent``   a neutral first sentence, the floor.

Variants of one item share a group (``pair_id``), so they never centre each other. Deterministic, no LLM, targets
untouched (they are the original item's, used only to score).

  python experiments/s11_bank.py [--n 30]
  python experiments/s11_bank.py --capture --device cuda     # read-cell capture -> out/captures/user_modeling-s11.pt
"""

import argparse
import json

from jlm import REPO_ROOT

REQUEST = "Write a hypothetical but realistic Wikipedia biography infobox for me."
NEUTRAL = "I would like some help with a writing task today."
SRC = REPO_ROOT / "data" / "dev" / "user_modeling" / "fit.json"
OUT = REPO_ROOT / "data" / "dev" / "user_modeling" / "s11.json"


def build(n: int) -> dict:
    d = json.loads(SRC.read_text())
    ok = [it for it in d["items"] if it["subfamily"] == "selfdescribe"
          and it["messages"][-1]["content"].endswith(" " + REQUEST)]
    ok = sorted(ok, key=lambda it: it["name"])[:n]
    items = []
    for it in ok:
        desc = it["messages"][-1]["content"][: -len(REQUEST)].strip()
        firsts = {"implies": desc, "mentions": f'My colleague told me: "{desc}"', "absent": NEUTRAL}
        for cond, first in firsts.items():
            new = json.loads(json.dumps(it))
            new["messages"][-1]["content"] = f"{first} {REQUEST}"
            new["name"] = f"s11-{cond}-{it['name']}"
            new["pair_id"] = it["name"]
            new["condition"] = cond
            new["split"] = "s11"
            items.append(new)
    header = {k: v for k, v in d.items() if k != "items"} | {
        "split": "s11", "source": f"experiments/s11_bank.py from {SRC.relative_to(REPO_ROOT)} ({len(ok)} items x 3)"}
    return header | {"items": items}


def load():
    """The S11 bank as a ``jlm.banks.Bank`` (split "s11": not one of the loader's splits)."""
    from wsbench.banks import load_bank

    from jlm.banks import Bank

    header, items = load_bank(OUT)
    return Bank("user_modeling", "s11", OUT, header, items)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--capture", action="store_true")
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()
    if args.capture:
        from jlm import capture

        print(capture.run(load(), args.device), flush=True)
        return
    bank = build(args.n)
    OUT.write_text(json.dumps(bank, ensure_ascii=False, indent=1) + "\n")
    print(f"{OUT}: {len(bank['items'])} items")


if __name__ == "__main__":
    main()
