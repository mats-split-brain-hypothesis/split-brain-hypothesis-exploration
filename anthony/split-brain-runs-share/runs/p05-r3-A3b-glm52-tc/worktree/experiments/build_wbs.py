"""White-bear stance steering vector from self-authored think/don't-think pairs.

Inspired by the reading-list paper on stance steering (Raman et al. 2026), which shows that a
concept-agnostic "think about X / don't think about X" stance direction, added at mid depth
with a large dose, makes implied concepts readable through the plain J-lens.  We build the
direction INDEPENDENTLY from our own contrast pairs (not WSB's directed_modulation items):
each pair shares the same concept and the same carrier sentence; only the stance instruction
differs.  The concept and carrier cancel, leaving the stance direction.

Capture at the assistant-turn carrier cells, layers 20-24.  Steer at layers 20-24 (above the
read band 26-30) so the model's own forward pass writes the implied concept into the read
position.  Large dose (the useful region is narrow and high).
"""
import json
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import metric  # noqa: E402

LAYERS = [20, 21, 22, 23, 24]

# 24 (concept, carrier) pairs.  Diverse concepts and neutral carriers.
PAIRS = [
    ("the body part clavicle", "The committee approved the minutes without changes."),
    ("the chess piece bishop", "She placed the document on the desk and left the room."),
    ("the bird species eagle", "The report was filed under section four of the archive."),
    ("the geological feature glacier", "He turned the key and the engine started on the second try."),
    ("the abstract concept justice", "The invoice was paid in full by the end of the quarter."),
    ("the musical instrument cello", "They walked to the corner store and bought a loaf of bread."),
    ("the colour indigo", "The meeting was rescheduled to Thursday at three o clock."),
    ("the tree species sequoia", "The pipes were replaced and the water ran clear again."),
    ("the mineral quartz", "She signed her name at the bottom of the form."),
    ("the emotion melancholy", "The train arrived at platform six exactly on time."),
    ("the sport fencing", "He adjusted the thermostat and sat down with the newspaper."),
    ("the celestial body Sirius", "The receipt was stapled to the bag and handed over."),
    ("the language Malayalam", "The shelves were dusted and the books returned to order."),
    ("the element tungsten", "She opened the window and the curtain moved with the breeze."),
    ("the fabric velvet", "The form was completed in triplicate and submitted."),
    ("the dynasty Merovingian", "The clock on the wall showed quarter past noon."),
    ("the constellation Orion", "He folded the letter and placed it in the envelope."),
    ("the dish risotto", "The ladder was leaning against the wall in the garage."),
    ("the organ pancreas", "She poured the water into the glass and set it down."),
    ("the planet Mercury", "The catalogue was updated with the new prices."),
    ("the concept entropy", "They locked the door and walked down the stairs together."),
    ("the instrument harpsichord", "The pattern was traced onto the fabric with chalk."),
    ("the weapon crossbow", "The contract was signed by both parties without amendment."),
    ("the flower magnolia", "He wiped the counter and arranged the chairs in a row."),
]

STANCE = [
    ("Think about {c} while you write. Now write exactly this sentence:", "{carrier}"),
    ("Do not think about {c} while you write. Now write exactly this sentence:", "{carrier}"),
]


def build_prompts(stance_idx: int):
    prompts = []
    for concept, carrier in PAIRS:
        instr, _ = STANCE[stance_idx]
        prompts.append({"user": instr.format(c=concept), "assistant": carrier})
    return prompts


def main():
    think_p = build_prompts(0)
    dont_p = build_prompts(1)
    print(f"capturing think ({len(think_p)} pairs)...", file=sys.stderr)
    tk = metric.capture({"layers": LAYERS, "prompts": think_p, "positions": "assistant"})
    print(f"capturing dont-think ({len(dont_p)} pairs)...", file=sys.stderr)
    dt = metric.capture({"layers": LAYERS, "prompts": dont_p, "positions": "assistant"})
    d = {}
    for L in LAYERS:
        d[L] = (tk["mean"][L] - dt["mean"][L]).float()
        print(f"L{L}: ||d||={d[L].norm().item():.3f}  cos(think,dont)={torch.nn.functional.cosine_similarity(tk['mean'][L],dt['mean'][L],dim=0).item():.4f}", file=sys.stderr)
    out = ROOT / "submission" / "wbs_vectors.pt"
    torch.save(d, out)
    print(f"saved -> {out}", file=sys.stderr)
    # sweep positions and scale. per-layer step s_l = 0.13*||d_l||; dose k; vector=d_l, scale=0.13*k
    # paper best k=6 -> scale ~ 0.78. sweep around it.
    print("\n--- sweep ---")
    best = (0, None)
    for pos in ["read", "context", "prefix"]:
        for sc in [0.3, 0.5, 0.78, 1.0, 1.5, 2.0]:
            r = metric.run_metric(d, pos, sc)
            tag = f"{pos:8s} scale={sc:>5}  p@10={r['pass_at_10']:.4f}  rank={r['mean_log10_rank']:.3f}"
            print(tag)
            if r["pass_at_10"] > best[0]:
                best = (r["pass_at_10"], (pos, sc))
    print(f"\nBEST: p@10={best[0]:.4f} at {best[1]}")


if __name__ == "__main__":
    main()
