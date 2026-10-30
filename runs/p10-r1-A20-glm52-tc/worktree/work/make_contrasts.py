import json

layers = [18,20,21,22,23,24,26]

# ---- Contrast 1: self-written think/don't-think with my OWN concepts & carriers ----
# Distinct from bench: my own concepts, my own neutral carrier sentences, my own wording.
own_pairs = [
    ("anvil", "The blacksmith wiped soot from his apron and reached for the heavy iron tool."),
    ("compass", "The navigator rotated the glass face and watched the magnetized needle settle."),
    ("kayak", "She dipped the double-bladed paddle and glided past the line of mossy boulders."),
    ("accordion", "He pumped the bellows and his fingers danced across the rows of buttons."),
    ("telescope", "She adjusted the brass tube and squinted through the eyepiece at the rings."),
    ("harvest", "The farmer wiped his brow and surveyed the golden field ready for the sickle."),
    ("glacier", "A tongue of blue ice crept between the peaks, cracking and groaning in the cold."),
    ("monsoon", "The seasonal rains returned and the river swelled over its muddy banks."),
    ("meadow", "Wildflowers swayed in the breeze and bees drifted among the clover blossoms."),
    ("canyon", "The river had carved a deep groove through the layered red rock over millennia."),
    ("temple", "Incense drifted past the stone columns and devotees bowed before the altar."),
    ("carnival", "Ferris wheels turned above the stalls and barkers called out to the passing crowds."),
    ("trellis", "Vines climbed the wooden lattice and clusters of grapes hung heavy in the sun."),
    ("forge", "Sparks flew as the hammer rang against the glowing bar of metal on the anvil."),
    ("kennel", "The dogs barked from their runs as the trainer walked down the line with bowls."),
    ("atelier", "Easels crowded the sunlit room and the smell of turpentine and oil paint hung thick."),
    ("regatta", "Sails billowed across the bay as the fleet jostled at the starting line."),
    ("orchard", "Rows of apple trees stretched up the slope, their branches heavy with red fruit."),
    ("aqueduct", "The stone arches carried water across the valley from the distant hills."),
    ("observatory", "The domed roof slid open and the great mirror turned toward the night sky."),
    ("mill", "The great wheel turned and water splashed as the stones ground the grain below."),
    ("bazaar", "Lanterns hung across the alley and merchants spread their silks upon the mats."),
    ("vineyard", "Workers moved between the rows of vines, baskets filling with dark purple clusters."),
    ("campfire", "Sparks rose into the dark and the logs settled with a hiss as the evening cooled."),
]
SA = "Hold the {c} clearly in mind as you write. Now write exactly this sentence:"
SB = "Keep the {c} firmly out of mind as you write. Now write exactly this sentence:"
prompts_own = []
for c, carrier in own_pairs:
    prompts_own.append({"user": f"{SA.format(c=c)} \"{carrier}\"", "assistant": carrier})
    prompts_own.append({"user": f"{SB.format(c=c)} \"{carrier}\"", "assistant": carrier})
json.dump({"layers": layers, "prompts": prompts_own[0::2], "positions": "assistant"}, open("work/spec_own_A.json","w"), ensure_ascii=False)
json.dump({"layers": layers, "prompts": prompts_own[1::2], "positions": "assistant"}, open("work/spec_own_B.json","w"), ensure_ascii=False)
print("own pairs", len(own_pairs))

# ---- Contrast 2: hold-the-subject-in/out-of-thoughts, NO concept named ----
# Both instructions reference "the subject of the sentence" abstractly; the concept is only implied by the carrier.
subj_carriers = [
    "She leapt above the net and spiked the ball into the open corner of the court.",
    "He moved the knight across the board and tapped the clock without looking up.",
    "He hunched low over the handlebars as the peloton streamed toward the finish line.",
    "She served an ace down the center line, the ball clipping the tape on its way past.",
    "He swung hard and the bat connected, sending the ball soaring over the outfield wall.",
    "She lined up the putt on the green and tapped the ball gently toward the hole.",
    "His fingers moved across the black and white keys, filling the room with a flowing melody.",
    "She drew the bow across the strings, vibrato warming each sustained note.",
    "The river burst its banks and muddy water poured through the streets of the town.",
    "Ash belched from the crater and a river of molten rock crept down the mountainside.",
    "A wall of snow broke loose from the ridge and thundered down the gully below.",
    "Lightning split the sky and the wind hurled rain against the shutters all night.",
    "Dunes stretched to the horizon under a relentless sun, the air shimmering with heat.",
    "Rows of shelves stretched back into the silence, each packed with spines in faded gold.",
    "Pots clattered on the stove and the smell of garlic filled the small busy room.",
    "The soprano held the final note as the curtain fell to a hushed, darkened hall.",
    "He pushed his chips to the center and studied the other players across the felt table.",
    "She drew the bowstring to her cheek and let the arrow fly toward the distant target.",
    "A sweeping beam rotated over the dark water, warning ships away from the rocks.",
    "Drops began to patter on the leaves and within minutes the path was a stream of mud.",
]
UA = "Keep the subject of the following sentence actively in mind as you copy it. Now write exactly:"
UB = "Disregard the subject of the following sentence entirely as you copy it. Now write exactly:"
prompts_subj = []
for carrier in subj_carriers:
    prompts_subj.append({"user": f"{UA} \"{carrier}\"", "assistant": carrier})
    prompts_subj.append({"user": f"{UB} \"{carrier}\"", "assistant": carrier})
json.dump({"layers": layers, "prompts": prompts_subj[0::2], "positions": "assistant"}, open("work/spec_subj_A.json","w"), ensure_ascii=False)
json.dump({"layers": layers, "prompts": prompts_subj[1::2], "positions": "assistant"}, open("work/spec_subj_B.json","w"), ensure_ascii=False)
print("subj carriers", len(subj_carriers))
