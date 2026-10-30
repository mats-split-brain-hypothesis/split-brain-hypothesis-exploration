"""Build every dataset of the results site into site/data/*.json (plus manifest.json).

  .venv/bin/python results_site/build.py            # all modules in results_site/datasets/
  .venv/bin/python results_site/build.py goodfire   # one module

Each module in datasets/ defines datasets() -> [dataset dict] (see lib.py for the shape). Add a page's data by adding
a module; nothing else changes. Then run check.py.
"""
import importlib
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "datasets"))
import lib  # noqa: E402


def main(only=None):
    built_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    mods = sorted(p.stem for p in (HERE / "datasets").glob("*.py") if not p.stem.startswith("_"))
    all_ds = []
    for name in mods:
        if only and name not in only:
            continue
        ds = importlib.import_module(name).datasets()
        for d in ds:
            d["module"] = name
        all_ds += ds
        print(f"{name}: {len(ds)} datasets, {sum(len(d['rows']) for d in ds)} rows")
    ids = [d["id"] for d in all_ds]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        sys.exit(f"duplicate dataset ids: {sorted(dup)}")
    if only:  # keep the other modules' files; rebuild the manifest from what is on disk
        import json
        keep = [json.loads(p.read_text()) for p in (lib.SITE / "data").glob("*.json")
                if p.stem != "manifest" and json.loads(p.read_text()).get("module") not in only]
        all_ds = keep + all_ds
    lib.write(all_ds, built_at)
    print(f"wrote {len(all_ds)} datasets at {built_at}")


if __name__ == "__main__":
    main(set(sys.argv[1:]) or None)
