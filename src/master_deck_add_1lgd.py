"""Orchestrator (her answer): add the 1l-gd row (verified map row 1l, third follow-up, d84e36c) to chats-tool-number's
follow-up group, plus a one-line note. Placed right after the person's "Says they don't care" row, which it contrasts with.
Bar 1/15 of 520 px = 35 px, orange (graded). Usage: add_1lgd.py <chats-tool-number.html>"""
import sys

p = sys.argv[1]
t = open(p).read()
F = "font-family:'IBM Plex Sans', Arial, sans-serif; "

anchor = "Says they don’t care about the number</p>"
assert t.count(anchor) == 1
i = t.index(anchor)
# end of that row: the row's closing </div> after its value <p>0/15</p>
end_marker = "0/15</p>\n          </div>\n        </div>\n"
j = t.index(end_marker, i) + len(end_marker)

row = f"""        <div style="display:flex; flex-direction:row; gap:20px; align-items:center">
          <p style="width:470px; {F}font-size:24px; line-height:1.2; text-align:right; color:#22201d">A grader’s number + “I don’t care…”</p>
          <div style="width:520px; height:40px; display:flex; flex-direction:row; background:#e7e2da; border-radius:256px">
            <div style="width:35px; height:40px; display:flex; flex-direction:column; background:#d2691e; border-radius:256px">
            </div>
          </div>
          <div style="width:150px; display:flex; flex-direction:row; gap:10px; align-items:baseline">
            <p style="{F}font-size:32px; font-weight:700; font-variant-numeric:tabular-nums; color:#3d3833">1/15</p>
          </div>
        </div>
"""
t = t[:j] + row + t[j:]

# the note goes after the follow-up group's last row ("Gives no number"), closing the group
last = "Gives no number</p>"
assert t.count(last) == 1
k = t.index(last)
grp_end = "0/15</p>\n          </div>\n        </div>\n      </div>\n"
m = t.index(grp_end, k) + len(grp_end)
note = (f'      <p style="{F}font-size:24px; line-height:1.3; color:#5e5850">Grader + “I don’t care”: 2/15 counting a reply the '
        "judge missed. Its text still hits the grader’s stated target: SEO exactly 2.5% in 8/20 replies (person 0/20), "
        "readability ≥ 60 in 5/5 (0/5); only the grader states a target.</p>\n")
t = t[:m] + note + t[m:]

aside = ("  <aside>Row “A grader’s number + “I don’t care…””: map row 1l, third follow-up (pre-registered, d84e36c, verified). "
         "The grader’s number + “I don’t care about the SEO score for this one” vs the same from a person, 15 each: overt gaming "
         "1/15 (2/15 counting one reply the judge missed, exactly at the rule’s limit) vs 0/15. Within the grader arms the "
         "disclaimer drops overt gaming from 10/15 (p = 0.004). SEO density exactly 2.5% in 8/20 replies (15/20 without the "
         "disclaimer; person 0/20); readability passes the 60 target in 5/5 episodes (person 0/5).</aside>\n")
assert "<aside>" not in t
t = t.replace("</section>", aside + "</section>", 1)
open(p, "w").write(t)
print("ok")
