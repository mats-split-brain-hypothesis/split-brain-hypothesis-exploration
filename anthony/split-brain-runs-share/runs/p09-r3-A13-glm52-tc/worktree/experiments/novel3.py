"""Imagery / mental-simulation contrasts (constructive, not suppressive like WBS)."""
from novel2 import _CONCEPTS, _CARRIERS
from contrasts2 import _A_PASSAGES

# I1: visualize/picture-in-mind vs transcribe (shared carrier)
def i1_visualize_transcribe():
    A, B = [], []
    for i, c in enumerate(_CONCEPTS):
        car = _CARRIERS[i % len(_CARRIERS)]
        A.append({"user": f"Picture the object {c} vividly in your mind as you write. Now write exactly this sentence: \"{car}\"", "assistant": car})
        B.append({"user": f"Simply transcribe this sentence without thinking of anything: \"{car}\"", "assistant": car})
    return A, B

# I2: imagine-the-scene vs copy (shared descriptive carrier)
def i2_imagine_copy():
    A, B = [], []
    for i, p in enumerate(_A_PASSAGES):
        A.append({"user": f"Imagine the scene being described, then copy it exactly: \"{p}\"", "assistant": p})
        B.append({"user": f"Copy this sentence exactly, letter by letter: \"{p}\"", "assistant": p})
    return A, B

# I3: mental-simulation vs mechanical (shared carrier, minimal diff)
def i3_simulate_mechanical():
    A, B = [], []
    for i, c in enumerate(_CONCEPTS):
        car = _CARRIERS[i % len(_CARRIERS)]
        A.append({"user": f"Simulate the object {c} in your thoughts while you write. Now write exactly this sentence: \"{car}\"", "assistant": car})
        B.append({"user": f"Write exactly this sentence: \"{car}\"", "assistant": car})
    return A, B
