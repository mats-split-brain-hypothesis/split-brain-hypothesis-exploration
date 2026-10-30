"""Generate additional independent self-authored think/don't-think stance prompt sets.
Each set uses different concepts, carriers and wording, so the sets are independent draws
of the same stance contrast. Ensembling their unit directions gives a cleaner stance vector
than any single set, without using WSB's directed_modulation bank.
"""
import json, random

# A larger pool of (category, concept) pairs, none in the association fit targets.
CONCEPTS = [
    ("the instrument", "cello"), ("the wood", "mahogany"), ("the bird", "pelican"),
    ("the mineral", "quartz"), ("the boat", "gondola"), ("the nut", "pistachio"),
    ("the instrument", "saxophone"), ("the stone", "marble"), ("the bird", "heron"),
    ("the spice", "saffron"), ("the fabric", "linen"), ("the tool", "chisel"),
    ("the flower", "tulip"), ("the metal", "copper"), ("the fish", "trout"),
    ("the fruit", "guava"), ("the tree", "birch"), ("the vegetable", "radish"),
    ("the insect", "dragonfly"), ("the shell", "conch"), ("the weapon", "dagger"),
    ("the dance", "tango"), ("the gem", "topaz"), ("the cloud", "cumulus"),
    ("the knot", "bowline"), ("the engine", "turbine"), ("the lens", "prism"),
    ("the coin", "doubloon"), ("the curve", "parabola"), ("the dish", "risotto"),
    ("the sport", "fencing"), ("the fabric", "velvet"), ("the metal", "tungsten"),
    ("the bird", "falcon"), ("the tree", "willow"), ("the spice", "paprika"),
    ("the instrument", "harpsichord"), ("the flower", "orchid"), ("the boat", "kayak"),
    ("the stone", "granite"),
    # extra for sets 2/3
    ("the fruit", "lychee"), ("the metal", "bronze"), ("the bird", "robin"),
    ("the tree", "cedar"), ("the spice", "cumin"), ("the fabric", "denim"),
    ("the tool", "plane"), ("the flower", "dahlia"), ("the gem", "garnet"),
    ("the instrument", "mandolin"), ("the fish", "mackerel"), ("the boat", "trawler"),
    ("the wood", "teak"), ("the dance", "waltz"), ("the sport", "javelin"),
    ("the cloud", "cirrus"), ("the knot", "hitch"), ("the engine", "piston"),
    ("the lens", "louver"), ("the coin", "florin"), ("the curve", "hyperbola"),
    ("the dish", "goulash"), ("the shell", "nautilus"), ("the insect", "locust"),
    ("the stone", "basalt"), ("the mineral", "beryl"), ("the weapon", "mace"),
    ("the vegetable", "fennel"), ("the tree", "poplar"), ("the bird", "raven"),
    ("the spice", "turmeric"), ("the fabric", "satin"), ("the metal", "nickel"),
    ("the tool", "gouge"), ("the flower", "petunia"), ("the gem", "opal"),
    ("the instrument", "clarinet"), ("the fish", "halibut"), ("the boat", "skiff"),
    ("the wood", "walnut"), ("the dance", "polka"), ("the sport", "curling"),
    ("the fruit", "papaya"), ("the knot", "bend"), ("the engine", "crankshaft"),
]

CARRIERS = [
    "The quarterly figures were filed before the deadline.",
    "She adjusted the thermostat and closed the blinds.",
    "The courier left the parcel at the front desk.",
    "He signed the receipt and pocketed the change.",
    "The auditor noted a small discrepancy in the ledger.",
    "They rescheduled the call for Thursday afternoon.",
    "The printer jammed on the third page of the report.",
    "She watered the plant and locked the office door.",
    "The backup completed just before midnight.",
    "He forwarded the memo to the whole team.",
    "The tenant paid the rent in cash this month.",
    "She replaced the battery and tested the alarm.",
    "The chef tasted the broth and added a pinch of salt.",
    "He wiped the counter and stacked the chairs.",
    "The delegate raised a point of order.",
    "She folded the letter and sealed the envelope.",
    "The mechanic checked the tyre pressure first.",
    "He sorted the mail into three piles.",
    "The librarian reshelved the returned books.",
    "She refilled the kettle and switched it on.",
    "The gardener pruned the hedge in the rain.",
    "He calibrated the scale before weighing the sample.",
    "The nurse recorded the reading on the chart.",
    "She stitched the hem and pressed the fabric.",
    "The clerk stamped the form and filed it away.",
    "He oiled the chain and tightened the brakes.",
    "The pilot checked the gauges one last time.",
    "She tuned the radio to the morning broadcast.",
    "The baker scored the loaves before baking.",
    "He marked the trail with a strip of cloth.",
    "The artist mixed the paints on a wooden board.",
    "She wrapped the gift in brown paper.",
    "The driver checked the mirror and signalled.",
    "He nailed the boards together evenly.",
    "The tailor pinned the pattern to the cloth.",
    "She poured the wax into the mould slowly.",
    "The vet examined the paw and applied a wrap.",
    "He cast the line and waited by the bank.",
    "The welder tapped the helmet down and struck an arc.",
    "She swept the step and shook out the mat.",
    # extra carriers
    "The porter carried the cases up two flights.",
    "She logged the call and filed the report.",
    "He replaced the filter and bled the radiator.",
    "The guide untied the rope and coiled it neatly.",
    "She stamped the ticket and waved him through.",
    "The intern collated the pages and bound them.",
    "He prised the lid off with a flat blade.",
    "She calibrated the meter against the reference.",
    "The cook blanched the vegetables in salted water.",
    "He keyed the code and pushed the door open.",
]

PAIRS = [
    ("Think about", "Do not think about"),
    ("Keep in mind", "Keep out of mind"),
    ("Hold in your thoughts", "Push out of your thoughts"),
    ("Concentrate on", "Avoid thinking about"),
    ("Focus on", "Try hard not to think about"),
    ("Turn your attention to", "Turn your attention away from"),
    ("Reflect on", "Refrain from reflecting on"),
    ("Bear in mind", "Banish from your mind"),
    ("Mull over", "Refuse to dwell on"),
    ("Dwell on", "Steer your mind away from"),
]

def make_set(seed, n=40):
    rnd = random.Random(seed)
    concepts = CONCEPTS[:]
    carriers = CARRIERS[:]
    rnd.shuffle(concepts); rnd.shuffle(carriers)
    think, dont = [], []
    for i in range(n):
        cat, concept = concepts[i % len(concepts)]
        carrier = carriers[i % len(carriers)]
        tp, dp = rnd.choice(PAIRS)
        t = f'{tp} {cat} {concept} while you write. Now write exactly this sentence: "{carrier}"'
        d = f'{dp} {cat} {concept} while you write. Now write exactly this sentence: "{carrier}"'
        think.append({"user": t, "assistant": carrier})
        dont.append({"user": d, "assistant": carrier})
    return think, dont

if __name__ == "__main__":
    layers = [20,21,22,23,24]
    for sid in [2,3]:
        think, dont = make_set(seed=100+sid, n=40)
        json.dump({"layers": layers, "prompts": think, "positions": "assistant"},
                  open(f"work/steer/spec_s{sid}_think.json","w"))
        json.dump({"layers": layers, "prompts": dont, "positions": "assistant"},
                  open(f"work/steer/spec_s{sid}_dont.json","w"))
        print(f"set {sid}: {len(think)} pairs; T: {think[0]['user'][:90]}")
    print("wrote specs for sets 2,3")
