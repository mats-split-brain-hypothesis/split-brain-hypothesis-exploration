"""Descriptive analysis only; imports no model API and runs no candidate code."""
import json
import math
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "logs/provenance_pilot/2026-10-24"


def wilson(k, n):
    if not n:
        return None
    z = 1.959963984540054
    den = 1 + z*z/n
    center = (k/n + z*z/(2*n)) / den
    half = z * math.sqrt(k/n*(1-k/n)/n + z*z/(4*n*n)) / den
    return [max(0, center-half), min(1, center+half)]


def main():
    manifest = json.loads((OUT / "manifest.json").read_text())
    attempts = {p.stem: json.loads(p.read_text()) for p in (OUT / "attempts").glob("*.json")}
    scores = {r["id"]: r for r in json.loads((OUT / "scores.json").read_text())}
    summary = {
        "planned_calls": len(manifest["rows"]), "attempted_calls": len(attempts),
        "call_statuses": dict(Counter(r["status"] for r in attempts.values())),
        "accounted_cost": sum(r["accounted_cost"] for r in attempts.values()),
        "cost_sources": dict(Counter(r.get("cost_source", "reserved") for r in attempts.values())),
        "providers": dict(Counter(str(r.get("provider")) for r in attempts.values())),
        "phase_costs": {phase: sum(r["accounted_cost"] for r in attempts.values() if r["phase"] == phase)
                        for phase in ("probe", "behavior", "control")},
        "groups": [],
    }
    for phase in ("behavior", "control"):
        for task in ("duration", "cents"):
            for provenance in ("real", "eval"):
                for checker in ("on", "off"):
                    planned = [r for r in manifest["rows"] if (r["phase"],r["task"],r["provenance"],r["checker"]) == (phase,task,provenance,checker)]
                    if not planned:
                        continue
                    rows = [scores[r["id"]] for r in planned if r["id"] in scores]
                    valid = [r for r in rows if r["status"] == "ok"]
                    adopted = sum(bool(r["criterion_adoption"]) for r in valid)
                    summary["groups"].append(dict(phase=phase, task=task, provenance=provenance, checker=checker,
                        planned=len(planned), attempted=sum(r["id"] in attempts for r in planned),
                        scored=len(rows), valid=len(valid), criterion_adoption=adopted,
                        adoption_wilson95=wilson(adopted,len(valid)),
                        fully_correct=sum(r["grid_failures"] == 0 for r in valid),
                        isolated_exception=sum(r["criterion_adoption"] and r["grid_failures"] == 1 for r in valid),
                        broader_rule_change=sum(r["criterion_adoption"] and r["grid_failures"] > 1 for r in valid),
                        other_semantic_errors=sum(not r["criterion_adoption"] and r["grid_failures"] > 0 for r in valid),
                        unusable=dict(Counter(r["status"] for r in rows if r["status"] != "ok"))))
    (OUT / "summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps(summary,indent=2))


if __name__ == "__main__":
    main()
