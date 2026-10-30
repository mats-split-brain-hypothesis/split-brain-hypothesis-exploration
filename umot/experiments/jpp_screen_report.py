"""Tables from ``jpp_screen.py``: concept hit rate by layer per condition (the J++ paper's Figure 5 view),
and held-vs-mentioned rank separation (mention_control). Filtered ranks (J++ Readout Filtering).

  python experiments/jpp_screen_report.py --family mention_control
  python experiments/jpp_screen_report.py --family directed_modulation
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from jpp_screen import bank_rows  # noqa: E402
from m1_run import OUT_DEFAULT  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", required=True)
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--readout", default="rms")
    args = ap.parse_args()
    bank, _ = bank_rows(args.family)
    df = pd.read_json(OUT_DEFAULT / "jpp-screen" / f"{args.family}.jsonl", lines=True)
    df["cond"] = df["id"].map(lambda i: bank[i]["cond"].split("/")[0])
    df = df[df.readout == args.readout]
    big = 10**9
    df["rx"] = df["rxf"].fillna(big)
    df["ry"] = df["ryf"].fillna(big)
    has_x = df.groupby("id")["rxf"].transform(lambda s: s.notna().any())
    df = df[has_x]

    # Item-level best rank per layer (min over the item's cells), then hit rate per condition.
    per = df.groupby(["lens", "arm", "cond", "id", "layer"])[["rx", "ry"]].min().reset_index()
    per["hx"] = per["rx"] < args.k
    tab = per.groupby(["lens", "arm", "cond", "layer"])["hx"].mean().unstack("layer")
    n = per.groupby(["cond"])["id"].nunique()
    print(f"# {args.family}: X in top {args.k} (filtered) at any cell, by layer; readout {args.readout}; items with a rankable X: {n.to_dict()}")
    with pd.option_context("display.width", 250, "display.max_rows", 500):
        print(tab.round(2).to_string())

    if args.family == "mention_control":
        # Held X vs mentioned Y within holdmention prompts, and held X (hold) vs mentioned X (mention).
        for band, lo, hi in (("L40-48", 40, 48), ("L52-60", 52, 60)):
            b = per[(per.layer >= lo) & (per.layer <= hi)].groupby(["lens", "arm", "cond", "id"])[["rx", "ry"]].min().reset_index()
            hm = b[(b.cond == "holdmention") & (b.ry < big) & (b.rx < big)]
            g = hm.groupby(["lens", "arm"]).apply(
                lambda d: pd.Series({"n": len(d), "med_held_X": d.rx.median(), "med_mentioned_Y": d.ry.median(),
                                     "P(X better)": (d.rx < d.ry).mean()}), include_groups=False)
            print(f"\n# {band}: within one prompt (holdmention), best rank of held X vs mentioned Y")
            print(g.round(2).to_string())
            hx = b[b.cond.isin(["hold", "mention"]) & (b.rx < big)].groupby(["lens", "arm", "cond"])["rx"].median().unstack("cond")
            print(f"\n# {band}: median best rank of X when held vs when only mentioned (different prompts)")
            print(hx.round(0).to_string())


if __name__ == "__main__":
    main()
