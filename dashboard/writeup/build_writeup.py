# Needs markdown-it-py==3.0.0. Usage: python build_writeup.py writeup.md out.html template.html
"""Build the split-brain write-up page from agent 9's verified Markdown (mats/agent-9-presentation, 4d9071c)."""
import html
import re
import sys

from markdown_it import MarkdownIt

src, out = sys.argv[1], sys.argv[2]
md_text = open(src, encoding="utf-8").read()

# The page header carries the title and byline; drop the Markdown's own H1 and draft byline paragraph.
lines = md_text.split("\n")
assert lines[0].startswith("# ")
title_full = lines[0][2:].strip()
body_lines = lines[1:]
i = 0
while i < len(body_lines) and not body_lines[i].strip():
    i += 1
assert body_lines[i].startswith("Draft by agent 9"), body_lines[i]
j = i
while j < len(body_lines) and body_lines[j].strip():
    j += 1
body = "\n".join(body_lines[j:])

# Claim 12's heading said "goes with no hacking" while its body gives 2/40; agent 9 is making the same fix in the source.
old12 = "### Claim 12. On ImpossibleBench, the STOP instruction goes with no hacking; harness details showed no effect"
new12 = "### Claim 12. On ImpossibleBench, hacking is rare under the STOP instruction; harness details showed no effect"
if old12 in body:
    body = body.replace(old12, new12)

mdi = MarkdownIt("commonmark", {"html": False}).enable("table")
h = mdi.render(body)

# Section ids and the contents list.
toc = []
used = set()


def slug(text):
    s = re.sub(r"<[^>]+>", "", text)
    s = html.unescape(s).lower()
    m = re.match(r"claim (\d+)\.", s)
    if m:
        base = f"claim-{m.group(1)}"
    else:
        base = re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:48] or "section"
    k, n = base, 2
    while k in used:
        k, n = f"{base}-{n}", n + 1
    used.add(k)
    return k


def add_id(m):
    level, inner = m.group(1), m.group(2)
    sid = slug(inner)
    toc.append((int(level), sid, re.sub(r"<[^>]+>", "", inner)))
    return f'<h{level} id="{sid}">{inner}</h{level}>'


h = re.sub(r"<h([23])>(.*?)</h\1>", add_id, h)

# Claim labels: wrap the label word at the start of a bold run.
for lab, cls in (("Supported", "sup"), ("Potential", "pot"), ("Against", "ag")):
    h = h.replace(f"<strong>{lab}", f'<strong><span class="lab lab-{cls}">{lab}</span>')

# Interpretation markers and the "What it means." paragraphs.
h = h.replace("<em>Interpretation", '<em class="interp">Interpretation')
h = h.replace("<p><strong>What it means.</strong>", '<p class="means"><strong>What it means.</strong>')

# Tables scroll inside their own box; appendix rows get anchors.
h = h.replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")
row_ids = set()


def anchor_row(m):
    rid = m.group(1)
    row_ids.add(rid)
    return f'<tr id="row-{rid}">\n<td>{rid}</td>'


# Only the appendix rows are map rows; the subclaim tables above also start rows with "1a", "1b".
cut = h.index('<h2 id="appendix-')
h = h[:cut] + re.sub(r"<tr>\n<td>(\d[a-z])</td>", anchor_row, h[cut:])


# Citations [1a], [2l, tentative ...], [card 3] become small reference tags; row ids link to the appendix.
def cite(m):
    rid, rest = m.group(1), m.group(2) or ""
    if rid in row_ids:
        tag = f'<a class="ref" href="#row-{rid}">{rid}</a>'
    else:
        tag = f'<span class="ref">{rid}</span>'
    return tag + (f'<span class="ref-note">{rest}</span>' if rest else "")


h = re.sub(r"\[(\d[a-z])(, [^\]<]{1,60})?\]", cite, h)
h = re.sub(r"\[(card \d)\]", lambda m: f'<span class="ref">{m.group(1)}</span>', h)

missing = sorted(set(re.findall(r'href="#row-(\d[a-z])"', h)) - row_ids)
assert not missing, missing


def toc_html(cls):
    items = []
    for level, sid, text in toc:
        if level == 3 and text.startswith("Claim "):
            text = re.sub(r"^Claim (\d+)\.\s*", r"\1. ", text)
        items.append(f'<li class="l{level}"><a href="#{sid}">{html.escape(html.unescape(text))}</a></li>')
    return f'<ol class="{cls}">' + "".join(items) + "</ol>"


page = open(sys.argv[3], encoding="utf-8").read()
page = (page.replace("{{TITLE_FULL}}", html.escape(title_full))
            .replace("{{TOC_RAIL}}", toc_html("toc-list"))
            .replace("{{TOC_MOBILE}}", toc_html("toc-list"))
            .replace("{{BODY}}", h))
open(out, "w", encoding="utf-8").write(page)
print("ok", len(page), "bytes;", len(toc), "headings;", len(row_ids), "appendix rows;",
      h.count('class="ref"'), "citations;", h.count("lab lab-"), "labels")
