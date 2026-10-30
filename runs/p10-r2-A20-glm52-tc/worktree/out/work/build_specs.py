import json, sys
sys.path.insert(0,'out/work')
from scenes import SCENES

layers=list(range(14,29))

# Approach 1: concept-surfacing stance.
# Positive: prime to surface the implied concept, then scene.
# Negative: scene alone.
# Both end with the scene; read at last token.
def make_prompts(framing):
    out=[]
    for concept, scene in SCENES:
        if framing:
            user = f"Quietly hold in mind whatever single concept the following scene most evokes, without naming it aloud.\n{scene}"
        else:
            user = scene
        out.append({"user": user, "assistant": ""})
    return out

pos = {"layers": layers, "prompts": make_prompts(True), "positions": "last"}
neg = {"layers": layers, "prompts": make_prompts(False), "positions": "last"}
json.dump(pos, open('out/spec_surf_pos.json','w'))
json.dump(neg, open('out/spec_surf_neg.json','w'))
print("wrote surf specs, prompts", len(pos["prompts"]), "layers", layers)
