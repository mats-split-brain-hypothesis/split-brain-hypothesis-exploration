import sys, json, torch
sys.path.insert(0, "tools"); sys.path.insert(0, ".")
import metric

# try bench_items capture for basic_readout (other family)
for fam, split, ids in [
    ("basic_readout", "bench", ["br-ent-ath-ali", "br-ent-ath-brady"]),
    ("association", "bench", ["chess", "golf"]),
    ("directed_modulation", "bench", ["dm-pair-00-pos", "dm-pair-00-neg"]),
]:
    try:
        o = metric.capture({"layers": [22], "bench_items": ids, "family": fam, "split": split})
        print(fam, split, "-> ok, n_prompts", o.get("n_prompts"), "keys", sorted(o.keys()), "mean@22 norm", round(o['mean'][22].norm().item(),2))
    except Exception as e:
        print(fam, split, "-> ERROR:", e)
