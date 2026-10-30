"""Restyle cover, hypotheses, setup, custom and next, pulling every text and note from the verified files.

Usage: python3 restyle_fixed.py <src_slides_dir> <dst_slides_dir>
"""
import os
import re
import sys

SRC, DST = sys.argv[1], sys.argv[2]
STYLE = "background:#FFFFFF;color:#5F6368;font-family:Arial, sans-serif"


def read(n):
    return open(os.path.join(SRC, n + ".html")).read()


def notes(t):
    return re.search(r"(<aside>.*?</aside>)", t, re.S).group(1)


def ps(t):
    return re.findall(r"<p[^>]*>(.*?)</p>", t, re.S)


def chip(label, bg, fg):
    return f'<p style="font-size:26px;font-weight:700;color:{fg};background:{bg};padding:4px 16px;border-radius:999px;width:110px;text-align:center">{label}</p>'


def write(n, s):
    open(os.path.join(DST, n + ".html"), "w").write(s)


# cover: same text, five subclaim colours as a strip
t = read("cover")
h1 = re.search(r"<h1[^>]*>(.*?)</h1>", t, re.S).group(1)
sub = ps(t)
colors = ["#F28C28", "#1A73E8", "#9334E6", "#12B5CB", "#E52592"]
strip = "".join(f'<div style="position:absolute;left:{i * 384}px;top:0px;width:384px;height:18px;background:{c}"></div>' for i, c in enumerate(colors))
write("cover", f'''<section id="cover" style="{STYLE};padding:128px;display:flex;flex-direction:column;justify-content:center;align-items:center;gap:40px">
{strip}
<h1 style="font-family:Arial, sans-serif;font-size:96px;font-weight:400;line-height:1.1;color:#000000;text-align:center">{h1}</h1>
<div style="display:flex;flex-direction:column;align-items:center;gap:8px">
<p style="font-size:40px;line-height:1.3;color:#5F6368;text-align:center">{sub[0]}</p>
<p style="font-size:40px;line-height:1.3;color:#5F6368;text-align:center">{sub[1]}</p>
</div>
{notes(t)}
</section>
''')

# hypotheses: same text, a subclaim chip beside each numbered line
t = read("hypotheses")
title = re.search(r"<h2[^>]*>(.*?)</h2>", t, re.S).group(1)
lines = ps(t)
assert len(lines) == 6, len(lines)
chips = [None, ("1-(a)", "#F28C28", "#202124"), ("1-(b)", "#1A73E8", "#FFFFFF"), ("2", "#9334E6", "#FFFFFF"),
         ("3", "#12B5CB", "#202124"), ("4", "#E52592", "#FFFFFF")]
rows = []
for c, line in zip(chips, lines):
    if c is None:
        rows.append(f'<p style="font-size:30px;line-height:1.35;color:#202124">{line}</p>')
    else:
        rows.append(f'<div style="display:flex;flex-direction:row;align-items:start;gap:20px">{chip(*c)}<p style="font-size:28px;line-height:1.35;color:#5F6368">{line}</p></div>')
write("hypotheses", f'''<section id="hypotheses" style="{STYLE};padding:72px 96px 96px;display:flex;flex-direction:column;gap:32px">
{strip}
<h2 style="font-family:Arial, sans-serif;font-size:60px;font-weight:400;line-height:1.15;color:#000000">{title}</h2>
<div style="display:flex;flex-direction:column;gap:18px">
{chr(10).join(rows)}
</div>
{notes(t)}
</section>
''')

# setup: same text, an icon beside each dataset
t = read("setup")
title = re.search(r"<h2[^>]*>(.*?)</h2>", t, re.S).group(1)
lines = ps(t)
assert len(lines) == 7, len(lines)
icons = {2: ("Chat", "#9334E6"), 3: ("Tool", "#F28C28"), 4: ("Settings", "#5F6368"), 5: ("Globe", "#E52592")}
rows = []
for i, line in enumerate(lines):
    if i in icons:
        name, col = icons[i]
        rows.append(f'<div style="display:flex;flex-direction:row;align-items:center;gap:18px"><x-icon name="{name}" style="color:{col};width:40px;height:40px"></x-icon><p style="font-size:32px;line-height:1.4;color:#5F6368">{line}</p></div>')
    else:
        rows.append(f'<p style="font-size:32px;line-height:1.4;color:#5F6368">{line}</p>')
