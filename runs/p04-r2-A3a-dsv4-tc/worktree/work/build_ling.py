"""C1: a purely linguistic "concurrency vs sequence" contrast, motivated by the observation that
the working stance direction reads as "while / meanwhile / despite" under the J-lens. Same
sentence, only the temporal connector differs (While/As vs After/Once), so the direction isolates
concurrent vs sequential event structure with no instruction, no concept and no stance wording.
"""

import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import metric

CONCURRENT = [
    "While the kettle boiled, she set the table.",
    "As the rain fell, he finished the letter.",
    "While the music played, they cleared the hall.",
    "As the bread baked, she watered the plants.",
    "While the printer hummed, he sorted the pages.",
    "As the film ran, the audience stayed silent.",
    "While the soup simmered, she chopped the herbs.",
    "As the train slowed, he gathered his bags.",
    "While the fire crackled, they read aloud.",
    "As the tide climbed, the children built a wall.",
    "While the lecture droned, she sketched in the margin.",
    "As the plane descended, he fastened his belt.",
    "While the clock ticked, she counted backwards.",
    "As the snow settled, the roads turned white.",
    "While the choir rehearsed, he tuned the organ.",
    "As the engine idled, the driver checked the map.",
    "While the tea steeped, she unfolded the newspaper.",
    "As the crowd cheered, the runner crossed the line.",
    "While the paint dried, he washed the brushes.",
    "As the night deepened, the crickets grew louder.",
    "While the dough rose, she set out the filling.",
    "As the storm gathered, they nailed the shutters.",
    "While the guests arrived, she lit the candles.",
    "As the computer updated, he filed the invoices.",
    "While the stew cooled, she sliced the bread.",
    "As the dog barked, the postman retreated.",
    "While the debate raged, he took careful notes.",
    "As the ice melted, the river rose an inch.",
    "While the kettle whistled, he rinsed the cups.",
    "As the match burned, she touched it to the wick.",
    "While the phone rang, he covered his ears.",
    "As the chapter ended, she closed the book.",
]

SEQUENTIAL = [
    "After the kettle boiled, she set the table.",
    "Once the rain fell, he finished the letter.",
    "After the music played, they cleared the hall.",
    "Once the bread baked, she watered the plants.",
    "After the printer hummed, he sorted the pages.",
    "Once the film ran, the audience stayed silent.",
    "After the soup simmered, she chopped the herbs.",
    "Once the train slowed, he gathered his bags.",
    "After the fire crackled, they read aloud.",
    "Once the tide climbed, the children built a wall.",
    "After the lecture droned, she sketched in the margin.",
    "Once the plane descended, he fastened his belt.",
    "After the clock ticked, she counted backwards.",
    "Once the snow settled, the roads turned white.",
    "After the choir rehearsed, he tuned the organ.",
    "Once the engine idled, the driver checked the map.",
    "After the tea steeped, she unfolded the newspaper.",
    "Once the crowd cheered, the runner crossed the line.",
    "After the paint dried, he washed the brushes.",
    "Once the night deepened, the crickets grew louder.",
    "After the dough rose, she set out the filling.",
    "Once the storm gathered, they nailed the shutters.",
    "After the guests arrived, she lit the candles.",
    "Once the computer updated, he filed the invoices.",
    "After the stew cooled, she sliced the bread.",
    "Once the dog barked, the postman retreated.",
    "After the debate raged, he took careful notes.",
    "Once the ice melted, the river rose an inch.",
    "After the kettle whistled, he rinsed the cups.",
    "Once the match burned, she touched it to the wick.",
    "After the phone rang, he covered his ears.",
    "Once the chapter ended, she closed the book.",
]

LAYERS = list(range(14, 31))


def main():
    out = {}
    for tag, prompts in [("pos", CONCURRENT), ("neg", SEQUENTIAL)]:
        r = metric.capture({"layers": LAYERS, "positions": "last",
                            "prompts": [{"user": p, "assistant": ""} for p in prompts]})
        out[tag] = r["mean"]
        print(f"[C1] {tag}: {r['n_prompts']} prompts", file=sys.stderr)
    u = {}
    print("layer  ||d_l||")
    for L in LAYERS:
        d = (out["pos"][L] - out["neg"][L]).float()
        nrm = d.norm().item()
        print(f"{L:5d}  {nrm:8.4f}")
        u[L] = d / d.norm()
    torch.save({L: u[L] for L in [20, 21, 22, 23, 24]}, "work/C1_band.pt")
    torch.save(u, "work/C1_u.pt")
    print("saved work/C1_band.pt", file=sys.stderr)


if __name__ == "__main__":
    main()