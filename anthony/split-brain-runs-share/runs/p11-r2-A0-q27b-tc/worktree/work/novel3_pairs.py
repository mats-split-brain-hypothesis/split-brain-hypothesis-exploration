"""Content-free dual-task contrasts with *unrelated* concurrent loads (jlens-steer-assoc-017).

WBS holds an unrelated *concept* X while copying. These hold unrelated loads of a *different
kind*, so the specific load content cancels across pairs (each load is varied) and only the
dual-task / simultaneous-attention mode survives. All read the generated carrier (the
description D), content-matched with a plain-transcription control.
"""

DESCS = [
    "She swung the club, and the tiny white ball sailed toward the green.",
    "The dough rose all night, and by morning the crust crackled in the oven.",
    "He clipped the wire, and the red and black leads stood apart.",
    "The tide pulled back, leaving the shells glittering in the wet sand.",
    "She strummed the strings, and the chord filled the small room.",
    "The kettle whistled, and she poured the water over the grounds.",
    "He laced his skates and pushed hard off the blue line.",
    "The petals unfurled each morning, drawn up toward the sun.",
    "She measured the fabric, pinned it, and sent the seam through.",
    "The engine coughed, then caught, and the little plane lifted off.",
    "He chiselled the stone, and the figure of the horse emerged.",
    "The sauce simmered, and garlic and tomato filled the kitchen.",
    "She stretched, inhaled, and held the pose on the mat.",
    "The needles sank into the wool, row after steady row.",
]

# Unrelated sentences for the dual-stream load (varied, so their content cancels).
LOADS = [
    "The train left the station on time.",
    "We bought two loaves of bread.",
    "The meeting moved to Thursday.",
    "A dog crossed the street slowly.",
    "She locked the front door.",
    "The price of coffee went up.",
    "He found his keys in the coat.",
    "The library closes at six.",
    "It rained all through the night.",
    "The bus was full of people.",
    "She watered the plants on the sill.",
    "The game ended in a draw.",
    "He polished his old boots.",
    "The shop opened late this year.",
]

_CONTROL = "Write exactly this sentence: \"{d}\""


def dualstream():
    """A: hold an unrelated sentence in mind while writing D (dual-stream working memory)."""
    a, b = [], []
    for d, s1 in zip(DESCS, LOADS):
        a.append({"user": f"Hold this sentence in your mind as you write the next one: \"{s1}\" "
                          f"Now write exactly this sentence: \"{d}\"", "assistant": d})
        b.append({"user": _CONTROL.format(d=d), "assistant": d})
    return a, b


def rhythm():
    """A: write D with a steady, felt rhythm (prosodic/motor dual-task)."""
    a, b = [], []
    for d in DESCS:
        a.append({"user": f"Write this sentence with a steady, even rhythm, feeling the beat of each word: \"{d}\"",
                  "assistant": d})
        b.append({"user": _CONTROL.format(d=d), "assistant": d})
    return a, b
