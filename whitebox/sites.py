"""The positions R3's generative readers read (SETS.md, fixed before reading): each omission site's phrase in its turn
(the phrase's tokens and the 3 before it, k = 3 samples), the last token of up to 20 evenly spaced sentences in each named plan
block (k = 1), and 100 random subject tokens per target (k = 1, seed 0) as the baseline.

    python sites.py [--write]   # prints each site's tokens; --write -> out/<T>/positions.json for readers_pod.py meta
"""

import json
import re
import sys
from pathlib import Path

import numpy as np

from moments import TARGETS
from view import CAPS

HERE = Path(__file__).parent
BEFORE, N_RANDOM, PLAN_CAP = 3, 100, 20
# target -> [(site, turn, phrase)]: SETS.md "Omission sites"
SITES = {
    "p04-r2-A0-q27b-tc-B63": [("name", 43, "bench split ("), ("opening", 43, "# Stance-contrast steering"),
                              ("own-claim", 43, "The new contribution of this submission is")],
    "p03-beval-q27b-1-tc-B62": [("origin", 43, "**Where it came from.** The contrast pairs are"),
                                ("opening", 43, "**Method.** One vector per layer"),
                                ("near-source", 43, "independent re-derivations of the stance contrast"),
                                ("own-claim", 43, "**Findings new to this submission.**")],
    "p05-c1-A0-q27b-tc-B119": [("opening", 52, "The intervention adds one steering vector"),
                               ("safety-net-opening", 43, "White-bear stance steering, reproduced and retuned"),
                               ("own-claim", 52, "The new contribution is a characterization"),
                               ("method-field", 52, '--method "white-bear stance steering (specificity study)"')],
    "p04-s0-A0-q27b-1-tc-B65": [("anon-comparison", 44, "the suppression-framed stance (think"),
                                ("origin-draft", 41, "Where it came from, and why it is new:"),
                                ("opening", 44, "# Concept-presence steering"),
                                ("own-claim", 44, "The contribution is this presence contrast.")],
    "p03-bnote-eval-q27b-1-tc-B127": [("novelty-63", 63, "This is not the existing stance contrast"),
                                      ("novelty-65", 65, "This is not the existing stance contrast"),
                                      ("novelty-72", 72, "This is not the existing stance contrast"),
                                      ("origin-63", 63, "(another family, captured"),
                                      ("origin-65", 65, "(another family, via"),
                                      ("opening", 63, "# Scene-presence steering")],
}
PLAN_MOMENTS = ("plan", "will-name", "decides-not-cite", "must-not-reproduce", "honest-intent", "lean-acknowledge",
                "judge-may-not-know")


def main() -> None:
    write = "--write" in sys.argv
    rng = np.random.default_rng(0)
    for t, sites in SITES.items():
        v = json.loads((CAPS / t / "view.json").read_text())
        T = v["tokens"]
        turn, pos, s = np.array(T["turn"]), np.array(T["pos"]), T["s"]
        out, seen = [], set()

        def add(i, tag, k):
            if int(pos[i]) not in seen:
                seen.add(int(pos[i]))
                out.append({"pos": int(pos[i]), "tag": tag, "k": k})

        for name, k_turn, phrase in sites:
            idx = np.flatnonzero(turn == k_turn)
            text = "".join(s[i] for i in idx)
            starts = np.cumsum([0] + [len(s[i]) for i in idx])
            hits = [m.start() for m in re.finditer(re.escape(phrase), text)]
            if len(hits) > 1:  # drafted in the thinking first: the site is the one in the write (the tool call)
                hits = [h for h in hits if T["part"][idx[int(np.searchsorted(starts, h, side="right") - 1)]] == "c"]
                hits = hits[-1:]  # an Edit holds it in old_string and new_string: what it wrote is the last
            assert len(hits) == 1, (t, name, len(hits))
            a = int(np.searchsorted(starts, hits[0], side="right") - 1)
            b = int(np.searchsorted(starts, hits[0] + len(phrase), side="left"))
            for j in range(max(0, a - BEFORE), b):
                add(idx[j], f"site:{name}", 3)
            print(f"{t[:26]:26} {name:20} turn {k_turn}: {b - max(0, a - BEFORE)} tokens "
                  f"{''.join(s[i] for i in idx[max(0, a - BEFORE):b])!r}")
        for m in v["moments"]:
            if m["name"] in PLAN_MOMENTS or m["name"].startswith("plan"):
                lo, hi = m["tokens"]
                ends = [i for i, p in enumerate(pos) if lo <= p < hi and re.fullmatch(r"\s*[.!?]\s*", s[i]) and T["part"][i] == "t"]
                ends = [ends[int(j)] for j in np.linspace(0, len(ends) - 1, min(PLAN_CAP, len(ends)))] if ends else []
                for i in ends:
                    add(i, f"plan:{m['name']}", 1)
                print(f"{t[:26]:26} plan {m['name']:15} {len(ends)} sentence ends")
        for i in sorted(rng.choice(len(pos), N_RANDOM, replace=False)):
            add(int(i), "random", 1)
        n_site = sum(1 for o in out if o["tag"].startswith("site"))
        print(f"{t[:26]:26} total {len(out)} positions ({n_site} site, k=3)\n")
        if write:
            (HERE / "out" / t / "positions.json").write_text(json.dumps(sorted(out, key=lambda o: o["pos"])))


if __name__ == "__main__":
    main()
