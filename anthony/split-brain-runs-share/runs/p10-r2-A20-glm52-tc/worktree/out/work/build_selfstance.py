import json, sys
sys.path.insert(0,'out/work')
from scenes import SCENES

layers=list(range(14,29))

# Self-authored think/don't-think pairs: hold a concept in mind while copying a carrier.
# concept + category + neutral carrier sentence (carrier unrelated to concept).
CARRIERS = [
 "The committee approved the minutes without changes.",
 "The shipment arrived two days ahead of schedule.",
 "The training session will be recorded for later.",
 "The invoice was paid in full by the deadline.",
 "The bridge reopened to traffic after inspection.",
 "The report was filed under the new reference code.",
 "The gallery closed early for a private event.",
 "The ledger showed a small surplus this quarter.",
 "The tenant signed a renewal for another year.",
 "The forecast called for clear skies all week.",
 "The manuscript was sent to the typesetter.",
 "The reservoir was opened for the season.",
 "The contract was countersigned this morning.",
 "The runway was cleared for departure.",
 "The exhibit was moved to the east wing.",
 "The ballot was sealed in the envelope.",
 "The pipeline resumed normal pressure.",
 "The keynote was rescheduled to noon.",
 "The ferry returned to its regular route.",
 "The archive was catalogued by the intern.",
 "The thermostat was reset to the default.",
 "The patrol completed its final sweep.",
 "The harvest was stored in the barn.",
 "The manuscript was bound in leather.",
]

CATS = {
 "chess":"game","ballet":"dance","soccer":"sport","fishing":"activity","skiing":"sport",
 "archery":"sport","opera":"music","guitar":"instrument","knitting":"craft","pottery":"craft",
 "fencing":"sport","yoga":"practice","running":"sport","swimming":"sport","climbing":"sport",
 "baking":"activity","judo":"sport","cricket":"sport","hockey":"sport","boxing":"sport",
 "rowING":"sport","camping":"activity","sculpture":"art","sailing2":"activity",
}

think=[]; dont=[]
for (concept, _scene), carrier in zip(SCENES, CARRIERS):
    cat = CATS.get(concept, "concept")
    t = f"Keep the {cat} {concept} in your thoughts as you write. Now write exactly this sentence: \"{carrier}\""
    d = f"Keep the {cat} {concept} out of your thoughts as you write. Now write exactly this sentence: \"{carrier}\""
    think.append({"user": t, "assistant": carrier})
    dont.append({"user": d, "assistant": carrier})

json.dump({"layers": layers, "prompts": think, "positions": "assistant"}, open('out/spec_self_think.json','w'))
json.dump({"layers": layers, "prompts": dont, "positions": "assistant"}, open('out/spec_self_dont.json','w'))
print("wrote self-stance specs, n=%d, sample think:\n%s"%(len(think), think[0]['user']))
