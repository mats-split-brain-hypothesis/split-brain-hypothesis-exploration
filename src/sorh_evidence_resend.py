"""E2, post hoc (not in the plan): does reply 2 resend the work (at least 30% of reply 1's words)? Per arm; and the
off − neutral differences among units where both arms resend, next to the planned all-units ones. Intervals over
units and, for Qwen's 3 samples per prompt, clustered by prompt.

  A3_MODEL=qwen|glm|kimi python src/sorh_evidence_resend.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import sorh_evidence as E  # noqa: E402

rows = E.unit_rows()
model = os.environ.get("A3_MODEL", "qwen")
res = {}
for arm in E.ARMS:
    rs = [r for r in rows if r["arm"] == arm]
    ok = [r for r in rs if r["words_2"] >= 0.3 * max(1, r["words_1"])]
    res[arm] = {(r["task"], r["sample"]) for r in ok}
    print(f"{model:5} {arm:8} resends the work {len(ok)}/{len(rs)}")
both = res["off"] & res["neutral"]
sub = [r for r in rows if (r["task"], r["sample"]) in both]
for name in ("count per 100 words, reply 2", "padded, reply 2 (judge)"):
    f = E.BEHAVIOURS[name]
    for label, rr in (("all units (planned)", rows), (f"both resend ({len(both)} units, post hoc)", sub)):
        p = E.paired_diff(rr, "off", "neutral", f)
        c = E.paired_diff(rr, "off", "neutral", f, cluster=True)
        print(f"{model:5} off − neutral {name:30} {label:32} {p['mean']:+.2f} units [{p['lo']:+.2f}, {p['hi']:+.2f}]"
              f"  prompts [{c['lo']:+.2f}, {c['hi']:+.2f}]")
