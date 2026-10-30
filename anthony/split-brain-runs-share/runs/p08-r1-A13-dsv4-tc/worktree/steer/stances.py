"""(concept, carrier) pairs and stance templates for carrier-cell contrasts.

The concept is a concrete noun (in the think/don't-think or hold/forget instruction), never the
evaluation target; the carrier is a neutral unrelated sentence the model copies verbatim.
"""
CARRIERS = [
    "The committee approved the minutes without changes.",
    "The invoice total appears on the second page.",
    "She unlocked the door and set her keys on the table.",
    "The train arrived eight minutes behind schedule.",
    "He folded the letter and slid it into the drawer.",
    "The garden will be open to visitors on Sunday.",
    "A small dog crossed the empty street at dawn.",
    "The librarian returned the book to its shelf.",
    "They ordered two coffees and a slice of cake.",
    "The forecast calls for rain by late afternoon.",
    "Her phone buzzed once and then fell silent.",
    "The board voted to postpone the decision.",
    "He noted the address in a small notebook.",
    "The kettle began to whistle in the kitchen.",
    "A stranger asked for directions at the corner.",
    "The curtain drifted in the morning breeze.",
    "She measured the flour and set it aside.",
    "The meeting ended with a firm handshake.",
    "He walked the dog along the river path.",
    "The engine hummed steadily on the open road.",
]

CONCEPTS = [
    "clavicle", "bishop", "harp", "monsoon", "isthmus", "ozone", "kestrel", "fjord",
    "cantilever", "parabola", "mirage", "tarantula", "obelisk", "estuary", "tessellation",
    "sonnet", "baritone", "zircon", "pendulum", "geyser", "stalactite", "nebula",
    "orchard", "kaleidoscope", "marimba", "trellis", "undertow", "zephyr", "topaz",
    "lichen", "heron", "aqueduct", "cathedral", "origami", "volcano", "tundra",
    "lighthouse", "amphora", "fresco", "xylophone",
]

def think_pairs():
    return [{"concept": c, "carrier": CARRIERS[i % len(CARRIERS)]} for i, c in enumerate(CONCEPTS)]


# --- WBS-style think / don't-think, for pipeline calibration (NOT the submission) ---
WBS_POS = "Think about the {concept} while you write. Now write exactly this sentence: \"{carrier}\""
WBS_NEG = "Do not think about the {concept} while you write. Now write exactly this sentence: \"{carrier}\""

# --- novel candidate: hold-in-memory / discard (memory maintenance stance) ---
HOLD_POS = "Hold the word {concept} in memory as you write. Now write exactly this sentence: \"{carrier}\""
HOLD_NEG = "Erase the word {concept} from memory before you write. Now write exactly this sentence: \"{carrier}\""

# --- novel candidate: there-is-an-implication / no-implication (implicature stance) ---
IMPLY_POS = "The thing you just read implies a single hidden word; keep that hidden word in mind as you write this sentence: \"{carrier}\""
IMPLY_NEG = "The thing you just read implies nothing; forget any hidden meaning and write this sentence plainly: \"{carrier}\""

print(len(think_pairs()), "carrier pairs")

# novel candidates on carrier cells (tested below):
HOLD_POS = "Hold the word {concept} in memory while you write. Now write exactly this sentence: \"{carrier}\""
HOLD_NEG = "Erase the word {concept} from memory before you write. Now write exactly this sentence: \"{carrier}\""

BLANK_POS = "Keep one unspoken thought quietly in mind as you write. Now write exactly this sentence: \"{carrier}\""
BLANK_NEG = "Keep your mind entirely blank, with no unspoken thought, as you write. Now write exactly this sentence: \"{carrier}\""

MEAN_POS = "Write this sentence as if it quietly points to something beyond its words: \"{carrier}\""
MEAN_NEG = "Write this sentence as if it points to nothing beyond its words: \"{carrier}\""

SECRET_POS = "Keep a secret that you will not say as you write this sentence: \"{carrier}\""
SECRET_NEG = "Keep nothing hidden as you write this sentence: \"{carrier}\""

CARRIERS_MORE = [
    "The concierge handed over a folded map of the old town.",
    "He poured the last of the coffee into a waiting mug.",
    "A jogger passed beneath the window just after dawn.",
    "The chef wiped the counter and checked the reservations list.",
    "She pinned the receipt to the corkboard with a brass tack.",
    "The ferry crossed the harbour in the pale morning light.",
    "He tightened the rusty bolt and stood back to inspect it.",
    "The children lined their shoes by the door before bed.",
    "A van idled at the kerb with its hazards blinking.",
    "She restacked the books so the spines faced the room.",
    "The dog pricked its ears at a sound beyond the hedge.",
    "He signed both copies and slid one across the desk.",
    "The kettle was still warm from the last pot of tea.",
    "Pedestrians stopped to watch the crew hoist the banner.",
    "She adjusted the tripod and framed the shot in silence.",
    "The ledger lay open to a page of faded blue ink.",
    "He scraped the frost from the windscreen with a card.",
    "A moth circled the lamp and settled on the shade.",
    "The nurse pulled the curtain around the empty bed.",
    "He left the keys on the sill and locked the door behind him.",
]


def carriers_full():
    return CARRIERS + CARRIERS_MORE


def pairs_full():  # 40 distinct (concept, carrier) pairs
    out = []
    for i, c in enumerate(CONCEPTS):
        out.append({"concept": c, "carrier": (CARRIERS + CARRIERS_MORE)[i % len(CARRIERS + CARRIERS_MORE)]})
    return out

print(len(carriers_full()), "total carriers")
