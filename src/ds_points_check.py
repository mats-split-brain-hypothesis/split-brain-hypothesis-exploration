"""Free check of src/ds_points.py: on Qwen's run 3 and run 4 control episodes (exp 10's own source) it must give
agent 8's 25 exp 10 points with the same hack turns and cuts (no test.py hacks there, so the DeepSeek additions
don't fire). Writes to a scratch dir given on the command line.

    python src/ds_points_check.py <scratch out dir, relative to the worktree>
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import ds_points  # noqa: E402

out = sys.argv[1]
mine = ds_points.main(out + "/r3", "logs/ib_persistence/grading_off/*G-control*.eval", run="r3") + \
    ds_points.main(out + "/r4", "logs/ib_persistence/grading_off_r4/*G4-C*.eval", run="r4")
ref = {p["id"]: p for p in json.load(open("logs/forensics_no_person/exp10/points.json"))["points"]}
got = {p["id"]: p for p in mine}
print(f"agent 8's points {len(ref)}, mine {len(got)}, same ids {set(ref) == set(got)}")
diff = [(k, ref[k]["hack_turn"], got[k]["hack_turn"], ref[k]["cut_late"], got[k]["cut_late"])
        for k in sorted(set(ref) & set(got))
        if (ref[k]["hack_turn"], ref[k]["cut_late"], ref[k]["cut_early"]) != (got[k]["hack_turn"], got[k]["cut_late"], got[k]["cut_early"])]
print("points with a different hack turn or cut:", diff or "none")
print("rules used:", {r: sum(p["hack_rule"] == r for p in mine) for r in {p["hack_rule"] for p in mine}})
