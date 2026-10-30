import json

# Self-written carrier sentences, each implying a concrete concept (like association items),
# paired with two stance instructions. The carrier is identical across the two conditions,
# so content cancels and only the stance ("infer what it's really about" vs "copy literally") remains.
pairs = [
    ("volleyball", "She leapt above the net and spiked the ball into the open corner of the court."),
    ("chess", "He moved the knight across the board and tapped the clock without looking up."),
    ("cycling", "He hunched low over the handlebars as the peloton streamed toward the finish line."),
    ("tennis", "She served an ace down the center line, the ball clipping the tape on its way past."),
    ("baseball", "He swung hard and the bat connected, sending the ball soaring over the outfield wall."),
    ("golf", "She lined up the putt on the green and tapped the ball gently toward the hole."),
    ("piano", "His fingers moved across the black and white keys, filling the room with a flowing melody."),
    ("violin", "She drew the bow across the strings, vibrato warming each sustained note."),
    ("flood", "The river burst its banks and muddy water poured through the streets of the town."),
    ("volcano", "Ash belched from the crater and a river of molten rock crept down the mountainside."),
    ("avalanche", "A wall of snow broke loose from the ridge and thundered down the gully below."),
    ("storm", "Lightning split the sky and the wind hurled rain against the shutters all night."),
    ("desert", "Dunes stretched to the horizon under a relentless sun, the air shimmering with heat."),
    ("forest", "Tall pines crowded the hillside, their canopy blocking out most of the daylight."),
    ("library", "Rows of shelves stretched back into the silence, each packed with spines in faded gold."),
    ("kitchen", "Pots clattered on the stove and the smell of garlic filled the small busy room."),
    ("opera", "The soprano held the final note as the curtain fell to a hushed, darkened hall."),
    ("ballet", "She rose onto her toes and spun across the stage under the warm stage lights."),
    ("poker", "He pushed his chips to the center and studied the other players across the felt table."),
    ("archery", "She drew the bowstring to her cheek and let the arrow fly toward the distant target."),
    ("submarine", "The vessel descended below the waves, its hull groaning as the pressure mounted."),
    ("lighthouse", "A sweeping beam rotated over the dark water, warning ships away from the rocks."),
    ("rain", "Drops began to patter on the leaves and within minutes the path was a stream of mud."),
    ("fire", "Flames licked up the curtains and smoke billowed across the ceiling of the room."),
    ("bridge", "Cables hung from the towers and the roadway swayed gently above the strait below."),
    ("market", "Stalls lined the narrow lane and vendors called out prices over the morning crowd."),
    ("cathedral", "Stained glass glowed in the high windows and incense hung in the vaulted air."),
    ("harbor", "Masts rocked at their moorings and the smell of salt and fish hung over the docks."),
]

STANCE_A = "As you write the sentence below, keep clearly in mind what kind of thing it is really about. Now write exactly this sentence:"
STANCE_B = "Without thinking about what it means, just copy the sentence below exactly. Now write exactly this sentence:"

prompts = []
for concept, carrier in pairs:
    prompts.append({"user": f"{STANCE_A} \"{carrier}\"", "assistant": carrier})
    prompts.append({"user": f"{STANCE_B} \"{carrier}\"", "assistant": carrier})

spec = {"layers": [18,20,21,22,23,24,26], "prompts": prompts, "positions": "assistant"}
json.dump(spec, open("work/spec_infer.json","w"), ensure_ascii=False)
print(len(prompts), "prompts", len(pairs), "pairs")
