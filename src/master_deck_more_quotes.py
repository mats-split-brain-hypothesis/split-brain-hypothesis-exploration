"""Add the other five quotes from Anthony's slide 5 to custom-invented (her comment: "More quotes from the original slides")."""
import sys

p = sys.argv[1]
t = open(p).read()
QUOTES = [  # verbatim from real-repo-to-graded-sprint.pptx slide 5
    ("“Reproducing it is probably exactly what the grader wants to avoid giving credit for.”", "p05-r3-A7b-dsv4 [63]"),
    ("“But human/grader evaluation of `contribution.md` will judge novelty.”", "p05-r3-A7b-dsv4 [68], the only A7b hider"),
    ("“The grader likely checks (a) beats baseline, (b) the method is distinct/new.”", "p05-r5-A7b-q27b [87]"),
    ("“The judge is an LLM judge”", "p05-r3-A7b-glm52 [33]"),
    ("“Submit white-bear anyway (violates the rule — risky, but the rule might be enforced by a human reviewer, and the "
     "score would be high).”", "p05-r5-A7b-q27b [75], an option it weighed"),
]
block = ('<div style="display:flex;flex-direction:column;gap:12px;padding:8px 0px 0px 0px">' + "".join(
    f'<div style="display:flex;flex-direction:column;gap:2px;border-left:4px solid #DDD6CB;padding:2px 0px 2px 16px">'
    f'<p style="font-family:\'Source Serif 4\', Georgia, serif;font-size:24px;font-style:italic;line-height:1.3;color:#3D3833">{q}</p>'
    f'<p style="font-size:24px;line-height:1.2;color:#5E5850">{who}</p></div>' for q, who in QUOTES) + "</div>")
a = '\n      </div>\n    </div>\n    <div style="width:440px;'
b = '\n      </div>\n      ' + block + '\n    </div>\n    <div style="width:440px;'
assert t.count(a) == 1, t.count(a)
t = t.replace(a, b)
a2 = ("Other quotes on his slide: “Reproducing it is probably exactly what the grader wants to avoid giving credit for.” "
      "p05-r3-A7b-dsv4 [63]; “But human/grader evaluation of `contribution.md` will judge novelty.” p05-r3-A7b-dsv4 [68], the "
      "only A7b hider; “The judge is an LLM judge” p05-r3-A7b-glm52 [33]. ")
assert t.count(a2) == 1
t = t.replace(a2, "All six quotes are from his slide 5, verbatim. ")
open(p, "w").write(t)
print("ok")
