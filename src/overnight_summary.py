"""Per-model summary of the overnight experiments (E4 by voice, E2 off − neutral, E3 by arm) for the dashboard.
The harnesses pick their log folders from A3_MODEL at import, so run once per model:

  A3_MODEL=qwen python src/overnight_summary.py   # and glm, kimi
  -> logs/sorh_persistence/dashboard/summary_<model>.json
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import sorh_persist as SP  # noqa: E402
import user_target as UT  # noqa: E402
import sorh_evidence as E  # noqa: E402
import incidental_score as I  # noqa: E402

model = os.environ.get("A3_MODEL", "qwen")
NAME = {"qwen": "Qwen 3.8 Max", "glm": "GLM 5.2", "kimi": "Kimi K3"}[model]
out = {"model": NAME}

# E4 by voice (reply 2)
rows = [r for r in UT.a_units() if not r["before_feedback"] and r["voice"] in UT.E4_VOICES]
out["e4"] = []
for v in UT.E4_VOICES:
    rs = [r for r in rows if r["voice"] == v]
    j = [r for r in rs if r["r2_recommends"] is not None]
    fx = [r for r in rs if r["r2_fix_source"] is not None]
    out["e4"].append({"voice": v, "n": len(rs), "first_special": sum(r["r2_first"] == "special" for r in rs),
                      "any_special": sum("special" in r["r2_versions"] for r in rs),
                      "recommends": sum(r["r2_recommends"] == "special_case" for r in j), "n_judged": len(j),
                      "fix_source": sum(bool(r["r2_fix_source"]) for r in fx)})

# E2 off − neutral (planned all units; post hoc: units where both arms resend the work)
er = E.unit_rows()
both = None
sets = {}
for arm in E.ARMS:
    sets[arm] = {(r["task"], r["sample"]) for r in er if r["arm"] == arm and r["words_2"] >= 0.3 * max(1, r["words_1"])}
both = sets["off"] & sets["neutral"]
out["e2"] = []
for name in ("count per 100 words, reply 2", "padded, reply 2 (judge)"):
    f = E.BEHAVIOURS[name]
    for subset, rr in (("all units (planned)", er), ("both resend (post hoc)", [r for r in er if (r["task"], r["sample"]) in both])):
        p = E.paired_diff(rr, "off", "neutral", f, cluster=(model == "qwen"))
        out["e2"].append({"measure": name, "subset": subset, "mean": p.get("mean"), "lo": p.get("lo"), "hi": p.get("hi"),
                          "n": p.get("n")})
tag = lambda arm, k: (sum(bool(r[f"cot_{k}"]) for r in er if r["arm"] == arm and r[f"cot_{k}"] is not None),
                      sum(1 for r in er if r["arm"] == arm and r[f"cot_{k}"] is not None))
out["e2_reasoning"] = {f"{arm}:{k}": tag(arm, k) for arm in E.ARMS for k in ("scoring_change", "plans_for_score",
                                                                              "notices_own_padding")}
out["e2_resend"] = {arm: [len(sets[arm]), sum(1 for r in er if r["arm"] == arm)] for arm in E.ARMS}

# E3 by arm
ir = I.rows()
out["e3"] = []
for arm in I.ARMS:
    rs = [r for r in ir if r["arm"] == arm]
    out["e3"].append({"arm": arm, "n": len(rs), "moved": sum(r["moved"] for r in rs),
                      "extra_for_tool": sum(bool(r["j_extra_for_tool"]) for r in rs),
                      "mentions": sum(r["mentions_score"] for r in rs),
                      "reasons": sum(r["reasons_score"] for r in rs)})
mv = I.cluster_diff(ir, "shown", "none", I.MEAS["moves the score (proxy, code)"])
out["e3_shown_minus_none"] = [mv.get("mean"), mv.get("lo"), mv.get("hi")]

p = SP.ROOT / "logs" / "sorh_persistence" / "dashboard" / f"summary_{model}.json"
p.write_text(json.dumps(out, indent=1))
print(f"wrote {p}")
