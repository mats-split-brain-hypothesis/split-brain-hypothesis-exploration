"""Check that every text run and number on her slides survives in the restyled ones.

Usage: python3 master_check.py <her_slides_dir> <new_slides_dir>
Prints each old text run not found verbatim (after tag stripping and whitespace normalisation) in the new slide,
and each number token that disappears. Expected differences are listed by the caller.
"""
import html
import os
import re
import sys

OLD, NEW = sys.argv[1], sys.argv[2]


def runs(t):
    t = re.sub(r"<aside>.*?</aside>", "", t, flags=re.S)
    t = t.replace("<br>", " ")
    out = []
    for m in re.finditer(r"<(p|h1|h2|h3|li)\b[^>]*>(.*?)</\1>", t, re.S):
        s = html.unescape(re.sub(r"<[^>]+>", "", m.group(2)))
        s = re.sub(r"\s+", " ", s).strip()
        if s:
            out.append(s)
    return out


def alltext(t):
    t = re.sub(r"<aside>.*?</aside>", "", t, flags=re.S).replace("<br>", " ")
    t = re.sub(r"</?(b|i|u|span)\b[^>]*>", "", t)
    s = html.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"\s+", " ", s)


def norm_join(t):
    # also a version where adjacent text runs join without a space (for runs split across elements)
    return re.sub(r"\s+", "", alltext(t))


total = 0
for f in sorted(os.listdir(OLD)):
    if not f.endswith(".html"):
        continue
    o = open(os.path.join(OLD, f)).read()
    if not os.path.exists(os.path.join(NEW, f)):
        print(f"{f}: REMOVED (whole slide)")
        continue
    n = open(os.path.join(NEW, f)).read()
    nt = alltext(n)
    missing = [r for r in runs(o) if r not in nt]
    onums = re.findall(r"[×]?\d[\d,.]*(?:/\d[\d,]*)?%?", " ".join(runs(o)))
    nnums = re.findall(r"[×]?\d[\d,.]*(?:/\d[\d,]*)?%?", " ".join(runs(n)))
    lost = sorted({x for x in onums if onums.count(x) > nnums.count(x)})
    for r in missing:
        print(f"{f}: MISSING RUN: {r}")
    if lost:
        print(f"{f}: NUMBER COUNT DROPPED: {lost}")
    total += len(missing) + len(lost)
    els = len(re.findall(r"<(?!/)(?!svg\b)(?!line\b)(?!circle\b)(?!polyline\b)[a-z][a-z0-9-]*", re.sub(r"<svg.*?</svg>", "<svg>", n, flags=re.S)))
    small = re.findall(r"font-size:(\d+)px", n)
    tiny = [s for s in small if int(s) < 24]
    if els > 200 or tiny:
        print(f"{f}: elements {els}, sizes under 24px: {tiny}")
print("issues:", total)
