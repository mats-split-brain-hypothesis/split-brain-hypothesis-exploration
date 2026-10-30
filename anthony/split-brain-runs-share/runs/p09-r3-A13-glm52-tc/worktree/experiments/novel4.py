"""Engagement vs distractor (dual-task) contrasts — B is a distractor, not suppression."""
from novel2 import _CONCEPTS, _CARRIERS

# D1: vivid imagery vs count-the-words (distractor B)
def d1_imagery_count():
    A, B = [], []
    for i, c in enumerate(_CONCEPTS):
        car = _CARRIERS[i % len(_CARRIERS)]
        A.append({"user": f"Form a vivid mental image of the object {c} while you write. Now write exactly this sentence: \"{car}\"", "assistant": car})
        B.append({"user": f"Count the words in this sentence as you write it: \"{car}\"", "assistant": car})
    return A, B

# D2: think-about vs count-words (engage vs distractor, no suppression wording)
def d2_think_count():
    A, B = [], []
    for i, c in enumerate(_CONCEPTS):
        car = _CARRIERS[i % len(_CARRIERS)]
        A.append({"user": f"Keep the object {c} in your thoughts while you write. Now write exactly this sentence: \"{car}\"", "assistant": car})
        B.append({"user": f"Count the words in this sentence as you write it: \"{car}\"", "assistant": car})
    return A, B

# D3: imagery vs neutral-analyze (engage vs surface-analyze, no suppression)
def d3_imagery_analyze():
    A, B = [], []
    for i, c in enumerate(_CONCEPTS):
        car = _CARRIERS[i % len(_CARRIERS)]
        A.append({"user": f"Form a vivid mental image of the object {c} while you write. Now write exactly this sentence: \"{car}\"", "assistant": car})
        B.append({"user": f"Analyze the grammar of this sentence as you write it: \"{car}\"", "assistant": car})
    return A, B
