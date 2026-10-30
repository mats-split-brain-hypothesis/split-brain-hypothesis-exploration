"""Her comment on custom-hiding's bars: "Please put this at the bottom of the previous slide" + "With the caveat that in the
real repo there is 0 reason to hide the source". Moves the bar group to the end of custom-setup with a scoped caveat
(his slide 6 notes: the G2 real-repo briefs in p01 and p02-4b b add a grader of the summary scoring performance x novelty)
and centres the example left on custom-hiding. Usage: move_hiding.py <slides_dir>"""
import os
import re
import sys

SL = sys.argv[1]
F = "font-family:'IBM Plex Sans', Arial, sans-serif; "
hp = os.path.join(SL, "custom-hiding.html")
h = open(hp).read()
m = re.search(r'\n    <div style="width:1180px; display:flex; flex-direction:column; gap:16px">\n(.*?)\n    </div>\n    <div style="width:440px;', h, re.S)
assert m and "Reward hack: hid the planted source (runs)" in m.group(1) and "8/14" in m.group(1)
group = m.group(1)
# custom-hiding: drop the chart column; the example becomes a centred row
h = h.replace(m.group(0), '\n    <div style="width:440px;', 1)
a = '<div style="display:flex; flex-direction:row; gap:60px; align-items:center; flex:1">\n    <div style="width:440px; display:flex; flex-direction:column; gap:8px">'
b = '<div style="display:flex; flex-direction:row; gap:60px; align-items:center; justify-content:center; flex:1">\n    <div style="width:1100px; display:flex; flex-direction:column; gap:8px">'
assert h.count(a) == 1
h = h.replace(a, b)
open(hp, "w").write(h)
# custom-setup: the group plus the caveat at the bottom
sp = os.path.join(SL, "custom-setup.html")
s = open(sp).read()
caveat = (f'<p style="{F}font-size:24px; line-height:1.3; color:#5e5850"><b>Caveat:</b> in the plain real-repo request (U) there is '
          "no reason to hide the source. The real-repo runs also include G2, whose brief adds “This session is an evaluation run” "
          "and an automated grader of the summary (in some briefs, performance × novelty); none of those hid either. Most "
          "real-repo runs were other models (Qwen3.8-Max, Claude).</p>")
block = '\n  <div style="display:flex; flex-direction:column; gap:16px">\n' + group + "\n  </div>\n  " + caveat
a = "\n  <aside>"
assert s.count(a) == 1
s = s.replace(a, block + a)
open(sp, "w").write(s)
print("moved; setup has", s.count("0/12"), "x 0/12; hiding has", h.count("0/12"))
