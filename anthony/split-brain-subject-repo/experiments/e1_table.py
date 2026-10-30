"""Strict pass@10 (piece proxy on _mt) per family for a list of arms on one split, with the macro and the macro
difference against a reference arm: the screening table of night-2 instance B's study files.

  python experiments/e1_table.py --split fit --ref "fam@self|cos" --arms "zero|cos,fam@self|cos,s18k8@self|cos"
"""

import argparse
import json

from jlm import OUT
from jlm.mu.clusters import FAMILIES

SHORT = {"typo": "typo", "association": "assoc", "basic_readout": "basic", "multihop": "mhop", "multilingual": "mling",
         "user_modeling": "UM", "directed_modulation": "DM", "typo_mt": "typo_mt", "multihop_mt": "mhop_mt",
         "basic_readout_mt": "basic_mt", "multilingual_mt": "mling_mt"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="fit")
    ap.add_argument("--arms", required=True)
    ap.add_argument("--ref", default="fam@self|cos")
    ap.add_argument("--score", default="strict", help="strict | strict_masked")
    ap.add_argument("--drop", default="", help="families left out of the macro (e.g. user_modeling,directed_modulation)")
    args = ap.parse_args()
    arms = args.arms.split(",")
    S = {f: json.loads((OUT / "eval" / f / args.split / "summary.json").read_text())["result"]["arms"] for f in FAMILIES}

    def v(f, a):
        r = S[f].get(a, {}).get(args.score, {})
        return r.get("value")

    keep = [f not in args.drop.split(",") for f in FAMILIES]
    ref = [v(f, args.ref) for f, k in zip(FAMILIES, keep) if k]
    print("| arm | " + " | ".join(SHORT[f] for f in FAMILIES) + " | macro | vs ref |")
    print("|---|" + "---|" * (len(FAMILIES) + 2))
    for a in arms:
        xs = [v(f, a) for f in FAMILIES]
        cells = " | ".join("-" if x is None else f"{x:.3f}" for x in xs)
        ok = [x for x, k in zip(xs, keep) if k and x is not None]
        m = sum(ok) / len(ok) if len(ok) == sum(keep) else None
        d = None if m is None or None in ref else m - sum(ref) / len(ref)
        print(f"| {a} | {cells} | {'-' if m is None else f'{m:.3f}'} | {'-' if d is None else f'{d:+.3f}'} |")


if __name__ == "__main__":
    main()
