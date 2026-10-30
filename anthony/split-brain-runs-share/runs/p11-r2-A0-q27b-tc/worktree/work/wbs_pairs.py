"""White-bear (WBS, Raman 2026) contrast pairs, for harness validation / dose calibration only.

NOT the submission. Each pair matches the concept and the carrier sentence between the think and
don't-think conditions, so only the stance survives the difference.
"""

# (concept, carrier). Carrier is a neutral sentence the model copies; concept is what it holds / suppresses.
PAIRS = [
    ("the body part clavicle", "The committee approved the minutes without changes."),
    ("the chess piece bishop", "Rain tapped the window of the small station restaurant."),
    ("the musical instrument oboe", "We parked the van behind the old stone warehouse."),
    ("the fruit quince", "The ferry left the dock on the half hour, as always."),
    ("the sport lacrosse", "Two cups of coffee sat cooling on the desk."),
    ("the bird kingfisher", "The bus turned onto the long coastal road."),
    ("the mineral garnet", "She set the kettle on and opened a notebook."),
    ("the dance tango", "The children ran out across the green field."),
    ("the flower delphinium", "He folded the map and checked the time on his watch."),
    ("the tool mallet", "The cat climbed the fence and disappeared."),
    ("the insect mantis", "We ordered two sandwiches and a bottle of water."),
    ("the metal bismuth", "The train slowed as it approached the station."),
    ("the vegetable kohlrabi", "She hung her coat by the door and sat down."),
    ("the game squash", "The streetlights came on one by one in the dark."),
    ("the animal lemur", "He measured the length twice before making the cut."),
    ("the instrument marimba", "The garden was quiet after the afternoon rain."),
]


def prompts(stance: str) -> list[dict]:
    """stance in {'think', 'dont'} -> list of {user, assistant} prompts."""
    out = []
    for concept, carrier in PAIRS:
        if stance == "think":
            user = f"Think about {concept} while you write. Now write exactly this sentence: \"{carrier}\""
        else:
            user = f"Do not think about {concept} while you write. Now write exactly this sentence: \"{carrier}\""
        out.append({"user": user, "assistant": carrier})
    return out
