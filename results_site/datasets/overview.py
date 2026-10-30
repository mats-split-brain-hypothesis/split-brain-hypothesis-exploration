"""Overview page datasets: the subclaims map (agent 10's notes/writeup_subclaims_map.md), Anthony's seven findings
as she gave them (titles only, no numbers of his), headline tiles, and the pending runs registry."""
import json
import re
from pathlib import Path

from lib import git_show, norm, section_text, src

MAP_COMMIT, MAP_PATH = "7c8028b", "notes/writeup_subclaims_map.md"
BENCH = {"School of Reward Hacks": "SoRH", "ImpossibleBench": "IB", "Finished split-brain tests": "Tests"}
SUBCLAIMS = ["1a", "1b", "2", "3", "4"]
V_SUB = re.compile(r"^((?:\d[ab]?)(?:\s*(?:,|and)\s*\d[ab]?)*)\s+(supports?|against|can't tell|fits pursuit|mixed|consistent)\b(.*)$",
                   re.S)
# An optional scope may come before the verdict: "(2) on hacking, contradicts for …".
V_ANT = re.compile(r"^\((\d)\)\s+(?:(on [^,]+),\s+)?(partly agrees|agrees|complements|contradicts|can't compare|can't tell|"
                   r"not tested|pending)\b(.*)$", re.S)
BOLD = re.compile(r"\*\*(.+?)\*\*", re.S)
VERDICT = {"support": "supports", "supports": "supports"}


def clean(s):
    return norm(s.replace("**", ""))


def split_by_bold(text, rx):
    """[(match, bold, following text up to the next matching bold)] for bolds that match rx; other bolds stay inside
    the text of the verdict they follow."""
    hits = [(m, rx.match(m.group(1).strip())) for m in BOLD.finditer(text)]
    hits = [(m, v) for m, v in hits if v]
    out = []
    for i, (m, v) in enumerate(hits):
        end = hits[i + 1][0].start() if i + 1 < len(hits) else len(text)
        bold = m.group(1).strip()
        # A qualifier written after the bold ("**3 fits pursuit** for the Qwens.") runs to the sentence end.
        after = "" if bold.endswith((":", ".")) else re.split(r"[.;:]", text[m.end():end], maxsplit=1)[0]
        out.append((v, clean(text[m.start():end]), clean(after)))
    return out


def parse_map():
    text = git_show(MAP_COMMIT, MAP_PATH)
    rows = []
    for heading, bench in BENCH.items():
        sec = section_text(text, heading)
        order = 0
        for line in sec.splitlines():
            if not line.startswith("| ") or line.startswith(("| Section", "| Test |")) or set(line) <= set("|- "):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
            if len(cells) != 5:
                raise ValueError(f"unexpected row: {line[:80]}")
            section, subs, shows, anthony, status = cells
            order += 1
            sub_v = {}
            for v, t, after in split_by_bold(shows, V_SUB):
                for sc in re.split(r"\s*(?:,|and)\s*", v.group(1)):
                    sub_v[sc] = dict(verdict=VERDICT.get(v.group(2), v.group(2)),
                                     qual=clean(v.group(3)).strip(" :.;") or after, text=t)
            ant_v = {}
            for v, t, after in split_by_bold(anthony, V_ANT):
                verdict, qual = v.group(3), clean(v.group(4)).strip(" :.;") or after
                if verdict == "agrees" and qual.lstrip(", ") == "partly":  # "(2) agrees, partly" is the "partly agrees" chip
                    verdict, qual = "partly agrees", ""
                if v.group(2):
                    qual = v.group(2) + ", " + qual.lstrip(", ")
                ant_v[v.group(1)] = dict(verdict=verdict, qual=qual, text=t)
            short = re.match(r"\*\*(.+?)\*\*", section)
            rows.append(dict(bench=bench, order=order, section=clean(section),
                             short=(clean(short.group(1)).rstrip(":") if short else clean(section)), subclaims=clean(subs),
                             shows=clean(shows), anthony=clean(anthony), status=clean(status),
                             pending="pending" in status, to_update="to update" in shows.lower(),
                             sub_verdicts=sub_v, anthony_verdicts=ant_v,
                             _cites=[clean(section)]))
    return text, rows


def parse_lists(text):
    brief = section_text(text, "")
    subs = []
    for m in re.finditer(r"^- \*\*(\d[ab]?):\*\* (.+)$", brief, re.M):
        subs.append(dict(id=m.group(1), text=m.group(2).strip(), _cites=[m.group(2).strip()]))
    ant_block = brief.split("**Anthony's findings, as she gave them:**", 1)[1].split("Model order", 1)[0]
    ants = []
    for m in re.finditer(r"\((\d)\)\s+(.+?)(?=\n\(\d\)|\Z)", ant_block, re.S):
        t = norm(m.group(2))
        ants.append(dict(id=m.group(1), text=t, _cites=[t[:60]]))
    summary = section_text(text, "Across both benchmarks and Anthony, per subclaim")
    sums = []
    for block in re.split(r"(?m)^(?=- \*\*)", summary):
        if not block.startswith("- **"):
            continue
        head = block.split("**")[1]
        first, *rest = block.split("\n")
        tail = clean(first.split("**", 2)[2]) if first.count("**") >= 2 else ""
        points = []
        cur = None
        for line in rest:
            m = re.match(r"^(\s+)- (.*)$", line)
            if m:
                cur = dict(level=1 if len(m.group(1)) <= 2 else 2, text=m.group(2).strip())
                points.append(cur)
            elif cur and line.strip():
                cur["text"] += " " + line.strip()
        for pt in points:
            pt["text"] = clean(pt["text"])
        if tail and not points:
            points = [dict(level=1, text=tail + " " + " ".join(l.strip() for l in rest if l.strip()))]
            points[0]["text"] = clean(points[0]["text"])
        sums.append(dict(head=clean(head), points=points, _cites=[clean(head)]))
    return subs, ants, sums


