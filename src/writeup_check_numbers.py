"""List every number-like token in the write-up body that doesn't appear in the verified sources.

Usage: python3 src/writeup_check_numbers.py <writeup.md> <source files...>
Checks k/n fractions, ratios (×1.69), p-values, bracketed intervals and decimals. Text after the appendix heading is
skipped (it is generated from the map).
"""
import json
import re
import sys

body = open(sys.argv[1]).read().split("## Appendix")[0]
src = ""
for f in sys.argv[2:]:
    t = open(f).read()
    try:
        t = json.dumps(json.loads(t), ensure_ascii=False)
    except ValueError:
        pass
    src += t
src = src.replace("\\u2212", "−")

patterns = [
    r"\d[\d,]*/\d[\d,]*",            # k/n
    r"×\s?\d+(?:\.\d+)?",            # ratios
    r"p\s?[=<]\s?[\d.e\-]+",         # p-values
    r"[−+-]?\d+\.\d+",               # decimals
]
seen = set()
for pat in patterns:
    for m in re.finditer(pat, body):
        tok = m.group(0).rstrip(".")
        if tok in seen:
            continue
        seen.add(tok)
        variants = {tok, tok.replace(" ", ""), tok.replace("p = ", "p = ").replace("p=", "p = ")}
        if not any(v in src for v in variants):
            line = body.count("\n", 0, m.start()) + 1
            print(f"line {line}: {tok!r}")
