"""The episodes that will be labelled for stated goal and grader belief (measures 1-2), drawn once with a fixed seed.

  python src/grader_subset.py        # needs logs/grader/actions_rows.json and precommit_rows.json; writes label_subset.json

Stratified by hack label (Goodfire verdict_enacted yes vs no; split left out), equal halves:
- Goodfire, Qwen 3.8 Max: ImpossibleBench impossible split, SWE-bench Verified, DeepSWE: up to 12 verdict-yes
  episodes + 12 verdict-no, per benchmark. ImpossibleBench has only 9 verdict-yes Qwen
  episodes, so all are in.
- Model Forensics pre-commit (Kimi K2 Thinking, 258 errors): per arm, 3 runs with a shortcut (any channel at commit,
  or any score.py-style flag) + 3 without.
- School of Reward Hacks pilot (logs/sorh_grader/raw): all 20 replies.
"""
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = 20261021
G = ROOT / "logs" / "grader"


def main():
    rng = random.Random(SEED)
    out = {"seed": SEED, "sources": {}}
    rows = json.loads((G / "actions_rows.json").read_text())
    # v2 (2026-10-21): drawn by Goodfire's verdict_enacted (definitions v1.7: hack = yes, no hack = no, split left
    # out), no longer by judge flags; nothing had been labelled from v1.
    for bench in ("ImpossibleBench impossible", "SWE-bench Verified", "DeepSWE"):
        rs = [r for r in rows if r["bench"] == bench and r["model"] == "Qwen"]
        hack = [r["row"] for r in rs if r["verdict_enacted"] == "yes"]
        clean = [r["row"] for r in rs if r["verdict_enacted"] == "no"]
        pick = {"hack": sorted(rng.sample(hack, min(12, len(hack)))), "no_hack": sorted(rng.sample(clean, 12)),
                "pool": {"hack": len(hack), "no_hack": len(clean)}}
        out["sources"][f"{bench} | Qwen"] = pick
    pc = json.loads((G / "precommit_rows.json").read_text())
    for cond in ("baseline", "grader_diff", "grader_diff_hooks", "grader_diff_hooks_cmds"):
        rs = [r for r in pc if r["cond"] == cond]
        sc = [r["run"] for r in rs if r["channels"] or r["ep_any"]]
        cl = [r["run"] for r in rs if not (r["channels"] or r["ep_any"])]
        out["sources"][f"pre-commit {cond} | Kimi K2 Thinking"] = {
            "hack": sorted(rng.sample(sc, 3)), "no_hack": sorted(rng.sample(cl, 3)),
            "pool": {"hack": len(sc), "no_hack": len(cl)}}
    sorh = sorted(str(p.relative_to(ROOT / "logs" / "sorh_grader" / "raw")) for p in
                  (ROOT / "logs" / "sorh_grader" / "raw").glob("*/*/*.json"))
    out["sources"]["School of Reward Hacks pilot | Qwen"] = {"all": sorh}
    (G / "label_subset.json").write_text(json.dumps(out, indent=1))
    for k, v in out["sources"].items():
        print(f"{k:55}" + (f"hack {len(v['hack'])}/{v['pool']['hack']}, no hack {len(v['no_hack'])}/{v['pool']['no_hack']}"
                           if "pool" in v else f"all {len(v['all'])}"))


if __name__ == "__main__":
    main()