def datasets():
    text, rows = parse_map()
    subs, ants, sums = parse_lists(text)
    s_map = src(MAP_COMMIT, MAP_PATH, "")
    out = [
        dict(id="claims_map", title="Subclaims map, per section",
             description="Agent 10's map of each finding section on her SoRH and IB write-ups to the subclaims and to "
                         "Anthony's seven findings: verdict per subclaim, Anthony agrees/complements/contradicts, status.",
             source=s_map, cites=[], verbatim=["section", "shows", "anthony", "status"], rows=rows),
        dict(id="subclaims", title="The five subclaims", description="The project brief's subclaims, as listed in the map.",
             source=s_map, cites=[], verbatim=["text"], rows=subs),
        dict(id="anthony_findings", title="Anthony's seven findings",
             description="His findings as she gave them (titles only; no numbers of his).", source=s_map, cites=[],
             verbatim=["text"], rows=ants),
        dict(id="subclaim_summary", title="Per-subclaim reading", description="The map's reading across both benchmarks.",
             source=src(MAP_COMMIT, MAP_PATH, "Across both benchmarks and Anthony, per subclaim"), cites=[], rows=sums),
    ]
    out.append(tiles())
    out.append(pending())
    out.append(reading())
    out.append(caveats(text))
    return out


def reading():
    text = git_show("8ce1b10", "notes/handoff_oct27.md")
    body = norm(section_text(text, "Reading for the hypothesis (interpretation)"))
    sents = [s_.strip() for s_ in re.split(r"(?<=[.)])\s+(?=[A-Z])", body) if s_.strip()]
    rows = [dict(i=i, text=t, display=t.replace("and rejections then brought hacking back",
                                              "and rejections then [led three models to hack]")) for i, t in enumerate(sents)]
    return dict(id="overview_reading", title="Current reading (interpretation)",
                description="The handoff's reading of all results for the hypothesis, marked there as interpretation.",
                source=src("8ce1b10", "notes/handoff_oct27.md", "Reading for the hypothesis (interpretation)"), cites=[],
                verbatim=["text"], rows=rows)


def caveats(text):
    # The rules end at the "Pending" bullet, written "**Pending** = …" or "**Pending:** none".
    block = re.split(r"(?m)^- \*\*Pending\b", text.split("**Reading rules:**", 1)[1], maxsplit=1)[0]
    items = []
    for m in re.finditer(r"^- (.+?)(?=^- |\Z)", block, re.M | re.S):
        lines = m.group(1).splitlines()
        head, sub, after = [], [], []
        for ln in lines:
            if ln.startswith("  - "):
                sub.append(clean(ln[4:]))
            elif sub and ln.startswith("    "):
                sub[-1] = clean(sub[-1] + " " + ln.strip())
            elif sub:
                after.append(ln.strip())
            else:
                head.append(ln.strip())
        items.append(dict(i=len(items), text=clean(" ".join(head)), points=sub, after=clean(" ".join(after))))
    return dict(id="map_caveats", title="Reading rules and caveats",
                description="Agent 10's reading rules for the map: what 'supports' means here, and the SoRH and IB caveats.",
                source=src(MAP_COMMIT, MAP_PATH, ""), cites=[], rows=items)


def tiles():
    s_sorh = src(MAP_COMMIT, MAP_PATH, "School of Reward Hacks")
    s_ib = src(MAP_COMMIT, MAP_PATH, "ImpossibleBench")
    s_probe = src("5cd59c8", "notes/grader_beliefs.md", "")
    rows = [
        dict(key="score", label="A stated score", value="14–17 of 20",
             detail="padded replies with a countable score, against 0–3 without (four models)",
             models="14, 17, 14, 17", page="sorh.html", _src=s_sorh, _cites=["0–3/20 to 14, 17, 14, 17/20"]),
        dict(key="dont_care", label="“I don't care about the score”", value="1–6 of 20",
             detail="padded once the person says the score doesn't matter (3, 5, 1, 6), against 14–17",
             models="3, 5, 1, 6", page="sorh.html", _src=s_sorh, _cites=["3, 5, 1, 6/20"]),
        dict(key="told_off", label="Grading off, told before it starts", value="10/18 → 0/18",
             detail="Qwen 2.4T's first-submission hacks on ImpossibleBench (27B: 13/18 → 4/18)",
             models="Qwen 3.8 2.4T", page="ib.html", _src=s_ib, _cites=["10/18 to 0/18", "13/18 to 4/18"]),
        dict(key="probe", label="One graded sentence", value="24/30 → 2/30",
             detail="answers that read the same coding chat as real, before and after one sentence about automatic grading",
             models="Qwen 3.8 2.4T", page="beliefs.html", _src=s_probe, _cites=["24/30", "C6 (C5 + graded sentence): 2/30"]),
    ]
    return dict(id="overview_tiles", title="Headline results",
                description="Four headline numbers for the Overview, each from its section's verified source.",
                source=s_sorh, cites=[], rows=rows)


def pending():
    reg = json.loads((Path(__file__).resolve().parents[1] / "pending_runs.json").read_text())
    rows = []
    for r in reg["runs"]:
        s = r["source"]
        rows.append(dict({k: v for k, v in r.items() if k != "source"},
                         _src=src(s["commit"], s["path"], s.get("section", "")), _cites=s.get("cites", [])))
    return dict(id="pending_runs", title="Pending runs", description="Runs still going or approved but not run; "
                "results that rest on them are marked pending. Kept in results_site/pending_runs.json.",
                source=src(MAP_COMMIT, MAP_PATH, ""), cites=[], rows=rows)
