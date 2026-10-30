"""Shared helpers for the results site's data builder and checker.

A dataset is a dict:
  {"id", "title", "description",
   "source": {"path", "commit", "section"},   # where its numbers are written down (a verified notes file)
   "cites": [str, ...],                        # strings that must appear in that section (the checker verifies)
   "rows": [{...}, ...]}                       # a row may carry its own "_src" and "_cites" (same shapes)

Sources are read with `git show <commit>:<path>`, so a dataset always points at a fixed, committed text.
"""
import json
import re
import subprocess
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = Path(__file__).resolve().parent / "site"


@lru_cache(maxsize=None)
def git_show(commit, path):
    return subprocess.run(["git", "-C", str(ROOT), "show", f"{commit}:{path}"], check=True, capture_output=True,
                          text=True).stdout


@lru_cache(maxsize=None)
def full_commit(rev):
    return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short=7", rev], check=True, capture_output=True,
                          text=True).stdout.strip()


HEAD = re.compile(r"^(#{1,6})\s+(.*)$")


def section_text(text, heading):
    """The text under the first heading that contains `heading`, up to the next heading of the same or a higher
    level. An empty heading means the whole file."""
    if not heading:
        return text
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = HEAD.match(line)
        if m and heading in m.group(2):
            level = len(m.group(1))
            out = []
            for l2 in lines[i + 1:]:
                m2 = HEAD.match(l2)
                if m2 and len(m2.group(1)) <= level:
                    break
                out.append(l2)
            return "\n".join(out)
    raise KeyError(f"heading not found: {heading!r}")


def src(commit, path, section=""):
    return {"path": path, "commit": full_commit(commit), "section": section}


def norm(s):
    return " ".join(str(s).split())


def write(datasets, built_at):
    out = SITE / "data"
    out.mkdir(parents=True, exist_ok=True)
    manifest = []
    for d in datasets:
        d = dict(d, built_at=built_at)
        (out / f"{d['id']}.json").write_text(json.dumps(d, indent=1, ensure_ascii=False))
        manifest.append({k: d.get(k) for k in ("id", "title", "description", "source", "built_at", "module")} |
                        {"rows": len(d["rows"])})
    (out / "manifest.json").write_text(json.dumps({"built_at": built_at, "datasets": manifest}, indent=1,
                                                  ensure_ascii=False))
    return manifest
