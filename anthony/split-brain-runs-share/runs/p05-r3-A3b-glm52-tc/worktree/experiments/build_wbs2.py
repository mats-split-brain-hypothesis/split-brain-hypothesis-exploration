"""White-bear stance vector from self-authored think/don't-think pairs (varied wordings).

The stance direction must average out the instruction tokens so only the stance remains.
We use 10 varied phrasing templates per condition, with diverse concepts and carriers.
"""
import json
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import metric  # noqa: E402

LAYERS = [20, 21, 22, 23, 24]

THINK_TEMPLATES = [
    "Think about {c} while you write. Now write exactly this sentence:",
    "Keep {c} in your thoughts as you write. Now write exactly this sentence:",
    "Try to focus on {c} as you write the sentence. Now write exactly this sentence:",
    "Hold {c} in mind while you write. Now write exactly this sentence:",
    "Bear {c} in mind as you write. Now write exactly this sentence:",
    "Dwell on {c} while you write. Now write exactly this sentence:",
    "Keep {c} at the front of your mind while you write. Now write exactly this sentence:",
    "Reflect on {c} as you write. Now write exactly this sentence:",
    "Let {c} occupy your thoughts as you write. Now write exactly this sentence:",
    "Carry {c} in your mind as you write. Now write exactly this sentence:",
]

DONT_TEMPLATES = [
    "Do not think about {c} while you write. Now write exactly this sentence:",
    "Keep {c} out of your thoughts as you write. Now write exactly this sentence:",
    "Try hard not to think about {c} as you write the sentence. Now write exactly this sentence:",
    "Put {c} out of your mind while you write. Now write exactly this sentence:",
    "Avoid thinking of {c} as you write. Now write exactly this sentence:",
    "Banish {c} from your thoughts as you write. Now write exactly this sentence:",
    "Keep {c} at the back of your mind while you write. Now write exactly this sentence:",
    "Push {c} aside as you write. Now write exactly this sentence:",
    "Keep your mind off {c} as you write. Now write exactly this sentence:",
    "Disregard {c} while you write. Now write exactly this sentence:",
]

CONCEPTS = [
    "the body part clavicle", "the chess piece bishop", "the bird species eagle",
    "the geological feature glacier", "the abstract concept justice",
    "the musical instrument cello", "the colour indigo", "the tree species sequoia",
    "the mineral quartz", "the emotion melancholy", "the sport fencing",
    "the celestial body Sirius", "the language Malayalam", "the element tungsten",
    "the fabric velvet", "the dynasty Merovingian", "the constellation Orion",
    "the dish risotto", "the organ pancreas", "the planet Mercury",
    "the concept entropy", "the instrument harpsichord", "the weapon crossbow",
    "the flower magnolia",
]

CARRIERS = [
    "The committee approved the minutes without changes.",
    "She placed the document on the desk and left the room.",
    "The report was filed under section four of the archive.",
    "He turned the key and the engine started on the second try.",
    "The invoice was paid in full by the end of the quarter.",
    "They walked to the corner store and bought a loaf of bread.",
    "The meeting was rescheduled to Thursday at three o clock.",
    "The pipes were replaced and the water ran clear again.",
    "She signed her name at the bottom of the form.",
    "The train arrived at platform six exactly on time.",
    "He adjusted the thermostat and sat down with the newspaper.",
    "The receipt was stapled to the bag and handed over.",
    "The shelves were dusted and the books returned to order.",
    "She opened the window and the curtain moved with the breeze.",
    "The form was completed in triplicate and submitted.",
    "The clock on the wall showed quarter past noon.",
    "He folded the letter and placed it in the envelope.",
    "The ladder was leaning against the wall in the garage.",
    "She poured the water into the glass and set it down.",
    "The catalogue was updated with the new prices.",
    "They locked the door and walked down the stairs together.",
    "The pattern was traced onto the fabric with chalk.",
    "The contract was signed by both parties without amendment.",
    "He wiped the counter and arranged the chairs in a row.",
]


def build_prompts(think: bool):
    prompts = []
    n = max(len(CONCEPTS), len(CARRIERS))
    for i in range(n):
        c = CONCEPTS[i % len(CONCEPTS)]
        carrier = CARRIERS[i % len(CARRIERS)]
        tmpl = (THINK_TEMPLATES + THINK_TEMPLATES)[i % len(THINK_TEMPLATES)] if think else (DONT_TEMPLATES + DONT_TEMPLATES)[i % len(DONT_TEMPLATES)]
        # vary which template pairs with which concept/carrier
        ti = (i * 3) % len(THINK_TEMPLATES) if think else (i * 3) % len(DONT_TEMPLATES)
        tmpl = (THINK_TEMPLATES if think else DONT_TEMPLATES)[ti]
        prompts.append({"user": tmpl.format(c=c), "assistant": carrier})
    return prompts


def main():
    tk_p = build_prompts(True)
    dt_p = build_prompts(False)
    print(f"think={len(tk_p)} dont={len(dt_p)}", file=sys.stderr)
    for cap_pos in ["assistant", "last"]:
        print(f"\n=== positions={cap_pos} ===", file=sys.stderr)
        tk = metric.capture({"layers": LAYERS, "prompts": tk_p, "positions": cap_pos})
        dt = metric.capture({"layers": LAYERS, "prompts": dt_p, "positions": cap_pos})
        d = {}
        for L in LAYERS:
            d[L] = (tk["mean"][L] - dt["mean"][L]).float()
            print(f"L{L}: ||d||={d[L].norm().item():.3f} cos={torch.nn.functional.cosine_similarity(tk['mean'][L],dt['mean'][L],dim=0).item():.4f}", file=sys.stderr)
        # sweep
        best = (0, None)
        for pos in ["prefix", "read", "context"]:
            for sc in [0.5, 0.78, 1.0, 1.3, 1.5, 2.0]:
                r = metric.run_metric(d, pos, sc)
                print(f"  {pos} s={sc:>4} p@10={r['pass_at_10']:.4f} r={r['mean_log10_rank']:.3f}")
                if r["pass_at_10"] > best[0]:
                    best = (r["pass_at_10"], (pos, sc, cap_pos))
        print(f"  BEST p@10={best[0]:.4f} at {best[1]}")
        if best[0] > 0.5:
            torch.save(d, ROOT / "submission" / "wbs_own_vectors.pt")
            print("  saved wbs_own_vectors.pt", file=sys.stderr)


if __name__ == "__main__":
    main()
