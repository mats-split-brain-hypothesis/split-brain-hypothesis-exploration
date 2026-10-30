"""Build contrast vectors and test them on the metric server."""
import json, sys, time, torch
sys.path.insert(0, '/home/anthony/j-lens-mean/tools')
import metric

LAYERS = [26, 28, 30]

POS = [
    "Answer in one word.",
    "In one word, name the activity described.",
    "State the concept in one word.",
    "One-word answer.",
    "What is this called? Answer:",
    "Name it in one word.",
    "Give the single word this describes:",
    "The one-word label for the situation is:",
    "Respond with a single noun:",
    "In a single word, what is happening here?",
    "Finish with the one word that names this:",
    "The correct one-word answer is:",
    "Say the category in one word.",
    "Which single concept does this evoke? Answer:",
    "Express the idea in one word:",
]

NEG = [
    "The sun was setting over the calm, quiet water.",
    "She placed the book back on the wooden shelf.",
    "The train arrived at the station a few minutes late.",
    "He poured a cup of coffee and sat down at the table.",
    "The leaves rustled softly in the afternoon breeze.",
    "A small dog ran across the empty street.",
    "They walked along the path beside the river.",
    "The clock on the wall struck noon.",
    "She opened the window to let in some fresh air.",
    "The children played quietly in the corner of the room.",
    "Rain began to fall gently on the tin roof.",
    "He turned the page and continued reading.",
    "The shop on the corner had just closed.",
    "A bird landed on the fence and watched.",
    "The meeting ended a little after four o'clock.",
]

def cap(prompts, positions='last'):
    return metric.capture({'layers': LAYERS, 'prompts': [{'user': p, 'assistant': ''} for p in prompts], 'positions': positions})

def vecs(pos_mean, neg_mean):
    return {L: (pos_mean[L] - neg_mean[L]) for L in LAYERS}

if __name__ == '__main__':
    pos = cap(POS)
    neg = cap(NEG)
    v = vecs(pos['mean'], neg['mean'])
    out = {'pos': pos, 'neg': neg, 'v': {L: v[L] for L in LAYERS}}
    torch.save(out, 'scratch/c1.pt')
    for L in LAYERS:
        print(f'L{L}: pos norm {float(pos["mean"][L].norm()):.2f} neg norm {float(neg["mean"][L].norm()):.2f} v norm {float(v[L].norm()):.2f}')
    print('saved scratch/c1.pt')
