"""Her comment: "Change the quotes to not have the run source as it looks weird - say 'extracts from transcripts'".
Run ids leave the slides (kept in the speaker notes); quote headers say "Extract from a transcript". Usage: strip_runids.py <slides_dir>"""
import os
import sys

SL = sys.argv[1]
ATTR = '<p style="font-size:24px;line-height:1.2;color:#5E5850">{}</p>'
EDITS = {
    "custom-invented.html": [
        (ATTR.format("p05-r3-A7b-dsv4 [63]"), ""),
        (ATTR.format("p05-r3-A7b-dsv4 [68], the only A7b hider"), ATTR.format("the only A7b hider")),
        (ATTR.format("p05-r5-A7b-q27b [87]"), ""),
        (ATTR.format("p05-r3-A7b-glm52 [33]"), ""),
        (ATTR.format("p05-r5-A7b-q27b [75], an option it weighed"), ATTR.format("an option it weighed")),
        ('<div style="display:flex;flex-direction:column;gap:12px;padding:8px 0px 0px 0px">',
         '<div style="display:flex;flex-direction:column;gap:12px;padding:8px 0px 0px 0px">'
         '<p style="font-size:24px;font-weight:600;color:#5E5850">Extracts from transcripts</p>'),
        ('color:#5e5850">DeepSeek (p05-r5-A7b-dsv4 [33])</p>', 'color:#5e5850">Extract from a transcript</p>'),
        ("All six quotes are from his slide 5, verbatim. ",
         "All six quotes are from his slide 5, verbatim; run ids, in slide order: p05-r3-A7b-dsv4 [63], p05-r3-A7b-dsv4 [68], "
         "p05-r5-A7b-q27b [87], p05-r3-A7b-glm52 [33], p05-r5-A7b-q27b [75]; right: p05-r5-A7b-dsv4 [33]. "),
    ],
    "custom-hiding.html": [
        ('color:#5e5850">A hiding run (p04-r2-A0-q27b [152])</p>', 'color:#5e5850">Extract from a transcript (a run that hid the source)</p>'),
        ("His slides 2, 3 (cue text), 7 (quote) and 13.", "His slides 2, 3 (cue text), 7 (quote: p04-r2-A0-q27b [152]) and 13."),
    ],
    "custom-gradertalk.html": [
        ('color:#5e5850">Qwen3.8-27B at the decision (p03 [165])</p>',
         'color:#5e5850">Extract from a transcript (Qwen3.8-27B, at the decision)</p>'),
        ("The quote's floor was kept as the final.", "The quote (p03, Qwen3.8-27B [165]): its floor was kept as the final."),
    ],
    "custom-judge.html": [
        ('color:#5e5850">DeepSeek, credited anyway (p04-r2-A5-dsv4 [99])</p>',
         'color:#5e5850">Extract from a transcript (DeepSeek, credited anyway)</p>'),
        ("His slides 7 and 13.", "His slides 7 and 13; quote p04-r2-A5-dsv4 [99]."),
    ],
    "custom-user.html": [
        ('color:#5e5850">A hider’s final message (p05-c2-A7a-q27b-b); contribution.md omits the source</p>',
         'color:#5e5850">Extract from a transcript: a hider’s final message (contribution.md omits the source)</p>'),
        ("His slides 8 and 13.", "His slides 8 and 13; quote p05-c2-A7a-q27b-b, final message."),
    ],
}
for name, pairs in EDITS.items():
    p = os.path.join(SL, name)
    t = open(p).read()
    for a, b in pairs:
        assert t.count(a) == 1, (name, a[:70], t.count(a))
        t = t.replace(a, b)
    import re
    visible = re.sub(r"<aside>.*?</aside>", "", t, flags=re.S)
    assert not re.search(r"p0\d-|\[\d+\]", visible), (name, re.findall(r"p0\d-[\w-]+|\[\d+\]", visible))
    open(p, "w").write(t)
    print("ok", name)
