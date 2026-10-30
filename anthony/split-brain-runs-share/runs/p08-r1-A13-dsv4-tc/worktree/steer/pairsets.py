"""Contrast pairs for non-stance directions (grammatical / figurative contrasts)."""

# concurrent (subordinate 'while' holding a background state) vs sequential (paratactic)
CONCURRENT = [
    ("While she stirred the soup, she kept an eye on the timer.", "She stirred the soup and kept an eye on the timer."),
    ("As he drove through the rain, he rehearsed the speech.", "He drove through the rain and rehearsed the speech."),
    ("While the kettle boiled, she sorted the post.", "The kettle boiled and she sorted the post."),
    ("As the music played on, he thought about the letter.", "The music played on and he thought about the letter."),
    ("While waiting for the train, she counted the cracks in the platform.", "She waited for the train and counted the cracks in the platform."),
    ("As the night wore on, the sentry watched the ridge.", "The night wore on and the sentry watched the ridge."),
    ("While the bread rose, he swept the kitchen floor.", "The bread rose and he swept the kitchen floor."),
    ("As the tide came in, the walkers moved up the beach.", "The tide came in and the walkers moved up the beach."),
    ("While the meeting dragged on, she sketched in the margin.", "The meeting dragged on and she sketched in the margin."),
    ("As the kettle hissed, he read the last page.", "The kettle hissed and he read the last page."),
    ("While the snow fell outside, they played cards at the table.", "The snow fell outside and they played cards at the table."),
    ("As the clock struck nine, the guards changed shifts.", "The clock struck nine and the guards changed shifts."),
    ("While the river rose, the village stacked sandbags.", "The river rose and the village stacked sandbags."),
    ("As the storm gathered, the crew lashed down the sails.", "The storm gathered and the crew lashed down the sails."),
    ("While the fire crackled, the child turned the pages.", "The fire crackled and the child turned the pages."),
    ("As the kettle steamed, she jotted the recipe down.", "The kettle steamed and she jotted the recipe down."),
    ("While the patient slept, the nurse checked the chart.", "The patient slept and the nurse checked the chart."),
    ("As the crowd quieted, the conductor raised the baton.", "The crowd quieted and the conductor raised the baton."),
    ("While the engine idled, he studied the map.", "The engine idled and he studied the map."),
    ("As the candles burned low, the two talked on.", "The candles burned low and the two talked on."),
    ("While the dough cooled, the baker mixed the glaze.", "The dough cooled and the baker mixed the glaze."),
    ("As the fog thickened, the ferry sounded its horn.", "The fog thickened and the ferry sounded its horn."),
    ("While the audience settled, the pianist flexed her fingers.", "The audience settled and the pianist flexed her fingers."),
    ("As the kettle sang, he folded the newspaper.", "The kettle sang and he folded the newspaper."),
    ("While the stars came out, the campers lit the lantern.", "The stars came out and the campers lit the lantern."),
    ("As the rain let up, they stepped out into the wet street.", "The rain let up and they stepped out into the wet street."),
    ("While the paint dried, she cleaned the brushes.", "The paint dried and she cleaned the brushes."),
    ("As the bell sounded, the students closed their books.", "The bell sounded and the students closed their books."),
    ("While the tea steeped, he returned the phone call.", "The tea steeped and he returned the phone call."),
    ("As the curtain rose, the stage lights flared.", "The curtain rose and the stage lights flared."),
    # figurative vs literal
]

FIGURATIVE = [
    ("Her heart was a stone in her chest.", "She felt nothing at all."),
    ("Time is a thief that steals the hours.", "Time passes more quickly than one expects."),
    ("The news hit him like a wave.", "The news surprised him very much."),
    ("His words were knives in the quiet room.", "His words hurt everyone in the quiet room."),
    ("The city was a jungle of concrete and glass.", "The city was crowded with buildings and glass."),
    ("Anger smouldered in his chest all evening.", "He stayed quietly angry all evening."),
    ("Her grief was an ocean she could not cross.", "Her grief was too large to get past."),
    ("The idea took root in her mind overnight.", "The idea gradually formed in her mind overnight."),
    ("A blanket of snow covered the quiet fields.", "Snow covered the quiet fields completely."),
    ("The rumor spread like wildfire through town.", "The rumor spread very fast through town."),
    ("Hope flickered like a candle in the dark.", "A small hope remained despite the difficulty."),
    ("The mist was a curtain over the harbour.", "Mist covered the harbour."),
    ("His mind was a maze that evening.", "His thoughts were confused that evening."),
    ("The old house creaked its complaints all night.", "The old house creaked noisily all night."),
    ("Jealousy coiled in her stomach like a snake.", "She felt sharply jealous."),
    ("The stars were diamonds on black velvet.", "The stars shone brightly in the black sky."),
    ("A wall of silence rose between them.", "They stopped speaking to one another."),
    ("The project was a sinking ship by June.", "The project was failing badly by June."),
    ("Laughter rippled through the crowded hall.", "People laughed together in the crowded hall."),
    ("The deadline loomed like a storm on the horizon.", "The deadline was approaching very soon."),
]


