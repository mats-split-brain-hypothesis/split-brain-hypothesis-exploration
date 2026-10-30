"""Novel contrast pairs for jlens-steer-assoc-017.

Each description implies a single concept without naming it (association-like), but the
descriptions are written here, from scratch -- they are not the fit items and their implied
concepts are not the fit targets. Within a contrast the SAME description appears in both
conditions, so the content cancels and only the processing mode survives.

Two candidates, each distinct from WBS (Raman 2026) "think about X while you copy" (a *side
stance* imposed on a carrier task):

  namer   -- the model's MAIN task is to name/identify (a task-role contrast).
  gist    -- the model aims top-down at the gestalt vs. bottom-up at the details (an
             attention-allocation contrast).
"""

# (description). The implied concept is whatever it is; it is matched within each contrast.
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


def namer() -> tuple[list[dict], list[dict]]:
    """A: model's task is to NAME the implied thing. B: model just continues passively."""
    a, b = [], []
    for d in DESCS:
        a.append({"user": f"What single word names what this describes? {d} Answer in one word:",
                  "assistant": ""})
        b.append({"user": f"{d}", "assistant": ""})
    return a, b


def gist() -> tuple[list[dict], list[dict]]:
    """A: aim top-down at the single thing it's about. B: take it in detail-by-detail."""
    a, b = [], []
    for d in DESCS:
        a.append({"user": f"Read this, and hold in mind the single thing it is really about. {d}",
                  "assistant": ""})
        b.append({"user": f"Read this one detail at a time, without trying to sum it up. {d}",
                  "assistant": ""})
    return a, b
