import json, sys, torch
sys.path.insert(0, '/home/anthony/j-lens-mean/tools')
import metric

LAYERS = [26, 28, 30]
# Neutral prose sentences (complete).  NEG = full sentence ending in "."
SENTS = [
    "The sun was setting over the calm water",
    "She placed the book back on the wooden shelf",
    "The train arrived at the station a few minutes late",
    "He poured a cup of coffee and sat at the table",
    "The leaves rustled softly in the afternoon breeze",
    "A small dog ran across the empty street",
    "They walked along the path beside the river",
    "The clock on the wall struck noon",
    "She opened the window to let in fresh air",
    "The children played quietly in the corner",
    "Rain began to fall gently on the tin roof",
    "He turned the page and continued reading",
    "The shop on the corner had just closed",
    "A bird landed on the fence and watched",
    "The meeting ended a little after four o'clock",
    "Dinner was served at the long oak table",
    "She folded the letter and put it away",
    "The road stretched out across the valley",
    "He checked his watch and quickened his pace",
    "The flowers bloomed early that spring",
    "A crowd gathered outside the old theater",
    "The kettle began to whistle on the stove",
    "She smiled and closed her eyes",
    "The wind picked up as the storm approached",
    "He straightened his tie in the mirror",
    "The cat curled up by the warm fire",
    "They packed their bags and left the hotel",
    "The paint was still wet on the wall",
    "She hummed a tune while she worked",
    "The boat drifted toward the far shore",
    "He lit the candle on the table",
    "The snow covered the empty field",
    "She kept the change in a small jar",
    "The music faded as the night went on",
    "He wrote his name at the top of the page",
    "The city lights came on at dusk",
    "She tightened her scarf against the cold",
    "The horses grazed near the old barn",
    "He turned off the engine and stepped out",
    "The path led down to the quiet lake",
]

def cap(prompts):
    return metric.capture({'layers': LAYERS, 'prompts': [{'user': p, 'assistant': ''} for p in prompts], 'positions': 'last'})

# NEG: sentence-final (with period).  POS: mid-sentence (strip last word, no period).
neg_prompts = [s + "." for s in SENTS]
pos_prompts = []

def strip_last_word(s):
    w = s.rsplit(" ", 1)
    if len(w) == 2 and len(w[1]) > 1:
        return w[0]
    return s.rsplit(" ", 1)[0]

pos_prompts = [strip_last_word(s) for s in SENTS]

neg = cap(neg_prompts)
pos = cap(pos_prompts)
v = {L: pos['mean'][L] - neg['mean'][L] for L in LAYERS}
torch.save({'pos': pos, 'neg': neg, 'v': v, 'pos_prompts': pos_prompts, 'neg_prompts': neg_prompts}, 'scratch/c2.pt')
for L in LAYERS:
    print(f'L{L}: mid norm {float(pos["mean"][L].norm()):.2f} final norm {float(neg["mean"][L].norm()):.2f} v norm {float(v[L].norm()):.2f}')
print('example pos prompt:', pos_prompts[0], '| neg:', neg_prompts[0])
