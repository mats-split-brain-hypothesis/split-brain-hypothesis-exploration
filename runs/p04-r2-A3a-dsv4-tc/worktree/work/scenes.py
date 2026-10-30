"""Neutral evocative scenes I wrote myself (each implies ONE concrete concept), for building
steering-direction contrasts. None of these are association items or use association targets."""

# (scene, its implied concept) — the concept is used ONLY in "name"-style exemplars/task text,
# never in a way that touches the association targets.
SCENES = [
    ("Drums started in the street at dusk, and feathered costumes danced until sunrise.", "parade"),
    ("She cast the line into the still water and watched the red-and-white float settle.", "fishing"),
    ("He struck the match and touched it to the pile of dry leaves in the pit.", "campfire"),
    ("The referee blew the whistle and the players dropped to one knee.", "football"),
    ("She pushed the cart down the aisle and compared the prices on the shelf.", "shopping"),
    ("The orchestra finished with a long chord that hung in the air.", "music"),
    ("He balanced the tray of glasses between the crowded tables.", "waiter"),
    ("Snow fell all night and by morning the cars were buried to their mirrors.", "blizzard"),
    ("She turned the handle and water came rushing into the tub.", "bathtub"),
    ("The dog raced after the stick and brought it back, tail wagging.", "fetch"),
    ("He flipped the pancake and caught it with a flick of the wrist.", "cooking"),
    ("The plane taxied down the runway and lifted slowly into the low clouds.", "flying"),
    ("She tightened the bolts and spun the wheel to check it moved freely.", "mechanic"),
    ("The actor forgot the line and the audience waited in silence.", "theater"),
    ("He climbed the ladder and reached for the ripest fruit on the top branch.", "orchard"),
    ("The tide went out and left the shells glistening in the sand.", "beach"),
    ("She threaded the needle and began the first careful stitch.", "sewing"),
    ("The lecturer circled a term on the board and underlined it twice.", "teacher"),
    ("He lit the torch and held it up to inspect the wall of the tunnel.", "mining"),
    ("The photographer adjusted the lens and told everyone to hold still.", "camera"),
    ("She stirred the pot and tasted the stew before adding more salt.", "soup"),
    ("The boat creaked as the oars dipped into the dark water.", "rowing"),
    ("He shuffled the deck and dealt two cards to each seat.", "poker"),
    ("The horse cleared the last fence and thundered toward the line.", "racing"),
    ("She swept the floor and emptied the pan into the bin.", "cleaning"),
    ("The climber checked the rope and drove another spike into the rock.", "mountain"),
    ("He mowed the lawn in long even stripes while the sprinkler turned.", "yard"),
    ("The waiter uncorked the bottle and poured a splash for him to taste.", "wine"),
    ("She signed her name at the bottom and slid the form across the desk.", "document"),
    ("The baker pulled the tray from the oven and the kitchen filled with warmth.", "bread"),
    ("He marked the answer sheet and moved to the next page.", "exam"),
    ("The diver stood at the edge and then sliced cleanly into the pool.", "diving"),
    ("She watered the pot and turned it so the plant faced the light.", "gardening"),
    ("The teller counted the bills twice and slid them under the glass.", "bank"),
    ("He tuned each string and plucked a slow chord to check the sound.", "guitar"),
    ("The waiter brought the check and she reached for her jacket.", "restaurant"),
]


def scenes_only():
    return [s for s, _ in SCENES]


def scenes_and_concepts():
    return list(SCENES)