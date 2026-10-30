"""Content-word vs function-word (at L20-24) and concept-completion contrasts."""
from contrasts2 import _A_PASSAGES
from novel2 import _CONCEPTS

_CONTENT = ["elephant","mountain","kitchen","thunder","blanket","forest","castle","harbor",
            "meadow","candle","tunnel","ribbon","boulder","lantern","pillow","biscuit",
            "saddle","anvil","compass","whisk"]
_FUNCTION = ["however","therefore","although","moreover","nevertheless","furthermore",
             "meanwhile","consequently","accordingly","otherwise","indeed","perhaps",
             "certainly","actually","basically","essentially","generally","obviously",
             "specifically","subsequently"]

def wf_content_function():
    A=[{"user":"Continue with one word.","assistant":w} for w in _CONTENT]
    B=[{"user":"Continue with one word.","assistant":w} for w in _FUNCTION]
    return A,B

# concept-completion: A = passage then concept word; B = passage then prose word.
# Use my own passages + my own concept words (not association targets).
_COMPLETION = [
    ("Wheels spun on wet asphalt as wipers slapped and headlights cut the downpour.","driving"),
    ("The dough rose under a cloth, then the baker folded and scored it.","bread"),
    ("Strings buzzed as fingers slid up the fretboard and the pick struck a chord.","guitar"),
    ("Steam rose from the boiler as pistons drove the iron wheels along the rails.","train"),
    ("The needle pierced the fabric and the thread pulled two panels of denim tight.","sewing"),
    ("Frost clung to the window as the kettle whistled and the mug warmed cold hands.","tea"),
    ("The reel sang as the line stripped out and the rod bent double under a flash.","fishing"),
    ("Pages turned in the quiet room as the lamp cast a warm circle on the open book.","reading"),
    ("The chisel bit into the walnut and a curl of shaving fell along the grain.","carving"),
    ("Hooves drummed on the turf as the rider leaned forward and the rail flashed past.","racing"),
    ("The lens clicked and the shutter blinked open for an instant, freezing light.","photography"),
    ("Bristles swept the canvas, leaving a thick stripe of cobalt in the wet edge.","painting"),
    ("The puck slid across the ice as the stick curved back and skates carved a turn.","hockey"),
    ("Coins rattled in the hopper as the lever clunked and three cherries lit up.","gambling"),
    ("The match flared, scent of sulfur, then the wick caught and a flame held.","lighting"),
    ("Gears clicked down as the chain climbed the cassette and the rider stood up.","cycling"),
    ("The whisk spun in the bowl and the cream thickened into soft pale peaks.","whipping"),
    ("Sand trickled through the narrow glass neck, marking the minutes falling.","time"),
    ("The bow drew across the strings and a long note swelled through the wood.","music"),
    ("The trowel scraped the mortar and the brick settled square to the line.","masonry"),
]
_PROSE = ["afterward","then","later","soon","meanwhile","afterwards","next","shortly","subsequently","eventually",
          "afterward","then","later","soon","meanwhile","afterwards","next","shortly","subsequently","eventually"]
def cc_completion():
    A=[{"user":p,"assistant":" "+c} for p,c in _COMPLETION]
    B=[{"user":p,"assistant":" "+w} for p,w in zip([p for p,_ in _COMPLETION],_PROSE)]
    return A,B