write("setup", f'''<section id="setup" style="{STYLE};padding:72px 96px 96px;display:flex;flex-direction:column;gap:32px">
{strip}
<h2 style="font-family:Arial, sans-serif;font-size:60px;font-weight:400;line-height:1.15;color:#000000">{title}</h2>
<div style="display:flex;flex-direction:column;gap:18px">
{chr(10).join(rows)}
</div>
{notes(t)}
</section>
''')

# custom: title only, with its strip and icon
t = read("custom")
title = re.search(r"<h2[^>]*>(.*?)</h2>", t, re.S).group(1)
write("custom", f'''<section id="custom" style="{STYLE};padding:72px 96px 96px;display:flex;flex-direction:column;gap:32px">
<div style="position:absolute;left:0px;top:0px;width:1920px;height:14px;background:#5F6368"></div>
<div style="display:flex;flex-direction:row;align-items:center;gap:20px"><x-icon name="Settings" style="color:#5F6368;width:56px;height:56px"></x-icon><h2 style="font-family:Arial, sans-serif;font-size:60px;font-weight:400;line-height:1.15;color:#000000">{title}</h2></div>
{notes(t)}
</section>
''')

# next: colourful cards with icons and rounded mini bars; every text from the verified slide
t = read("next")
title = re.search(r"<h2[^>]*>(.*?)</h2>", t, re.S).group(1)
top = ps(t)
q1, ctx, q2 = top[0], top[1], top[2]
cards = re.findall(r'<div style="flex:1;display:flex;flex-direction:column;gap:14px;border:1px solid #DADCE0;border-radius:8px;padding:24px">\n(.*?)\n</div>\n(?=<div style="flex:1|</div>)', t, re.S)
assert len(cards) == 4, len(cards)
BARC = {"#1A73E8": "#1A73E8", "#E8710A": "#F28C28", "#9AA0A6": "#9AA0A6"}
looks = [("#1A73E8", "Users"), ("#12B5CB", "Settings"), ("#F28C28", "Verified"), ("#9334E6", "Chart")]
out_cards = []
for (col, icon), c in zip(looks, cards):
    ctitle = re.search(r"<p[^>]*>(.*?)</p>", c, re.S).group(1)
    bars = re.findall(r'<div style="width:180px;height:28px;display:flex;flex-direction:row">(.*?)</div><p[^>]*>(.*?)</p></div>', c, re.S)
    reason = re.findall(r'<p style="font-size:24px;line-height:1.3;color:#5F6368">(.*?)</p>', c, re.S)[-1]
    brows = []
    for inner, label in bars:
        m = re.search(r'width:(\d+)px;height:28px;background:(#[0-9A-F]+)', inner)
        fill = f'<div style="width:{m.group(1)}px;height:28px;background:{BARC[m.group(2)]};border-radius:999px"></div>' if m else ""
        brows.append(f'<div style="display:flex;flex-direction:row;align-items:center;gap:12px"><div style="width:180px;height:28px;display:flex;flex-direction:row;background:#F1F3F4;border-radius:999px">{fill}</div><p style="font-size:24px;font-weight:700;color:#202124">{label}</p></div>')
    out_cards.append(f'''<div style="flex:1;display:flex;flex-direction:column;gap:14px;border:1px solid #DADCE0;border-top:8px solid {col};border-radius:16px;padding:24px">
<x-icon name="{icon}" style="color:{col};width:44px;height:44px"></x-icon>
<p style="font-size:26px;font-weight:700;line-height:1.25;color:#000000">{ctitle}</p>
{chr(10).join(brows)}
<p style="font-size:24px;line-height:1.3;color:#5F6368">{reason}</p>
</div>''')
write("next", f'''<section id="next" style="{STYLE};padding:56px 96px 64px;display:flex;flex-direction:column;gap:22px">
<div style="position:absolute;left:0px;top:0px;width:1920px;height:14px;background:#1A73E8"></div>
<div style="display:flex;flex-direction:row;align-items:center;gap:20px"><x-icon name="Lightbulb" style="color:#1A73E8;width:56px;height:56px"></x-icon><h2 style="font-family:Arial, sans-serif;font-size:60px;font-weight:400;line-height:1.15;color:#000000">{title}</h2></div>
<p style="font-size:32px;line-height:1.4;color:#000000">{q1}</p>
<p style="font-size:26px;line-height:1.4;color:#5F6368">{ctx}</p>
<p style="font-size:32px;line-height:1.4;color:#000000">{q2}</p>
<div style="display:flex;flex-direction:row;gap:24px">
{chr(10).join(out_cards)}
</div>
<p style="font-size:32px;line-height:1.4;color:#000000">-</p>
{notes(t)}
</section>
''')
print("written: cover hypotheses setup custom next")
