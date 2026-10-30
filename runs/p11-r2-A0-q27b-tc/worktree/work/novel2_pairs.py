"""Carrier-based novel contrasts (jlens-steer-assoc-017).

Unlike the first attempt (read a single template-marker token), each condition here has the model
*write* the same description as its assistant turn, and we read the generated description cells
(the carrier), exactly as WBS reads its carrier. Within a contrast the description is identical in
both conditions, so only the processing mode survives the difference.

The carrier is a description that implies a single concept (association-like, written here -- not
the fit items). Three modes, each distinct from WBS's "hold an *unrelated* concept X while copying":

  namer    -- keep the *word that names it* as the live prediction while writing (self-referential).
  gist     -- attend top-down to what the sentence is *about* while writing.
  imagery  -- generate *vivid mental imagery* of it while writing.
All are contrasted with plain mechanical transcription of the same sentence.
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

_CONTROL = "Write the following sentence exactly as given, word for word: \"{d}\""


def _pair(a_template: str) -> tuple[list[dict], list[dict]]:
    a, b = [], []
    for d in DESCS:
        a.append({"user": a_template.format(d=d), "assistant": d})
        b.append({"user": _CONTROL.format(d=d), "assistant": d})
    return a, b


def namer():
    return _pair("As you write the following sentence, keep in mind the single word that names it, ready to say it: \"{d}\"")


def gist():
    return _pair("As you write the following sentence, hold in mind the single thing it is really about: \"{d}\"")


def imagery():
    return _pair("As you write the following sentence, picture it vividly in your mind's eye: \"{d}\"")
