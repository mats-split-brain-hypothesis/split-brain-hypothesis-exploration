"""Scene sentences that imply a concept without naming it (association-style). Written for this
task; none are copied from the fit items. Each entry: (scene, implied word) — the word is for
bookkeeping only and never enters any prompt."""

SCENES = [
    # activities
    ("Mallets swung and the ball skittered across the grass toward the goal.", "polo"),
    ("The shuttlecock arced over the net and was smashed back with a flick.", "badminton"),
    ("Yarn looped over the needles and a sleeve slowly took shape row by row.", "knitting"),
    ("The line went taut and the reel whined as the catch fought for the deep.", "fishing"),
    ("Poles dug into the snow and the pair glided down the slope in long arcs.", "skiing"),
    ("The pan hissed and onions turned translucent under the stirring spoon.", "cooking"),
    ("Gloved fists rose and the crowd pressed in around the ring.", "boxing"),
    ("The bowstring thrummed and the arrow sank into the bullseye's centre.", "archery"),
    ("Blades crossed with a ring of steel and the lunge was answered in turn.", "fencing"),
    ("Wet clay rose on the wheel and the potter's hands shaped a lip.", "pottery"),
    ("The chisel found the stone and dust fell away from a shoulder's curve.", "sculpting"),
    ("The batter rose in the oven and the kitchen filled with sweetness.", "baking"),
    ("A saw hummed and fresh sawdust drifted down from the joinery bench.", "carpentry"),
    ("The hull skimmed the water as the eight pulled together in perfect rhythm.", "rowing"),
    ("Wheels hissed on the ice and the skater's blade carved a figure.", "skating"),
    ("The kiteboard caught the gust and the rider lifted clear of the waves.", "surfing"),
    ("Thirty-two pieces stood ready and the first move was to the king's pawn.", "chess"),
    ("The caddie handed over the wedge and the player lined up the chip.", "golf"),
    ("Fingers found the keys and the first chord filled the empty hall.", "piano"),
    ("The diva held the high note and the audience forgot to breathe.", "opera"),
    # places / events
    ("The bell rang and rows of students slid into their seats with textbooks out.", "school"),
    ("Trolleys clattered and a voice announced the departure from gate twelve.", "airport"),
    ("The waves hissed over the sand and shells scattered at the tideline.", "beach"),
    ("Gurneys wheeled past and a nurse tapped a chart against her palm.", "hospital"),
    ("Stalls heaped with fruit lined the alley and vendors called their prices.", "market"),
    ("The gavel fell and the jury filed back in with their verdict folded.", "courtroom"),
    ("Candles flickered and the two stood before the altar repeating the vows.", "wedding"),
    # objects / animals
    ("It ticked on the wall, its pendulum swinging a slow, patient arc.", "clock"),
    ("The pages yellowed and the spine cracked as the old story fell open.", "book"),
    ("It curled by the fire and purred, tail flicking at a drifting ember.", "cat"),
    ("Wings beat the air and the flock wheeled south in a widening V.", "birds"),
    # nature
    ("The ground shook and the buildings swayed as the rumble rolled through.", "earthquake"),
    ("Ash plumed from the cone and the lava river crept toward the village.", "volcano"),
    ("Snow lay thick on the boughs and every sound was hushed in the white.", "winter"),
    ("Petals opened at dawn and the garden turned to face the climbing sun.", "flowers"),
    # abstract situations
    ("She tore open the envelope and her hands shook as the letter dropped.", "news"),
    ("The crowd roared and the trophy was lifted high under the floodlights.", "victory"),
    ("He stared at the ceiling all night, the argument replaying on a loop.", "regret"),
    ("The last page closed and the reader sat still, blinking back a blur.", "ending"),
    # professions / roles
    ("The baton rose and the orchestra drew a single breath together.", "conductor"),
    ("The apron went on and the first customer was waved to the chair.", "barber"),
    ("The moonlit deck creaked and the lookout scanned the fog with a glass.", "sailor"),
]

print(f"{len(SCENES)} scenes")
