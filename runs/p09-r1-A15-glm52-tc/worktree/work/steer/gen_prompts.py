"""Generate self-authored contrast prompts for steering vectors (not WSB's directed_modulation bank).

Two families:
  stance : my own think / don't-think pairs (same concept + carrier, only the stance word differs)
            -> captured at the assistant (carrier) cells, as WBS does, but from MY prompts.
  fv     : function-vector / task-set contrast. ICL (with examples) vs zero-shot (no examples),
            same query, captured at the answer position. A task-set vector, not a stance.

Concepts and carriers are hand-written and share no string with the association fit targets
or with directed_modulation's concepts.
"""
import json, random

random.seed(7)

# concepts: concrete, single-token-friendly, NOT in fit targets, NOT in dm concepts
STANCE_CONCEPTS = [
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
]

# (positive_phrase, negative_phrase) inserted before "{cat} {concept} while you write."
STANCE_PAIRS = [
    ("Think about", "Do not think about"),
    ("Keep in mind", "Keep out of mind"),
    ("Hold in your thoughts", "Push out of your thoughts"),
    ("Concentrate on", "Avoid thinking about"),
    ("Focus on", "Try hard not to think about"),
    ("Turn your attention to", "Turn your attention away from"),
    ("Reflect on", "Refrain from reflecting on"),
]

def stance_prompts():
    """think / dont_think pairs: same concept+carrier, only the stance phrase differs."""
    pairs = list(zip(STANCE_CONCEPTS, CARRIERS))
    random.shuffle(pairs)
    think, dont = [], []
    for (cat, concept), carrier in pairs:
        tp, dp = random.choice(STANCE_PAIRS)
        t_instr = f"{tp} {cat} {concept} while you write. Now write exactly this sentence: \"{carrier}\""
        d_instr = f"{dp} {cat} {concept} while you write. Now write exactly this sentence: \"{carrier}\""
        think.append({"user": t_instr, "assistant": carrier})
        dont.append({"user": d_instr, "assistant": carrier})
    return think, dont

# ---- function-vector / task-set contrast ----
# My own description->concept pairs (NOT fit targets).
FV_PAIRS = [
    ("A stringed instrument played with a bow, larger than a violin.", "cello"),
    ("A hardwood with a reddish-brown grain, used for fine furniture.", "mahogany"),
    ("A large white waterbird with a long beak.", "pelican"),
    ("A hard crystalline mineral, often clear or smoky.", "quartz"),
    ("A long narrow boat rowed from the stern, used in Venice.", "gondola"),
    ("A small green nut with a split shell.", "pistachio"),
    ("A curved brass wind instrument with a reed mouthpiece.", "saxophone"),
    ("A hard metamorphic stone, often streaked with colour.", "marble"),
    ("A wading bird with long legs, found by marshes.", "heron"),
    ("An orange-red spice dried from crocus flowers.", "saffron"),
    ("A woven fabric made from flax fibres.", "linen"),
    ("A hand tool with a bevelled blade for carving wood.", "chisel"),
    ("A cup-shaped spring flower of many colours.", "tulip"),
    ("A reddish metal, excellent conductor of electricity.", "copper"),
    ("A freshwater fish with speckled skin, prized by anglers.", "trout"),
    ("A round tropical fruit with pink flesh.", "guava"),
    ("A pale-barked tree with drooping branches.", "willow"),
    ("A red root vegetable, often eaten in salads.", "radish"),
    ("A fast-flying insect with four long wings.", "dragonfly"),
    ("A spiral sea shell, often pink inside.", "conch"),
]

def fv_prompts():
    """ICL (with examples) vs zero-shot (no examples), same query, captured at answer position.
    Positive: a few-shot prompt ending 'Concept:' at the query.
    Negative: the query alone ending 'Concept:'.
    Returns (positive_list, negative_list), each a list of {user, assistant}."""
    pos, neg = [], []
    # build many by rotating examples and queries
    ex_pool = FV_PAIRS
    n = len(ex_pool)
    for qi in range(n):
        query_d, query_c = ex_pool[qi]
        examples = [ex_pool[j] for j in range(n) if j != qi][:4]  # 4 examples, exclude query
        ex_text = "".join(f"Description: {d} Concept: {c}. " for d, c in examples)
        pos_user = f"{ex_text}Description: {query_d} Concept:"
        # answer position is right after "Concept:" -> put a leading space as assistant prefill
        pos.append({"user": pos_user, "assistant": " "})
        neg_user = f"Description: {query_d} Concept:"
        neg.append({"user": neg_user, "assistant": " "})
    return pos, neg

if __name__ == "__main__":
    think, dont = stance_prompts()
    print(f"stance: {len(think)} think, {len(dont)} dont")
    print("  T:", think[0]["user"][:110])
    print("  D:", dont[0]["user"][:110])
    pos, neg = fv_prompts()
    print(f"fv: {len(pos)} pos, {len(neg)} neg")
    print("  P:", pos[0]["user"][:160])
    print("  N:", neg[0]["user"][:160])
    layers = [20,21,22,23,24]
    json.dump({"layers": layers, "prompts": think, "positions": "assistant"},
              open("work/steer/spec_stance_think.json","w"))
    json.dump({"layers": layers, "prompts": dont, "positions": "assistant"},
              open("work/steer/spec_stance_dont.json","w"))
    json.dump({"layers": layers, "prompts": pos, "positions": "last"},
              open("work/steer/spec_fv_pos.json","w"))
    json.dump({"layers": layers, "prompts": neg, "positions": "last"},
              open("work/steer/spec_fv_neg.json","w"))
    print("wrote 4 specs")
