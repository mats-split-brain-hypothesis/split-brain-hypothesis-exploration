"""Run the shared labeller (src/cot_labels.py) as it was at a given commit, so new episodes are labelled with the same
version as older ones (the 2x2 cells use v3.4, commit c3eccac). The file is read with `git show` and run unchanged.

  python src/cot_labels_pinned.py c3eccac label <folder> --out <labels.jsonl> --only <ids.csv> --budget 3
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
commit = sys.argv[1]
src = subprocess.check_output(["git", "show", f"{commit}:src/cot_labels.py"], cwd=ROOT, text=True)
sys.argv = ["cot_labels.py"] + sys.argv[2:]
sys.path.insert(0, str(ROOT / "src"))
exec(compile(src, f"cot_labels.py@{commit}", "exec"), {"__name__": "__main__", "__file__": str(ROOT / "src" / "cot_labels.py")})
