"""More stance contrast families, all with a NAMED concept + matched carrier (the structure that
works), but with genuinely different instruction semantics:

H1  keep-it-secret vs free-to-mention  (a second, unexpressed track is held)
H4  will-be-asked vs never-asked       (prospective memory / anticipated retrieval)
"""

import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import metric

CONCEPTS = [
    "a white bear", "the body part clavicle", "the chess piece bishop", "a red balloon",
    "the planet Saturn", "a paperclip", "the number seven", "the Eiffel Tower",
    "a striped zebra", "the colour turquoise", "a rusty key", "the constellation Orion",
    "a cactus", "the ocean tide", "a violin bow", "the smell of rain",
    "a lighthouse", "the game of cricket", "a walnut tree", "the letter Q",
    "a stop sign", "the month of February", "a bicycle chain", "the spice cinnamon",
    "a snowflake", "the island of Java", "a grandfather clock", "the sport of fencing",
    "a marble statue", "the word serendipity", "a fire escape", "the fraction one half",
    "a hummingbird", "the city of Kyoto", "a dentist's chair", "the concept of gravity",
]

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

LAYERS = list(range(14, 31))


def h1_specs():
    pos, neg = [], []
    for i in range(min(len(CONCEPTS), len(CARRIERS))):
        c, s = CONCEPTS[i], CARRIERS[i]
        pos.append({"user": f"Keep {c} a secret in your mind while you write. Now write exactly this sentence:",
                    "assistant": f'"{s}"'})
        neg.append({"user": f"Feel free to mention {c} while you write. Now write exactly this sentence:",
                    "assistant": f'"{s}"'})
    return pos, neg


def h4_specs():
    pos, neg = [], []
    for i in range(min(len(CONCEPTS), len(CARRIERS))):
        c, s = CONCEPTS[i], CARRIERS[i]
        pos.append({"user": f"While you write, remember you will be asked what {c} is later. Now write exactly this sentence:",
                    "assistant": f'"{s}"'})
        neg.append({"user": f"While you write, you will not be asked about {c} again. Now write exactly this sentence:",
                    "assistant": f'"{s}"'})
    return pos, neg


FAMILIES = {"H1": h1_specs, "H4": h4_specs}


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