"""The dense read (Anthony 2026-10-23: "does it say anything about omission before / while it writes?"): every token of
each run's final write (the tool call) and the 200 subject tokens leading into it, for the oracle lens at L32 / L44
(k = 3) and the text-only control; plus the two controls' write tokens (variants.py).

    python dense.py   -> out/<T>/positions_dense.json, and out/<T>/states_dense/ (subj_idx.npy + subj_L32/L44.npy: the
                         stored captures' rows at those positions, uploaded instead of recomputing on the pod)
"""

import json
from pathlib import Path

import numpy as np

from view import CAPS

HERE = Path(__file__).parent
LEAD = 200
FINAL = {"p04-r2-A0-q27b-tc-B63": [43], "p03-beval-q27b-1-tc-B62": [43], "p05-c1-A0-q27b-tc-B119": [52],
         "p04-s0-A0-q27b-1-tc-B65": [44], "p03-bnote-eval-q27b-1-tc-B127": [65, 72]}
LAYERS = (32, 44)


def main() -> None:
    for t, turns in FINAL.items():
        v = json.loads((CAPS / t / "view.json").read_text())
        T = v["tokens"]
        out = []
        for k in turns:
            w = [i for i, (tt, pt) in enumerate(zip(T["turn"], T["part"])) if tt == k and pt == "c"]
            out += [{"pos": T["pos"][i], "tag": f"dense:write-{k}", "k": 3} for i in w]
            out += [{"pos": T["pos"][i], "tag": f"dense:lead-{k}", "k": 3} for i in range(max(0, w[0] - LEAD), w[0])]
        out = sorted({o["pos"]: o for o in out}.values(), key=lambda o: o["pos"])
        (HERE / "out" / t / "positions_dense.json").write_text(json.dumps(out))
        subj = np.load(CAPS / t / "subj_idx.npy")
        pos = np.array([o["pos"] for o in out])
        rows = np.searchsorted(subj, pos)
        assert (subj[rows] == pos).all()
        d = HERE / "out" / t / "states_dense"
        d.mkdir(exist_ok=True)
        np.save(d / "subj_idx.npy", pos)
        for L in LAYERS:
            np.save(d / f"subj_L{L}.npy", np.load(CAPS / t / f"subj_L{L}.npy", mmap_mode="r")[rows])
        n_w = sum(o["tag"].startswith("dense:write") for o in out)
        print(f"{t}: {len(out)} positions ({n_w} write, {len(out) - n_w} lead)")


if __name__ == "__main__":
    main()
