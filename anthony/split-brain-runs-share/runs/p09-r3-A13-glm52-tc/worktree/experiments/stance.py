"""Self-authored think/don't-think stance pairs (SANITY CHECK of the L20-24 band mechanism).

Not the directed_modulation family; my own generic concepts and carrier sentences.
Used only to calibrate band/dose/positions before building the novel method.
"""
_CONCEPTS = ["compass", "harbor", "anvil", "lantern", "ribbon", "saddle", "biscuit",
             "pillow", "tunnel", "meadow", "castle", "boulder", "thunder", "blanket",
             "candle", "forest", "kettle", "trowel", "chisel", "whisk"]
_CARRIERS = [
    "The committee approved the minutes without changes.",
    "A small bird landed on the fence post at dawn.",
    "She filed the documents in the third cabinet.",
    "The train arrived four minutes later than scheduled.",
    "He folded the letter and placed it in the drawer.",
    "They walked along the canal toward the bridge.",
    "The cashier counted the change twice, carefully.",
    "A thin rain began to fall just after noon.",
    "She opened the window to let in some air.",
    "The lecture ran over by ten full minutes.",
    "He turned the key and the engine started at once.",
    "They set the table for six guests that evening.",
    "The drawer stuck until she gave it a sharp tug.",
    "A long queue formed outside the small bakery.",
    "She watered the plant and wiped the shelf.",
    "The boat rocked gently at its mooring.",
    "He signed the form at the bottom line.",
    "They took the narrow path behind the barn.",
    "The lamp flickered once, then held steady.",
    "She swept the step and shook out the mat.",
]

def stance_prompts():
    A, B = [], []
    for i, c in enumerate(_CONCEPTS):
        carrier = _CARRIERS[i % len(_CARRIERS)]
        A.append({"user": f"Think about the object {c} while you write. Now write exactly this sentence: \"{carrier}\"",
                  "assistant": carrier})
        B.append({"user": f"Do not think about the object {c} while you write. Now write exactly this sentence: \"{carrier}\"",
                  "assistant": carrier})
    return A, B
