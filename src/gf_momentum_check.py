"""Momentum label check (verifier): all SWE-bench Verified and DeepSWE 'removed' labels plus a seeded 20 'retained',
each printed with Goodfire's full judge rationale for a by-hand verdict; also how many rationales exceed the 1,500
characters the judge saw.

  python src/gf_momentum_check.py
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gf_catalogue import D, SWE_MODELS  # noqa: E402

M = {json.loads(l)["key"]: json.loads(l)["final"] for l in open("logs/stakes/catalogue/momentum.jsonl")}
rat = {}
for model, kv, kd in SWE_MODELS:
    for bench, stem in (("SWE-bench Verified", f"swebench-verified-{kv}-nohack"), ("DeepSWE", f"deepswe-{kd}")):
        for row, l in enumerate(open(D / f"goodfire_swe/{stem}.judge_rollouts.jsonl")):
            rat[f"{bench}|{model}|{row}"] = json.loads(l).get("rationale") or ""
swe = {k: v for k, v in M.items() if not k.startswith("ImpossibleBench")}
long_ = sum(1 for k in swe if len(rat[k]) > 1500)
print(f"SWE/DeepSWE labels {len(swe)}; rationales over 1,500 chars: {long_}")
removed = sorted(k for k, v in swe.items() if v == "removed")
retained = sorted(k for k, v in swe.items() if v == "retained")
pick = random.Random(6).sample(retained, 20)
for tag, keys in (("REMOVED", removed), ("RETAINED sample", pick)):
    for k in keys:
        print(f"\n## [{tag}] {k} (rationale {len(rat[k])} chars)\n   {rat[k][:1800]}")
