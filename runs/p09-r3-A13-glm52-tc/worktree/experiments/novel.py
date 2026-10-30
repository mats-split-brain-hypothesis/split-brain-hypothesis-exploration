"""Novel contrast prompts (content / mode based, NOT think/don't-think stance).

All use my own descriptive passages of generic concepts (not association targets).
Designed to induce 'active concept retrieval / development' vs surface processing,
sharing the read-position content where possible (Raman's clean-contrast trick).
"""
from contrasts2 import _A_PASSAGES  # reuse my descriptive passages

# Contrast N1: identify-the-concept vs read-aloud (mode contrast, shared assistant passage).
def n1_identify_vs_read():
    A, B = [], []
    for p in _A_PASSAGES:
        A.append({"user": f"What concept does this sentence illustrate? \"{p}\"",
                  "assistant": p})
        B.append({"user": f"Read this sentence aloud, word for word. \"{p}\"",
                  "assistant": p})
    return A, B

# Contrast N2: name-the-concept vs continue-narrative (cue contrast at last token).
def n2_name_vs_continue():
    A, B = [], []
    for p in _A_PASSAGES:
        A.append({"user": p, "assistant": "This is an example of"})
        B.append({"user": p, "assistant": "And then"})
    return A, B

# Contrast N3: infer-theme vs describe-surface (mode, shared assistant).
def n3_infer_vs_describe():
    A, B = [], []
    for p in _A_PASSAGES:
        A.append({"user": f"Identify the underlying activity in this scene: \"{p}\"",
                  "assistant": p})
        B.append({"user": f"Describe the surface actions in this scene: \"{p}\"",
                  "assistant": p})
    return A, B

# Contrast N4: answer-a-definition vs repeat-a-definition (retrieval vs copy, shared def).
_DEFS = [
    "A game where a shuttlecock is hit over a net with rackets.",
    "A vehicle with two wheels and pedals.",
    "A yellow citrus fruit that is very sour.",
    "A building where books are kept for borrowing.",
    "A tool with a handle and metal head used for hitting nails.",
    "A color made by mixing blue and yellow.",
    "A common pet that says meow and chases mice.",
    "A piece of furniture with a flat top and legs.",
    "A season when leaves fall and the weather cools.",
    "A white liquid produced by mammals.",
    "A large body of water surrounded by land.",
    "A hard clear stone used in jewelry.",
    "A machine that keeps food cold.",
    "A planet we live on.",
    "A person who treats sick people.",
    "A fruit that is red or green and grows on trees.",
    "A shape with three straight sides and three angles.",
    "A metal that is liquid at room temperature.",
    "A long narrow piece of wood used in building.",
    "A small round green seed eaten as a vegetable.",
]
def n4_answer_vs_repeat():
    A, B = [], []
    for d in _DEFS:
        A.append({"user": f"Answer this question: {d}", "assistant": "The answer is"})
        B.append({"user": f"Repeat this definition: {d}", "assistant": "The answer is"})
    return A, B
