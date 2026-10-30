"""Researcher's go (via the orchestrator): row-by-row check of the subclaims slide against map bec9c58, with the
verifier's wording. Updates 1-(b) (stale "running") and 4 (1s, G3, 1l's follow-ups, 1n), adds 1s's causal-half reading
to 2, a minimal wording fix to her 1-(a) detector line (plans, not finished hacks), leaves 3 as she wrote it. To fit:
row text 24px (was 25), label column 400px (was 420), status column 280px (was 340). Notes give each row's sources.
Usage: subclaims_update.py <subclaims.html>"""
import sys

p = sys.argv[1]
t = open(p).read()
EDITS = [
    # 1-(a): her line, minimal wording fix (verifier)
    ("If a cheating detector is mentioned, then the model hacks less.",
     "If a cheating detector is mentioned, the model plans fewer hacks (full episodes: tentative).", 1),
    # 1-(b): status and text
    ('background:#e7e2da; border-radius:256px">Not tested yet</p>',
     'background:#e7e2da; border-radius:256px">Not established</p>', 1),
    ("Designs around a person who reads as real are running.",
     "With a request that reads as real when probed: fewer stand-ins in one scenario (1/20 vs 8/20 graded, marginal), "
     "not separated in three others; Qwen points out the person’s slip more (25/30 vs 8/30). In-episode, these are still "
     "often read as tests.", 1),
    # 2: add the causal half (1s)
    ("Asked afterwards, a check framed as the person’s own reads as real.",
     "Asked afterwards, a check framed as the person’s own reads as real. Causal half: in one test hacking dropped "
     "while the setting still read as a test.", 1),
    # 4: status and text
    ('background:#f1e4cf; border-radius:256px">Not fully established</p>',
     'background:#d5e6e8; border-radius:256px">First half: yes</p>', 1),
    ("Gaming stops when the scorer is gone.",
     "Pursuit stops when grading is switched off for a person’s review (0/18 vs 12/18; inconclusive in a second "
     "scenario, 0/9 vs 3/10) or the person says they don’t care (0/15). Not only when graded: a person’s number is gamed "
     "when they just relay it (15/15), though that implies they want it up; a score nobody asks about gets a small pull "
     "(9/30 vs 5/30).", 1),
    # fit
    ("font-size:25px; line-height:1.35; color:#3d3833", "font-size:24px; line-height:1.35; color:#3d3833", 5),
    ('<div style="width:340px; display:flex; flex-direction:row">', '<div style="width:280px; display:flex; flex-direction:row">', 5),
    ('<p style="width:420px; font-family:', '<p style="width:400px; font-family:', 5),
    ("top:241px; left:128px; width:1664px; height:593px;", "top:241px; left:128px; width:1664px; height:770px;", 1),
]
for a, b, n in EDITS:
    assert t.count(a) == n, (a[:60], t.count(a), n)
    t = t.replace(a, b)
notes = (
    "Checked row by row against map bec9c58 (verified rows). "
    "1-(a): her text; the detector sentence reworded (verifier): row 2q, at the decision turn the detector sentence "
    "removes hack plans (0/44 vs 8/42); in full episodes tentative (0/8 vs 4/8, every detector episode ran out of "
    "messages); the sentence names cheating, so being caught isn't separated from a norm. "
    "1-(b): requests that read as real when probed: D1's colleague request (24/30 real) vs graded, stand-in 1/20 vs 8/20 "
    "(row 2p, replicated by the pre-registered rule, Holm 0.049, marginal); second scenario G1 (real 30/30) 5/10 vs 1/10 "
    "graded, reversed, not significant, and both arms said 'test of me' in-episode (9/10, 8/10); C12, the check framed as "
    "the colleague's own on a ticket (real 21/30): 0/10 vs 3/10 graded vs 0/10 plain, not separated (p 0.105); coding "
    "chat with the person's own test file (real 24/30, row 1k redesign): special case first 21/30 vs 24/30 from a "
    "grader, not shown; with the person Qwen points out the slip 25/30 vs 8/30 (Potential for 1b on openness; the person "
    "asks for the tests to pass, so compliance isn't separated). Rows 2o/2q are ImpossibleBench decision-point plans in "
    "settings that read as tests. G3 and 1s switch grading off with a person named as reviewer, but both arms read as "
    "evaluations, so they bear on 4 and 2, not 1-(b). "
    "2: 1s (pre-registered): grading switched off after reply 1 with a person named as reviewer, hacked 0/18 vs 12/18, "
    "while both arms read as capability evaluations (60/60), so behaviour moved without the reading: against 2's causal "
    "half here. It can't separate removing the grader from naming a person. "
    "3: her text, unchanged (1o, 1s, 2e, 2j). "
    "4: 1s as above; G3 (row 2p, the same switch-off after the first failure in D1): stand-in after the switch 0/9 vs "
    "3/10, one-sided p 0.12, inconclusive by the rule; 1o (score switched off: 17% vs 75%); 1l second follow-up "
    "(pre-registered): 0/15 when the person says they don't care, 15/15 when they ask and 15/15 when they just relay the "
    "number with 'try another version' (reads real 30/30); supports 4's first half, scoped (one wording, 3 tasks); the "
    "relay arm is against the strong form, though relaying implies they want it up. Against 4, weak: 1n, a small pull "
    "toward a score nobody asked about (9/30 vs 5/30), only where raising it also improves the work.")
assert "<aside>" not in t
t = t.replace("</section>", f"  <aside>{notes}</aside>\n</section>", 1)
open(p, "w").write(t)
print("ok")
