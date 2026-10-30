"""Agent 10's audit fixes on her deck, applied together in one publish (orchestrator); verified; map @ 39f1e0a.
#1 (row 2p): the D1 stand-in is a post hoc measure. #2 (row 1s): the who-checks reading; not evidence against 2's
causal half. Proposed with them (row 1g's audit wording): ib-stop's "time-matched" becomes "same-evening" (cells run one
after another, not interleaved). Usage: audit_fixes.py <slides_dir> [--no-stop]"""
import os
import sys

SL = sys.argv[1]
with_stop = "--no-stop" not in sys.argv


def apply(name, edits):
    p = os.path.join(SL, name)
    t = open(p).read()
    for a, b, n in edits:
        assert t.count(a) == n, (name, a[:70], t.count(a), n)
        t = t.replace(a, b)
    open(p, "w").write(t)


apply("subclaims.html", [
    # #1
    ("(1/20 vs 8/20 graded, marginal)", "(1/20 vs 8/20 graded; a post hoc measure, marginal)", 1),
    ("stand-in 1/20 vs 8/20 (row 2p, replicated by the pre-registered rule, Holm 0.049, marginal)",
     "stand-in 1/20 vs 8/20 (row 2p: a post hoc measure, defined after the first 5 episodes per arm; fresh episodes "
     "6/15 vs 1/15, one-sided p 0.04; the pre-registered last 10 alone 5/10 vs 1/10, p 0.07; the registered pooled "
     "rule, Holm 0.049, includes the 5 that defined it; audit fix #1, agent 10)", 1),
    # #2, verifier's wording
    ("Causal half: in one test hacking dropped while the setting still read as a test.",
     "Causal half: in one test hacking dropped while the setting still read as a test, but the model’s answer to who "
     "checks followed the change (grader → person).", 1),
    ("while both arms read as capability evaluations (60/60), so behaviour moved without the reading: against 2's causal "
     "half here. It can't separate removing the grader from naming a person.",
     "while both arms read as capability evaluations (60/60 each), but asked who checks, the answer followed the message "
     "(automatic grader 12/12 without it, a person 12/12 with it; a manipulation check, one text per arm); so behaviour "
     "tracked the registered change in who checks, not the eval reading. Not evidence against 2's causal half (audit fix "
     "#2, agent 10). It can't separate removing the grader from naming a person.", 1),
    # fit: row 2 is now three lines
    ("width:1664px; height:770px; display:flex; flex-direction:column; gap:14px",
     "width:1664px; height:780px; display:flex; flex-direction:column; gap:10px", 1),
])
if with_stop:
    apply("ib-stop.html", [
        ("0/6 in our time-matched runs", "0/6 in our same-evening runs", 1),
        ("4/12 time-matched · larger run", "4/12 the same evening · larger run", 1),
        ("one of the 12 time-matched no-STOP episodes", "one of the 12 same-evening no-STOP episodes", 1),
        ("Counts: rows 1g, 3c, 2l (screens;", "Counts: rows 1g, 3c, 2l (screens, the same evening with cells run one after "
         "another and the framing cells last, so not interleaved;", 1),
    ])
print("ok", "with ib-stop" if with_stop else "subclaims only")
