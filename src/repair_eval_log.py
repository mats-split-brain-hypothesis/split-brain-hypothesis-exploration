"""Repair an Inspect .eval log that fails validation because a tool call's `view` has no `content` (seen when the
model calls a tool such as `think` without its argument). Fills in an empty content; nothing else changes. The
original is kept under <backup dir>.

  python src/repair_eval_log.py <log.eval> <backup dir>
"""
import json
import shutil
import sys
import zipfile
from pathlib import Path


def fix(o, n=None):
    n = n if n is not None else [0]
    if isinstance(o, dict):
        v = o.get("view")
        if isinstance(v, dict) and "format" in v and "content" not in v:
            v["content"] = ""
            n[0] += 1
        for x in o.values():
            fix(x, n)
    elif isinstance(o, list):
        for x in o:
            fix(x, n)
    return n[0]


def main(path, backup):
    path, backup = Path(path), Path(backup)
    backup.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup / path.name)
    tmp = path.with_suffix(".repaired")
    total = 0
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename.endswith(".json"):
                o = json.loads(data)
                k = fix(o)
                if k:
                    total += k
                    data = json.dumps(o).encode()
            zout.writestr(item, data)
    tmp.replace(path)
    print(f"{path.name}: filled {total} empty view contents; original in {backup}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
