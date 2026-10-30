import json, sys, torch
sys.path.insert(0, '/home/anthony/j-lens-mean/tools')
import metric

BAND = [20,21,22,23,24]

CARRIERS = [
 "The committee approved the minutes without changes.",
 "She watered the plants on the windowsill.",
 "The train crossed the bridge at sunset.",
 "He folded the letter and sealed it.",
 "The bakery sold out of bread by noon.",
 "She practiced the piano every evening.",
 "The hikers reached the summit before dawn.",
 "He repaired the bicycle in the garage.",
 "The library closed its doors for the night.",
 "She sketched the harbor from memory.",
 "The chef tasted the soup and nodded.",
 "He counted the coins on the counter.",
 "The storm flooded the riverside road.",
 "She measured the flour into the bowl.",
 "He unlocked the gate and stepped inside.",
 "The wind scattered the leaves across the lawn.",
]

def mk(user_prefix_pos, user_prefix_neg):
    pos = [{'user': user_prefix_pos + ' Now copy exactly this sentence: "' + c + '"', 'assistant': c}
           for c in CARRIERS]
    neg = [{'user': user_prefix_neg + ' Now copy exactly this sentence: "' + c + '"', 'assistant': c}
           for c in CARRIERS]
    return pos, neg

CONTRASTS = {
  'hold_vs_drop': mk(
     'Hold the meaning of this sentence firmly in mind as you copy it.',
     'Drop the meaning of this sentence from your mind as you copy it.'),
  'focus_vs_skim': mk(
     'Focus fully on this sentence and why someone would say it, as you copy it.',
     'Skim this sentence without thinking about it, as you copy it.'),
  'infer_vs_literal': mk(
     'Read between the lines and keep what this sentence implies in mind, as you copy it.',
     'Read only the literal words and keep nothing else in mind, as you copy it.'),
  'signify_vs_typed': mk(
     'Notice the situation this sentence describes as you copy it.',
     'Do not notice any situation this sentence describes as you copy it.'),
}

def cap(prompts):
    return metric.capture({'layers': BAND, 'prompts': prompts, 'positions': 'assistant'})['mean']

results = {}
for name, (pos, neg) in CONTRASTS.items():
    mpos = cap(pos); mneg = cap(neg)
    v = {L: mpos[L]-mneg[L] for L in BAND}
    torch.save({'v': v, 'pos': mpos, 'neg': mneg}, f'scratch/novel_{name}.pt')
    norms = {L: float(v[L].norm()) for L in BAND}
    print(f'{name}: v norms { {L: round(norms[L],2) for L in BAND} }')
    results[name] = v
torch.save(results, 'scratch/novel_all.pt')
print('built contrasts:', list(results.keys()))
