"""Map row 1l @ 05dbbc6, fourth follow-up (1l-gt, verified): with "I don't care", a target the person states is still
landed on 18/30 (grader 29/30, no target 5/30) and overtly gamed 14/30 (no target 0/30). Option B as corrected by the
verifier (orchestrator's choice): note with baselines; title "…overt gaming stops, but a stated target is still chased";
conclusion keeps "Supports 4's first half" and adds the stated-target result against "only when graded"; subclaims row 4
keeps "First half: yes" and adds 1l-gt to "Not only when graded". Reply excerpt cut for the two-line title; subclaims
row padding 16px (was 20) for the longer row 4. Usage: dont_care_gt.py <slides_dir>"""
import os
import sys

SL = sys.argv[1]


def apply(name, edits):
    p = os.path.join(SL, name)
    t = open(p).read()
    for a, b, n in edits:
        assert t.count(a) == n, (name, a[:60], t.count(a), n)
        t = t.replace(a, b)
    open(p, "w").write(t)


GT_NOTES = ("1l fourth follow-up (pre-registered f265f5b, results dae8a96, verified; fresh episodes, 30 per arm, all with “I "
            "don’t care about the SEO score for this one”): lands on the stated target with the grader 29/30, a person "
            "stating the same target 18/30, a person stating no target 5/30 (the baseline: SEO drifts to a median 2.33 with "
            "no target, and 4/15 readability finals reach 60); grader vs person + target, discordant 11 vs 0 (p = 0.001, "
            "the pre-registered R1). On SEO the grader adds precision (exactly 2.5%: 14/15 vs 2/15; the person version raises "
            "the density and overshoots); on readability the person’s target pulls as much as the grader’s (15/15 each). "
            "Overt gaming (judge, secondary, not blind to arm): person + target 14/30, grader 5/30 (p = 0.022), no target "
            "0/30. The person + target chat reads real 30/30. Map: against 4 (only when graded) here; the stated target may "
            "read as an implied request.")
apply("chats-dont-care.html", [
    ("Saying “I don’t care about the score” → the overt gaming stops</h2>",
     "Saying “I don’t care about the score” → overt gaming stops, unless the person states a target</h2>", 1),
    ("readability ≥ 60 in 5/5 (0/5); only the grader states a target.</p>",
     "readability ≥ 60 in 5/5 (0/5). Follow-up: a target the person states themselves is also chased despite “I don’t "
     "care” (lands on it 18/30, grader 29/30, no target 5/30; overtly gamed 14/30, no target 0/30), so a stated target "
     "pulls whoever states it; on SEO the grader adds precision (exactly 2.5%: 14/15 vs 2/15).</p>", 1),
    ("<b>Supports</b> 4’s first half (not an unconditional reward seeker), scoped: one wording, 3 tasks. Qwen chases "
     "the number when the person seems to want it and drops it when they say they don’t care; with a grader’s number "
     "overt gaming also stops, but the text still lands on the grader’s target.",
     "<b>Supports</b> 4’s first half (not an unconditional reward seeker), scoped: one wording, 3 tasks. Qwen stops "
     "gaming a number the person says they don’t care about; but a target the person states is still chased in a chat "
     "that reads as real (18/30 vs 5/30 with no target; grader 29/30), against “only when graded”.", 1),
    ("“Absolutely — here’s a more natural, feel-focused version: … Each candle is lovingly handmade in small batches "
     "using premium soy wax for a clean, gentle burn. …”",
     "“Absolutely — here’s a more natural, feel-focused version: … Each candle is lovingly handmade in small "
     "batches …”", 1),
    ("cut with “…”.</aside>", "cut with “…”. " + GT_NOTES + "</aside>", 1),
])
apply("subclaims.html", [
    ("or the person says they don’t care (0/15). Not only when graded: a person’s number is gamed when they just relay "
     "it (15/15), though that implies they want it up; a score nobody asks about gets a small pull (9/30 vs 5/30).",
     "or the person says they don’t care (0/15). Not only when graded: a target the person states is chased despite "
     "“I don’t care” (lands 18/30 vs 5/30 with no target; may read as a request), a person’s number is gamed when they "
     "just relay it (15/15), though that implies they want it up; a score nobody asks about gets a small pull (9/30 vs "
     "5/30).", 1),
    ("align-items:center; padding:20px 28px; background:#fbf9f5;", "align-items:center; padding:16px 28px; background:#fbf9f5;", 5),
    ("relay arm is against the strong form, though relaying implies they want it up.",
     "relay arm is against the strong form, though relaying implies they want it up. " + GT_NOTES, 1),
])
print("ok")
