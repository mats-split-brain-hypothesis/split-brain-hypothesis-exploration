"""Sweep several contrastive steering vectors for the association J-lens readout."""
import json
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import metric  # noqa: E402

LAYERS = [22, 24, 26, 28, 30]


def bench_ids(fam):
    return [it["name"] for it in json.load(open(f"data/dev/{fam}/fit.json"))["items"]]


def cap_bench(fam):
    spec = {"layers": LAYERS, "bench_items": bench_ids(fam), "family": fam, "split": "fit"}
    return metric.capture(spec)["mean"]


def cap_prompts(prompts, positions="last"):
    spec = {"layers": LAYERS, "prompts": prompts, "positions": positions}
    return metric.capture(spec)["mean"]


SCENES = [
    "The tent was striped and the clowns piled out of a tiny car while the ringmaster cracked his whip.",
    "The hearse rolled slowly past the lowered heads and the organ played a hymn nobody could finish.",
    "The bell rang and twenty children grabbed their backpacks and poured into the fluorescent hallway.",
    "The trenches were full of mud and the shells came over every few minutes while the soldiers kept their heads down.",
    "The gavel came down and the jury box emptied while the man in the orange suit stared at the floor.",
    "The cockpit lit up red and the pilot pulled back on the stick as the carrier deck fell away.",
    "The monks chanted in the cold stone corridor and the candles threw long shadows on the wall.",
    "The market stalls overflowed with spices and the vendors shouted over each other in a dozen tongues.",
    "The conductor raised his baton and the strings lifted their bows as the hall fell silent.",
    "The forge glowed orange and the hammer rang on the anvil while sparks flew into the dark.",
    "The sails were hoisted and the creak of the rigging mixed with the spray as the land fell behind.",
    "The microscope was focused and the slide showed a writhing field of cells under the stain.",
    "The ballot box was sealed and the volunteers counted the slips by lamplight long after midnight.",
    "The patient in the chair opened wide and the drill whined as the dentist leaned in.",
    "The combine harvester rolled across the field and the grain poured into the truck all afternoon.",
    "The chapel was dark and the confessional screen slid open as the penitent knelt down.",
]


def sweep(name, vecs):
    print(f"\n=== {name} ===", file=sys.stderr)
    best = (0, None)
    for pos in ["prefix", "context", "read"]:
        for sc in [0.5, 1.0, 2.0, 4.0]:
            r = metric.run_metric(vecs, pos, sc)
            tag = f"{pos:8s} s={sc:>4}  p@10={r['pass_at_10']:.4f}  r={r['mean_log10_rank']:.3f}"
            print(tag)
            if r["pass_at_10"] > best[0]:
                best = (r["pass_at_10"], (pos, sc, r))
    print(f"  best: {best[0]:.4f} at {best[1][0]},{best[1][1]}")
    return best


def main():
    results = {}
    # A: bench contrasts (plain render)
    print("capturing bench families...", file=sys.stderr)
    br = cap_bench("basic_readout")
    ty = cap_bench("typo")
    mh = cap_bench("multihop")
    um = cap_bench("user_modeling")
    results["br-ty"] = sweep("basic_readout - typo", {L: (br[L] - ty[L]).float() for L in LAYERS})
    results["br-mh"] = sweep("basic_readout - multihop", {L: (br[L] - mh[L]).float() for L in LAYERS})
    results["um-ty"] = sweep("user_modeling - typo", {L: (um[L] - ty[L]).float() for L in LAYERS})
    # B: prompt contrasts (chat render)
    print("capturing prompt contrasts...", file=sys.stderr)
    pos_p = [{"user": s + " Concept:", "assistant": ""} for s in SCENES]
    neg_p = [{"user": s + " Continue:", "assistant": ""} for s in SCENES]
    pm = cap_prompts(pos_p)
    nm = cap_prompts(neg_p)
    results["concept-continue"] = sweep("scene+Concept: - scene+Continue:", {L: (pm[L] - nm[L]).float() for L in LAYERS})
    # C: answer vs narrative
    pos_p2 = [{"user": s + " The answer is", "assistant": ""} for s in SCENES]
    neg_p2 = [{"user": s + " She then", "assistant": ""} for s in SCENES]
    pm2 = cap_prompts(pos_p2)
    nm2 = cap_prompts(neg_p2)
    results["answer-narrative"] = sweep("scene+answer - scene+then", {L: (pm2[L] - nm2[L]).float() for L in LAYERS})
    print("\n=== SUMMARY ===")
    for k, (score, (pos, sc, r)) in results.items():
        print(f"{k:20s} best p@10={score:.4f} at {pos},{sc}")


if __name__ == "__main__":
    main()
