"""Contrast prompt pairs for steering the plain J-lens toward concept-naming.

All concepts are generic everyday words unrelated to the association fit targets.
Each pair shares a definition (user) and differs only in the assistant cue:
  A cues a single concept word (retrieval/commit mode);
  B cues prose continuation.
"""

# (definition, ) -> A assistant / B assistant
# A: cue to output the single concept word; B: cue to continue prose.
_PAIRS = [
    ("A color made by mixing blue and yellow.",
     "The word for it is", "Continuing, the color"),
    ("A common pet that says meow and chases mice.",
     "The word for it is", "Continuing, the animal"),
    ("A fruit that is red or green and grows on trees.",
     "The word for it is", "Continuing, the fruit"),
    ("A shape with three straight sides and three angles.",
     "The word for it is", "Continuing, the shape"),
    ("A vehicle with two wheels and pedals.",
     "The word for it is", "Continuing, the vehicle"),
    ("A piece of furniture with a flat top and legs.",
     "The word for it is", "Continuing, the object"),
    ("A large body of water surrounded by land.",
     "The word for it is", "Continuing, the feature"),
    ("A tool with a handle and metal head used for hitting nails.",
     "The word for it is", "Continuing, the tool"),
    ("A yellow citrus fruit that is very sour.",
     "The word for it is", "Continuing, the fruit"),
    ("A machine that keeps food cold.",
     "The word for it is", "Continuing, the appliance"),
    ("A season when leaves fall and the weather cools.",
     "The word for it is", "Continuing, the season"),
    ("A metal that is liquid at room temperature.",
     "The word for it is", "Continuing, the element"),
    ("A building where books are kept for borrowing.",
     "The word for it is", "Continuing, the place"),
    ("A person who treats sick people.",
     "The word for it is", "Continuing, the person"),
    ("A white liquid produced by mammals.",
     "The word for it is", "Continuing, the liquid"),
    ("A hard stone that is often clear and used in jewelry.",
     "The word for it is", "Continuing, the stone"),
    ("A device that makes light when electricity passes through it.",
     "The word for it is", "Continuing, the device"),
    ("A long narrow piece of wood used in building.",
     "The word for it is", "Continuing, the material"),
    ("A planet we live on.",
     "The word for it is", "Continuing, the planet"),
    ("A small round green seed eaten as a vegetable.",
     "The word for it is", "Continuing, the vegetable"),
]


def prompts():
    A, B = [], []
    for defin, cueA, cueB in _PAIRS:
        A.append({"user": defin, "assistant": cueA})
        B.append({"user": defin, "assistant": cueB})
    return A, B
