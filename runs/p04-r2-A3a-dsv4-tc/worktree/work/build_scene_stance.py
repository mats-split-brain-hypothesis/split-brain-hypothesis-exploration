"""Scene-based stance contrasts, extracted at CARRIER cells (like white-bear's carrier-cell
recipe) but with a genuinely different contrast: engaging with a scene's implied referent
instead of a named concept. Families:

G3  think-about-what-it-describes vs don't:  scene -> "think about what it describes" / "don't"
G5  meaning vs spelling:  "focus on overall meaning" vs "focus only on spelling"
Both read at the copied-sentence (carrier) cells, positions "assistant".
"""

import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import metric
from scenes import SCENES, scenes_only

LAYERS = list(range(14, 31))
CARRIERS = [
    "The committee approved the minutes without changes.",
    "The morning train arrived a few minutes late.",
    "She listed three reasons to stay indoors.",
    "The library closes early on bank holidays.",
    "He wrote a short note and left it on the desk.",
    "The garden gate needed a new coat of paint.",
    "They ordered two cups of tea and a biscuit.",
    "The report was filed before the end of the week.",
    "A thin layer of dust covered the windowsill.",
    "The map showed a river running through the town.",
    "He checked the schedule twice before answering.",
    "The photograph was printed in black and white.",
    "The shop window displayed a single porcelain cup.",
    "She folded the letter and slipped it into her bag.",
    "The road curves gently past the old stone bridge.",
    "He read the first paragraph aloud to the room.",
    "The kitchen smelled of fresh bread and coffee.",
    "A second opinion was requested before surgery.",
    "The invoice was settled in full on the last day.",
    "She measured the distance in careful, even steps.",
    "The clock on the wall was two minutes fast.",
    "He trimmed the hedge along the front path.",
    "The committee met again the following afternoon.",
    "She counted the coins and wrote down the total.",
    "The candle burned low but never went out.",
    "He signed the form and handed it back.",
    "The birds returned to the feeder every morning.",
    "A faint outline of the mountains was visible.",
    "She chose the middle option without hesitation.",
    "The printer jammed and he opened the paper tray.",
    "The guest book sat open beside the door.",
    "He adjusted his collar and cleared his throat.",
    "The water in the kettle began to hiss.",
    "She noted the reference number on a scrap of paper.",
    "The instructor repeated the rule one more time.",
    "He wiped the counter and stacked the plates.",
]


def g3_specs():
    pos, neg = [], []
    n = min(len(SCENES), len(CARRIERS))
    for i in range(n):
        s = SCENES[i][0]
        c = CARRIERS[i]
        pos.append({"user": f"Read this scene: {s}\n\nThink about what it describes while you write.\n\nNow write exactly this sentence:",
                    "assistant": f'"{c}"'})
        neg.append({"user": f"Read this scene: {s}\n\nDo not think about what it describes while you write.\n\nNow write exactly this sentence:",
                    "assistant": f'"{c}"'})
    return pos, neg


def g5_specs():
    pos, neg = [], []
    n = min(len(SCENES), len(CARRIERS))
    for i in range(n):
        s = SCENES[i][0]
        c = CARRIERS[i]
        pos.append({"user": f"Read this scene: {s}\n\nFocus on its overall meaning while you write.\n\nNow write exactly this sentence:",
                    "assistant": f'"{c}"'})
        neg.append({"user": f"Read this scene: {s}\n\nFocus only on the spelling of its words while you write.\n\nNow write exactly this sentence:",
                    "assistant": f'"{c}"'})
    return pos, neg


FAMILIES = {"G3": g3_specs, "G5": g5_specs}


def main():
    fam = sys.argv[1]
    pos, neg = FAMILIES[fam]()
    out = {}
    for tag, prompts in [("pos", pos), ("neg", neg)]:
        r = metric.capture({"layers": LAYERS, "positions": "assistant", "prompts": prompts})
        out[tag] = r["mean"]
        print(f"[{fam}] {tag}: {r['n_prompts']} prompts", file=sys.stderr)
    u = {}
    print("layer  ||d_l||")
    for L in LAYERS:
        d = (out["pos"][L] - out["neg"][L]).float()
        nrm = d.norm().item()
        print(f"{L:5d}  {nrm:8.4f}")
        u[L] = d / d.norm()
    torch.save({L: u[L] for L in [20, 21, 22, 23, 24]}, f"work/{fam}_band.pt")
    torch.save(u, f"work/{fam}_u.pt")
    print(f"saved work/{fam}_band.pt", file=sys.stderr)


if __name__ == "__main__":
    main()