def concurrent_items():
    return [{"a": a, "b": b} for a, b in CONCURRENT]

def figurative_items():
    return [{"a": a, "b": b} for a, b in FIGURATIVE]

print(len(CONCURRENT), "concurrent pairs;", len(FIGURATIVE), "figurative pairs")

# topic-continuity (second sentence stays on the first's implied frame) vs topic-shift
TOPIC_HOLD = [
    ("She lifted the violin and drew the bow across the strings. The first note wobbled and then warmed into tune.", "She lifted the violin and drew the bow across the strings. The bus was running late again."),
    ("He chalked the cue and bent over the green felt. The white ball kissed the eight into the corner.", "He chalked the cue and bent over the green felt. The rent was due on Friday."),
    ("The nurse tightened the cuff and watched the dial. The reading was higher than the day before.", "The nurse tightened the cuff and watched the dial. The window needed replacing after winter."),
    ("She kneaded the dough and shaped it into a ball. The loaf rose slowly in the warm room.", "She kneaded the dough and shaped it into a ball. The meeting had been moved to three."),
    ("He checked the tide chart and strapped on the waxed boots. The pools teemed with tiny crabs.", "He checked the tide chart and strapped on the waxed boots. The invoice was missing a page."),
    ("The chef set the pan over the flame. The butter foamed and the garlic turned gold.", "The chef set the pan over the flame. The repairman never called back."),
    ("She adjusted the focus and pressed the shutter. The portrait came out sharper than she hoped.", "She adjusted the focus and pressed the shutter. The forecast mentioned snow."),
    ("He pulled on the gloves and stepped into the ring. The first jab caught the air by his chin.", "He pulled on the gloves and stepped into the ring. The printer had jammed again."),
    ("The pilot pulled back on the yoke. The wheels left the tarmac with a low shudder.", "The pilot pulled back on the yoke. The garden gate swung in the wind."),
    ("She buried the bulb and pressed the soil firm. A shoot would break through by spring.", "She buried the bulb and pressed the soil firm. The traffic report was grim."),
    ("He threaded the needle and knotted the thread. The seam disappeared into the hem.", "He threaded the needle and knotted the thread. The meeting dragged past five."),
    ("The bartender shook the tin over his shoulder. The drink came out cold and faintly green.", "The bartender shook the tin over his shoulder. The election was too close to call."),
    ("She tuned the guitar and tried a chord. The strings held their pitch through the verse.", "She tuned the guitar and tried a chord. There was a queue at the lockers."),
    ("He squared the paper and folded it twice. The crane stood upright on the desk.", "He squared the paper and folded it twice. The meeting was cancelled outright."),
    ("The mechanic slid under the chassis. The rattle was a loose bracket after all.", "The mechanic slid under the chassis. The bakery had sold out of rye."),
    ("She dipped the brush and touched it to the canvas. The sky took on a stormy grey.", "She dipped the brush and touched it to the canvas. The phone rang once and stopped."),
    ("He loaded the film and wound the spool. The first frame was a little overexposed.", "He loaded the film and wound the spool. The bus fare had gone up."),
    ("The barber snapped the cape and picked up the shears. The first lock fell to the floor.", "The barber snapped the cape and picked up the shears. The train had already left the station."),
    ("She lit the taper and held it to the wick. The flame caught and steadied in the dark.", "She lit the taper and held it to the wick. The report was due in an hour."),
    ("He read the compass and set the bearings. The ridge came into view through the mist.", "He read the compass and set the bearings. The fridge was almost empty."),
]

def topic_items():
    return [{"a": a, "b": b} for a, b in TOPIC_HOLD]

print(len(TOPIC_HOLD), "topic-hold pairs")
