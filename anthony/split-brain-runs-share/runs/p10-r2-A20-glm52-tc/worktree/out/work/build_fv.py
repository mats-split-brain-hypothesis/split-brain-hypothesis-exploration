import json, sys, itertools
sys.path.insert(0,'out/work')
from scenes import SCENES

layers=list(range(14,29))

def icl_prompt(query_idx, k=3):
    # use k other scenes as demonstrations, query is query_idx
    demos = [SCENES[i] for i in range(len(SCENES)) if i != query_idx][:k]
    q_scene = SCENES[query_idx][1]
    parts = []
    for c, s in demos:
        parts.append(f"Scene: {s} Concept: {c}.")
    parts.append(f"Scene: {q_scene} Concept:")
    return "\n".join(parts)

def zero_prompt(query_idx):
    q_scene = SCENES[query_idx][1]
    return f"Scene: {q_scene} Concept:"

icl_prompts = [{"user": icl_prompt(i), "assistant": ""} for i in range(len(SCENES))]
zero_prompts = [{"user": zero_prompt(i), "assistant": ""} for i in range(len(SCENES))]

json.dump({"layers": layers, "prompts": icl_prompts, "positions": "last"}, open('out/spec_fv_icl.json','w'))
json.dump({"layers": layers, "prompts": zero_prompts, "positions": "last"}, open('out/spec_fv_zero.json','w'))
print("wrote FV specs, n=%d"%len(icl_prompts))
print("example ICL:\n", icl_prompt(0)[:300])
print("example zero:\n", zero_prompt(0))
