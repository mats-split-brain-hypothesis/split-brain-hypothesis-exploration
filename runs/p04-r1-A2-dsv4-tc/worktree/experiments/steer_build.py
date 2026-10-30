"""Build and score candidate steering directions (contrasts only) for task jlens-steer-assoc-017."""
import json, sys, os, time
from pathlib import Path
import torch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import metric

LAYERS = [26, 28, 30]

CONTENT_PRIME = [  # natural next token is a content word
    "The capital of France is", "The sky is", "She plays the", "The largest planet is",
    "Bees make", "A young dog is called a", "The opposite of hot is", "Water when frozen is",
    "The fastest land animal is the", "The chemical symbol for gold is", "A group of lions is a",
    "The planet closest to the sun is", "The main ingredient in bread is", "A spider has eight",
    "The longest river on Earth is the", "A place where books are kept is a", "The instrument with 88 keys is the",
    "The colour of fresh snow is", "The number of days in a week is", "A vehicle with two wheels is a",
    "The study of stars is called", "A person who flies a plane is a", "The food bees produce is",
    "The season that follows winter is", "The thing fish use to breathe is", "The currency of Japan is the",
    "The tallest animal is the", "A chef cuts vegetables with a", "What a baker bakes in is an",
    "The nearest star to Earth is the", "A doctor listens to your heart with a", "The opposite of big is",
    "The number of continents is", "The place astronauts travel to is", "The animal that says moo is a",
    "The full number of legs on a dog is", "The metal that rusts is", "The liquid we drink is",
    "The planet with rings is", "The bird that cannot fly is the", "The instrument you blow into is a",
]
FUNCTION_PRIME = [  # natural next token is a function word (determiner/preposition/pronoun)
    "She opened the door and", "The cat sat on", "He walked into", "She is looking for",
    "They talked about", "He is afraid of", "The book was on", "She gave the present to",
    "The train arrived at", "He lives in", "The answer depends on", "She poured water into",
    "The path led to", "He put the cup on", "The story was about", "He is good at",
    "She thought about", "They waited for", "He is interested in", "She leaned against",
    "The letter was addressed to", "He is responsible for", "The meeting was postponed until",
    "She is married to", "He is familiar with", "The car belonged to", "She is proud of",
    "He is capable of", "The report was written by", "She is allergic to", "He is tired of",
    "The house next to", "She is different from", "He is sure about", "The reason for",
    "She is excited about", "He is jealous of", "The distance between", "She is fond of",
    "He is opposed to",
]

def cap_prompts(name, prompts, positions="user"):
    p = Path(f"out/steer/caps/{name}.pt")
    if p.exists() and not os.environ.get("RECAP"):
        return torch.load(p, weights_only=False)
    out = metric.capture({"layers": LAYERS, "prompts": [{"user": x} for x in prompts], "positions": positions})
    p.parent.mkdir(parents=True, exist_ok=True); torch.save(out, p)
    print(f"captured {name} n={out['n_prompts']}", flush=True)
    return out

def family_mean(name):
    d = torch.load(f"out/steer/caps/{name}.pt", weights_only=False)
    return d["mean"], d["n_prompts"]

def pooled_mean(fams):
    tot = 0; acc = {L: torch.zeros(2560) for L in LAYERS}
    for f in fams:
        m, n = family_mean(f)
        for L in LAYERS: acc[L] += m[L].float() * n
        tot += n
    for L in LAYERS: acc[L] /= tot
    return acc

def build_and_score(name, A, B, scales, positions="read", sign=1.0):
    """A, B are dict {layer: tensor}. v = A - B (times sign)."""
    vecs = {L: sign * (A[L] - B[L]) for L in LAYERS}
    p = Path(f"out/steer/{name}.pt")
    torch.save({int(L): vecs[L] for L in LAYERS}, p)
    print(f"\n=== {name} (positions={positions}) ===")
    for L in LAYERS:
        print(f"  L{L} ||v||={float(vecs[L].norm()):.2f}")
    for s in scales:
        r = metric.run_metric({int(L): vecs[L] for L in LAYERS}, positions, s)
        print(f"  scale {s:+.1f}: pass@10 {r['pass_at_10']:.4f}  mean_log10_rank {r['mean_log10_rank']:.4f}  (baseline 0.1275 / 2.3277)")

if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "fam_cont"
    # condition B: clean function-continuation prompts
    B = cap_prompts("function_prime", FUNCTION_PRIME)["mean"]
    B = {L: B[L].float() for L in LAYERS}
    if which == "fam_cont":
        A = pooled_mean(["basic_readout", "typo", "multilingual", "multihop"])
        build_and_score("fam_minus_func", A, B, [1.0, 3.0, 10.0, -1.0, -3.0])
    elif which == "content_func":
        A = cap_prompts("content_prime", CONTENT_PRIME)["mean"]
        A = {L: A[L].float() for L in LAYERS}
        build_and_score("content_minus_func", A, B, [1.0, 3.0, 10.0, -1.0, -3.0])
