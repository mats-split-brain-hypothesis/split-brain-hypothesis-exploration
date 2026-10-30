"""Build several NOVEL steering-direction contrast families (distinct from the white-bear
"think / don't-think" stance), all from prompts I write myself. Computes d_l = mean(pos) -
mean(neg) per family and saves unit vectors. Run one family: python work/build_novel.py F1
"""

import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import metric
from scenes import SCENES

LAYERS = list(range(14, 31))


def f1_specs():
    """name vs continue: elicit the single-word topic vs continue the passage (task contrast)."""
    pos, neg = [], []
    for s, _ in SCENES:
        pos.append({"user": "Identify the single word that best captures the passage below.\n\nPassage: " + s,
                    "assistant": "Topic:"})
        neg.append({"user": "Write the most likely next sentence of the passage below.\n\nPassage: " + s,
                    "assistant": "Next:"})
    return pos, neg


def f2_specs():
    """understand vs not: comprehend the scene's meaning vs read without forming one (comprehension stance)."""
    pos, neg = [], []
    for s, _ in SCENES:
        pos.append({"user": "Read the passage below and understand what it really means.\n\nPassage: " + s,
                    "assistant": "Meaning:"})
        neg.append({"user": "Read the passage below without forming any understanding of it.\n\nPassage: " + s,
                    "assistant": "Transcript:"})
    return pos, neg


def f4_specs():
    """one-word summary function vector: in-context exemplars of passage->word, query last (task FV)."""
    pos, neg = [], []
    n = len(SCENES)
    for i in range(0, n - n % 3, 3):
        g = SCENES[i:i + 3]
        pos.append({"user": "Passage: %s\nWord: %s\n\nPassage: %s\nWord: %s\n\nPassage: %s\nWord:"
                            % (g[0][0], g[0][1], g[1][0], g[1][1], g[2][0]),
                    "assistant": ""})
        neg.append({"user": "Passage: %s\n\nPassage: %s\n\nPassage: %s"
                            % (g[0][0], g[1][0], g[2][0]),
                    "assistant": ""})
    return pos, neg


FAMILIES = {"F1": f1_specs, "F2": f2_specs, "F4": f4_specs}


def main():
    fam = sys.argv[1]
    pos, neg = FAMILIES[fam]()
    specs = [("pos", pos), ("neg", neg)]
    out = {}
    for tag, prompts in specs:
        spec = {"layers": LAYERS, "positions": "last", "prompts": prompts}
        r = metric.capture(spec)
        out[tag] = r["mean"]
        print(f"[{fam}] {tag}: {r['n_prompts']} prompts", file=sys.stderr)
    u = {}
    print("layer  ||d_l||")
    for L in LAYERS:
        d = (out["pos"][L] - out["neg"][L]).float()
        nrm = d.norm().item()
        print(f"{L:5d}  {nrm:8.4f}")
        u[L] = d / d.norm()
    band = {L: u[L] for L in [20, 21, 22, 23, 24]}
    torch.save(band, f"work/{fam}_band.pt")
    torch.save(u, f"work/{fam}_u.pt")
    print(f"saved work/{fam}_band.pt", file=sys.stderr)


if __name__ == "__main__":
    main()