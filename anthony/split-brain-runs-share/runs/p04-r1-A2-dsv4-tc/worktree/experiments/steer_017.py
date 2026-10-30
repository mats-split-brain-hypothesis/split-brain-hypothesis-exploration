"""Build and score steering directions for task jlens-steer-assoc-017.

Contrast directions only (mean of condition A minus mean of condition B), captured through
the metric server's /capture endpoint. The association targets are never used; conditions are
our own prompts or other families' fit items.
"""
import json, sys, time
from pathlib import Path
import torch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import metric

L_READ = [26, 28, 30]

ANSWER_PROMPTS = [
    "What is the capital of France? Answer in one word.",
    "What is 7 multiplied by 8? Answer with a number.",
    "What do you call a baby cat? One word.",
    "Which planet is closest to the Sun? One word.",
    "What colour is a ripe banana? One word.",
    "How many legs does a spider have? A number.",
    "What is the opposite of 'hot'? One word.",
    "What is water called when it freezes? One word.",
    "What food do bees make? One word.",
    "What instrument has 88 keys? One word.",
    "What is the largest ocean? One word.",
    "What do you call a young dog? One word.",
    "What is the chemical symbol for gold? One token.",
    "How many days are in a week? A number.",
    "What is the square root of 144? A number.",
    "What do birds use to fly? One word.",
    "What is the currency of Japan? One word.",
    "What is the tallest animal in the world? One word.",
    "What does a chef use to cut vegetables? One word.",
    "What is the colour of fresh snow? One word.",
    "What do you call a group of lions? One word.",
    "What is the fastest land animal? One word.",
    "What is the main ingredient in bread? One word.",
    "What do astronauts travel in? One word.",
    "What is the longest river in the world? One word.",
    "What do you use to write on a blackboard? One word.",
    "What is a vehicle with two wheels called? One word.",
    "What is the name of Earth's natural satellite? One word.",
    "What do bees produce that is sweet? One word.",
    "What season comes after winter? One word.",
    "What do you call the study of stars? One word.",
    "What do you wear on your feet? One word.",
    "What is a place where books are kept? One word.",
    "What is the opposite of 'big'? One word.",
    "How many continents are there? A number.",
    "What do doctors use to listen to your heart? One word.",
    "What is a common breakfast drink? One word.",
    "What do you call a person who flies a plane? One word.",
    "What covers most of the Earth's surface? One word.",
    "What do fish use to breathe? One word.",
]

CONTINUE_PROMPTS = [
    "Complete the sentence: the sun rises in the",
    "Complete the sentence: she opened the door and saw",
    "The history of the Roman Empire began when",
    "Yesterday I went to the market and bought",
    "Once upon a time there was a",
    "The recipe for bread starts by mixing",
    "In the morning I usually",
    "The weather today is",
    "My favourite thing about the city is",
    "The scientist explained that",
    "A bicycle works by",
    "The mountain was covered in",
    "We decided to go to the beach because",
    "The old man told a story about",
    "The company's profits grew after",
    "Children learn to read by",
    "The river flows from",
    "A good friend is someone who",
    "The movie was about",
    "During the festival people",
    "The secret to happiness is",
    "Computers process information by",
    "The garden smelled of",
    "He felt nervous before",
    "The team won because",
    "The teacher asked the class to",
    "The forest at night is",
    "My grandmother used to say",
    "The train leaves the station at",
    "To bake a cake you need",
    "The city was founded in",
    "The reason I write is",
    "A healthy breakfast includes",
    "The song we heard was",
    "Rainy days always make me",
    "The problem with the plan was",
    "The students decided to",
    "The painter mixed blue and",
    "Birds migrate south when",
    "The bridge connects the two",
]


def capture(prompts, positions="user", layers=L_READ, tag="capture"):
    t0 = time.time()
    spec = {"layers": layers, "prompts": [{"user": p} for p in prompts], "positions": positions}
    out = metric.capture(spec)
    print(f"[{tag}] n={out['n_prompts']} pos={positions} layers={out['layers']} {time.time()-t0:.1f}s", flush=True)
    return out["mean"], out


def main():
    # Capture the two conditions
    mean_a, _ = capture(ANSWER_PROMPTS, "user", L_READ, "answer")
    mean_b, _ = capture(CONTINUE_PROMPTS, "user", L_READ, "continue")
    vecs = {}
    for L in L_READ:
        v = mean_a[L] - mean_b[L]
        vecs[L] = v
        print(f"L{L}: ||A||={float(mean_a[L].norm()):.2f} ||B||={float(mean_b[L].norm()):.2f} ||v||={float(v.norm()):.2f}")
    torch.save(vecs, "out/steer/answer_minus_continue.pt")
    print("saved out/steer/answer_minus_continue.pt")

if __name__ == "__main__":
    main()
