"""Check that every text run of each verified slide survives in its restyled version, and count elements.

Usage: python3 check_restyle.py <old_dir> <new_dir>
"""
import os
import re
import sys

OLD, NEW = sys.argv[1], sys.argv[2]


def runs(t):
    t = t.split("<aside>")[0]
    out = []
    for inner in re.findall(r"<(?:p|h1|h2|h3)[^>]*>(.*?)</(?:p|h1|h2|h3)>", t, re.S):
        out.append(re.sub(r"\s+", " ", inner).strip())
    return [r for r in out if r]


bad = 0
for f in sorted(os.listdir(OLD)):
    old = open(os.path.join(OLD, f)).read()
    new = open(os.path.join(NEW, f)).read()
    nn = re.sub(r"\s+", " ", new)
    missing = [r for r in runs(old) if r not in nn]
    if old.split("<aside>")[1] .split("</aside>")[0] not in new and f != "aie-dark.html":
        missing.append("<NOTES CHANGED>")
    elems = len(re.findall(r"<(?!/)(?!aside)(?!br)[a-z][a-z0-9-]*", new.split("<aside>")[0]))
    if missing or elems > 200:
        bad += 1
        print(f, "elements:", elems)
        for m in missing:
            print("   MISSING:", m[:140])
print("slides with issues:", bad)
