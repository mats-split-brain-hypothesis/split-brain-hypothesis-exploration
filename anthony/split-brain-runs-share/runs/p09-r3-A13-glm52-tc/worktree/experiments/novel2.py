"""More candidate contrasts at L20-24."""
from contrasts2 import _A_PASSAGES, _B_PASSAGES

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

# S1: remember/forget stance (different wording from think/don't-think)
def s1_remember_forget():
    A, B = [], []
    for i, c in enumerate(_CONCEPTS):
        car = _CARRIERS[i % len(_CARRIERS)]
        A.append({"user": f"Remember the object {c} while you write. Now write exactly this sentence: \"{car}\"", "assistant": car})
        B.append({"user": f"Try to forget the object {c} while you write. Now write exactly this sentence: \"{car}\"", "assistant": car})
    return A, B

# S2: focus/ignore stance
def s2_focus_ignore():
    A, B = [], []
    for i, c in enumerate(_CONCEPTS):
        car = _CARRIERS[i % len(_CARRIERS)]
        A.append({"user": f"Focus on the object {c} while you write. Now write exactly this sentence: \"{car}\"", "assistant": car})
        B.append({"user": f"Ignore the object {c} while you write. Now write exactly this sentence: \"{car}\"", "assistant": car})
    return A, B

# C1: concurrent vs sequential conjunction (token contrast)
def c1_concurrent_sequential():
    A, B = [], []
    pairs = [("She hummed a tune", " she folded the laundry."),
             ("He drank his coffee", " he read the report."),
             ("The children played outside", " their parents chatted inside."),
             ("She typed the email", " she ate her lunch."),
             ("He whistled softly", " he walked the dog."),
             ("The rain fell steadily", " the wind shook the trees."),
             ("She sorted the papers", " she explained the process."),
             ("He polished the glass", " he described the exhibit."),
             ("They sang together", " they walked home."),
             ("The cat purred", " it watched the birds.")]
    seqpairs = [("She hummed a tune", " then she folded the laundry."),
                ("He drank his coffee", " then he read the report."),
                ("The children played outside", " then their parents called them in."),
                ("She typed the email", " then she ate her lunch."),
                ("He whistled softly", " then he walked the dog."),
                ("The rain fell steadily", " then the wind picked up."),
                ("She sorted the papers", " then she explained the process."),
                ("He polished the glass", " then he described the exhibit."),
                ("They sang together", " then they walked home."),
                ("The cat purred", " then it watched the birds.")]
    for a, b in pairs:
        A.append({"user": "Continue the sentence naturally.", "assistant": a + " while" + b})
    for a, b in seqpairs:
        B.append({"user": "Continue the sentence naturally.", "assistant": a + b})
    return A, B

# P1: descriptive vs generic passage at L20-24 (retry at right band)
def p1_passage():
    A = [{"user": p, "assistant": ""} for p in _A_PASSAGES]
    B = [{"user": p, "assistant": ""} for p in _B_PASSAGES]
    return A, B
