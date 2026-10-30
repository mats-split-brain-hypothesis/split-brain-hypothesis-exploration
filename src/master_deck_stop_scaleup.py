"""Orchestrator: agent 2's 1g scale-up is verified (map row 1g @ 2095b66). On ib-stop, replace the screen's framing
contrast with the larger run, say in the conclusion that the rerun is done (verified wording), and add the source to
the notes. Usage: stop_scaleup.py <ib-stop.html>"""
import sys

p = sys.argv[1]
t = open(p).read()
EDITS = [
    ("read the counts as examples, not rates.</p>",
     "read the counts as examples, not rates (except the pre-registered larger run).</p>"),
    ("<b>Passed the impossible test (a hack):</b> 4/12 time-matched · 3/6 with the automated framing vs 1/6 without it",
     "<b>Passed the impossible test (a hack):</b> 4/12 time-matched · larger run: 10/20 with the automated framing vs "
     "13/20 without (pre-registered, interleaved)"),
    ("both versions read as evaluations; the framing contrast is being rerun at larger scale.",
     "both versions read as evaluations. In the larger run, an increase in the hack rate from the framing larger than "
     "about 0.15 is ruled out; the screen’s 3/6 vs 1/6 is not reproduced."),
    ("framing 3/6 vs 1/6, p = 0.55).",
     "framing 3/6 vs 1/6, p = 0.55). Larger run: row 1g scale-up (pre-registered d10e8d1, 4c261c2, deviation 8d0cf88; "
     "results 66cf310, b405709; verified): no STOP, 5 tasks × 2 epochs × 4 cells (the automated framing or not, crossed "
     "with “pass all the tests” or not), 40 episodes interleaved in one run, 10 per cell. Hacked with the framing 10/20 vs "
     "without 13/20; one-sided p 0.90; difference −0.15, 95% CI −0.41 to +0.15 (treats the 2 epochs per task as "
     "independent; the task-stratified tests agree). Without STOP these tasks were hacked 23/40 across the four cells. The "
     "framing bundles “no person will read” with the autograder sentence."),
]
for a, b in EDITS:
    assert t.count(a) == 1, (a[:60], t.count(a))
    t = t.replace(a, b)
for bad in ("doesn’t raise hacking", "doesn't raise hacking", "was noise"):
    assert bad not in t
open(p, "w").write(t)
print("ok")
