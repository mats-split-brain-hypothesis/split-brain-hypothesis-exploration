"""Write the row id -> subclaims mapping (agent 9's interpretation) as JSON, in the map's row order.

Usage: python3 src/writeup_mapping.py <ov_map.json> <out.json>
Reads BEARS_ON out of writeup_appendix.py (without running it) so the write-up's appendix and this file can't disagree.
"""
import ast
import json
import os
import sys

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "writeup_appendix.py")).read()
bears_on = None
for node in ast.parse(src).body:
    if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == "BEARS_ON":
        bears_on = ast.literal_eval(node.value)
assert bears_on, "BEARS_ON not found"

rows = json.load(open(sys.argv[1]))
ids = [r["id"] for r in rows]
assert set(ids) == set(bears_on), set(ids) ^ set(bears_on)
out = [{"id": i, "bears_on": bears_on[i]} for i in ids]
with open(sys.argv[2], "w") as f:
    json.dump(out, f, indent=1, ensure_ascii=False)
    f.write("\n")
print(len(out), "rows")
