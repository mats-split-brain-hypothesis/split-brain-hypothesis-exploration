"""Read-cell-level contrast prompts (no association targets).

A: vivid descriptive passages ending where a concept should be named (concept-rich).
B: generic bland prose endings (concept-poor / prior-like).
Captured at the last token -> the read-cell-level residual difference.
"""

# My own descriptive passages (concepts NOT association fit targets).
_A_PASSAGES = [
    "Wheels spun on wet asphalt as the wipers slapped and the headlights cut through the downpour toward the city.",
    "The dough rose under a cloth, then the baker folded it, scored the top, and slid it onto the hot stone.",
    "Strings buzzed as the fingers slid up the fretboard and the pick struck a chord into the microphone.",
    "Steam rose from the boiler as the pistons drove the iron wheels along the gleaming rails.",
    "The needle pierced the fabric and the thread pulled tight, drawing two panels of denim together.",
    "Frost clung to the window as the kettle whistled and the mug warmed cold hands.",
    "The reel sang as the line stripped out and the rod bent double under a silver flash beneath the surface.",
    "Pages turned in the quiet room as the lamp cast a warm circle over the open book.",
    "The chisel bit into the walnut and a curl of shaving fell as the carver worked the grain.",
    "Hooves drummed on the turf as the rider leaned forward over the manee and the rail flashed past.",
    "The lens clicked and the shutter blinked open for an instant, freezing the light onto the sensor.",
    "Bristles swept across the canvas, leaving a thick stripe of cobalt that bled into the wet edge.",
    "The puck slid across the ice as the stick curved back and the skates carved a sharp turn.",
    "Coins rattled in the hopper as the lever clunked and three cherries lit up in a row.",
    "The match flared, scent of sulfur, then the candlewick caught and a steady flame steadied.",
    "Gears clicked down as the chain climbed the cassette and the rider stood on the pedals.",
    "The whisk spun in the bowl and the cream thickened into soft pale peaks.",
    "Sand trickled through the narrow glass neck, marking the minutes in a fine falling stream.",
    "The bow drew across the strings and a long note swelled through the wooden body of the instrument.",
    "The trowel scraped the mortar and the brick settled square against the line.",
]

_B_PASSAGES = [
    "It was, on the whole, a fairly ordinary afternoon, and things continued much as they had before.",
    "After a while the conversation drifted, and there was not a great deal more to be said about it.",
    "The weather being what it was, nothing much happened, and the day passed without incident.",
    "In any case, the matter was set aside, and they moved on to other, unrelated things.",
    "Eventually the discussion wound down, and a general sense of routine settled over everything.",
    "For the most part the situation remained unchanged, and the afternoon proceeded quietly.",
    "All things considered, it was neither here nor there, and not much came of it in the end.",
    "The details need not concern us further, as the outcome was broadly as one might have expected.",
    "Such being the case, the topic was allowed to lapse, and ordinary affairs resumed their course.",
    "On reflection there was little to remark upon, and the remainder of the day was uneventful.",
    "Be that as it may, the point is moot, and we need not dwell on it any longer than necessary.",
    "In short, nothing of note followed, and the whole affair concluded in the usual fashion.",
    "The rest, as they say, is history, though there is rather less to it than that implies.",
    "Suffice it to say that matters proceeded apace, and nothing especially remarkable came to pass.",
    "By and large the outcome was predictable, and the day ended much as it had begun.",
    "It goes without saying that the specifics are tedious, and the broad picture is unchanged.",
    "That about covers it, really, and there is little to add that would be of any consequence.",
    "Needless to say, this changed very little, and the situation carried on as before.",
    "At the end of the day it amounted to very little, and the matter was quietly forgotten.",
    "So things stood, more or less, and there was nothing further worth remarking upon.",
]


def passage_prompts():
    A = [{"user": p, "assistant": ""} for p in _A_PASSAGES]
    B = [{"user": p, "assistant": ""} for p in _B_PASSAGES]
    return A, B


# Content-word vs function-word contrast (assistant = the word itself).
_CONTENT = ["elephant", "mountain", "kitchen", "thunder", "blanket", "forest", "castle",
            "harbor", "meadow", "candle", "tunnel", "ribbon", "boulder", "lantern",
            "meadow", "pillow", "biscuit", "saddle", "anvil", "compass"]
_FUNCTION = ["however", "therefore", "although", "moreover", "nevertheless", "furthermore",
             "meanwhile", "consequently", "accordingly", "otherwise", "indeed", "perhaps",
             "certainly", "actually", "basically", "essentially", "generally", "obviously",
             "specifically", "subsequently"]


def word_prompts():
    A = [{"user": "Continue with one word.", "assistant": w} for w in _CONTENT]
    B = [{"user": "Continue with one word.", "assistant": w} for w in _FUNCTION]
    return A, B
