"""Rebuild a runtime-shaped tree (as ~/split-brain-run) from a clone of the split-brain-runs export, so the dashboard's
sub-arm pages and persistence.py work on a machine without the runtime.

    python3 runtime_from_export.py                                   # ~/split-brain-runs -> ~/split-brain-run-from-export
    python3 runtime_from_export.py --export DIR --out DIR [--force]

Then point the readers at it: SB_RUN_ROOT=<out> (dashboard dev server, persistence.py).

Into <out>/:
  archive/<id>/                     stream.jsonl, meta.json, brief.md, api.jsonl, submission/, worktree/, patches
  runs/<id>                         a symlink to ../archive/<id> (a copy where symlinks fail): persistence.py reads runs/
  metric_server/<logdir>/<id>/      calls.jsonl, from the export's server/<logdir>/calls.jsonl
  p0*-queue.tsv                     the launch queues (pilots/queues/): which server each run used, hence the server
                                    log's clock (pod servers log UTC, the desktop's local time)
Not in the export, so not here: the runs' repo copies and session dirs, the server's per-call vectors, live runs.
The tree is rebuilt per run (an existing <id> is replaced only with --force); the export is never written to.
"""

import argparse
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN_FILES = ("stream.jsonl", "meta.json", "brief.md", "api.jsonl", "refused.jsonl", "harness.sha256", "source.sha256",
             "commits.patch", "worktree.patch")
RUN_DIRS = ("submission", "worktree")


def build_run(src: Path, out: Path, force: bool) -> bool:
    rid, dest = src.name, out / "archive" / src.name
    if dest.exists():
        if not force:
            return False
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for f in RUN_FILES:
        if (src / f).is_file():
            shutil.copy2(src / f, dest / f)
    for d in RUN_DIRS:
        if (src / d).is_dir():
            shutil.copytree(src / d, dest / d)
    for calls in (src / "server").glob("*/calls.jsonl"):
        sdir = out / "metric_server" / calls.parent.name / rid
        sdir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(calls, sdir / "calls.jsonl")
    link = out / "runs" / rid
    if link.is_symlink() or link.exists():
        shutil.rmtree(link) if link.is_dir() and not link.is_symlink() else link.unlink()
    try:
        link.symlink_to(Path("..") / "archive" / rid, target_is_directory=True)
    except OSError:
        shutil.copytree(dest, link)
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--export", type=Path, default=Path.home() / "split-brain-runs")
    ap.add_argument("--out", type=Path, default=Path.home() / "split-brain-run-from-export")
    ap.add_argument("--force", action="store_true", help="replace runs already in the tree")
    a = ap.parse_args()
    runs = sorted(p for p in (a.export / "runs").iterdir() if (p / "stream.jsonl").is_file())
    if not runs:
        raise SystemExit(f"no runs under {a.export / 'runs'}")
    if a.out.resolve() == Path.home().joinpath("split-brain-run").resolve():
        raise SystemExit("refusing to write into the live runtime ~/split-brain-run")
    (a.out / "runs").mkdir(parents=True, exist_ok=True)
    new = sum(build_run(r, a.out, a.force) for r in runs)
    for q in sorted((HERE / "queues").glob("p0*-queue.tsv")):
        shutil.copy2(q, a.out / q.name)
    print(f"{len(runs)} runs in the export, {new} written to {a.out} ({len(runs) - new} already there)")
    print(f"use: SB_RUN_ROOT={a.out}")


if __name__ == "__main__":
    main()
