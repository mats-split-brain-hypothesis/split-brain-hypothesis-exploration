"""Build a stance-direction steering vector from think / don't-think prompt pairs via the metric server.

Implements a white-bear-style contrast over prompts I write myself (task rule: contrasts over
self-written prompts are fine; nothing touches the association targets). Two captures -> d_l =
mean(think) - mean(dont), then unit vectors u_l for a band of layers. Saves work/wb_u.pt and
prints the per-layer gap ||d_l|| so the dose can be swept against the server.
"""

import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import metric

# Concepts to "hold in mind" (none are association targets) and neutral carrier sentences.
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

# Instruction wordings that vary across pairs, like the paper's directed_modulation instructions.
THINK = [
    "Think about {c} while you write. Now write exactly this sentence:",
    "Keep {c} in your thoughts as you write. Now write exactly this sentence:",
    "Hold {c} in mind while you write. Now write exactly this sentence:",
    "As you write the next sentence, stay focused on {c}:",
]
DONT = [
    "Do not think about {c} while you write. Now write exactly this sentence:",
    "Keep {c} out of your thoughts as you write. Now write exactly this sentence:",
    "Do not hold {c} in mind while you write. Now write exactly this sentence:",
    "As you write the next sentence, push {c} from your mind:",
]

HELD_OUT_MSG = "keep_{c}_in_mind"


def pairs():
    out = []
    n = min(len(CONCEPTS), len(CARRIERS))
    for i in range(n):
        think = f"{THINK[i % len(THINK)].format(c=CONCEPTS[i])} \"{CARRIERS[i]}\""
        dont = f"{DONT[i % len(DONT)].format(c=CONCEPTS[i])} \"{CARRIERS[i]}\""
        out.append((think, dont, CARRIERS[i]))
    return out


def main():
    layers = list(range(14, 31))  # wide band so I can pick later
    ps = pairs()
    think_spec = {"layers": layers, "positions": "assistant",
                  "prompts": [{"user": t, "assistant": c} for t, _, c in ps]}
    dont_spec = {"layers": layers, "positions": "assistant",
                 "prompts": [{"user": d, "assistant": c} for _, d, c in ps]}
    print(f"{len(ps)} pairs, layers {layers}", file=sys.stderr)
    think = metric.capture(think_spec)
    dont = metric.capture(dont_spec)
    u = {}
    print("layer  ||d_l||")
    for L in layers:
        d = (think["mean"][L] - dont["mean"][L]).float()
        nrm = d.norm().item()
        print(f"{L:5d}  {nrm:8.4f}")
        u[L] = d / d.norm()
    torch.save(u, "work/wb_u.pt")
    print("saved work/wb_u.pt", file=sys.stderr)


if __name__ == "__main__":
    main()