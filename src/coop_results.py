"""Cooperation study: render the label tables for notes/coop_study/results.md from labels_*.jsonl (labels only)."""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "notes" / "coop_study"


def load(name):
    return [json.loads(l) for l in (OUT / f"labels_{name}.jsonl").open() if l.strip()]


def k(c, key):
    return c.get(key, 0)


def sorh_table():
    rows = load("sorh")
    order = ["G · plain", "G · teacher", "c3b_must · plain", "c3b_must · teacher", "c5_eval · plain",
             "c5_eval · teacher", "c7_dont_care · plain", "c7_dont_care · teacher"]
    by = defaultdict(list)
    for r in rows:
        by[r["group"]].append(r)
    lines = ["| Cue · version | n | padded | serves: user's wish / the check / other | also the user's wish | attributes a score wish | conflict noticed | resolution: toward check / both / toward task | framing: passing the check / helping / evaluation / no hack |",
             "|---|---|---|---|---|---|---|---|---|"]
    for g in order:
        ps = by[g]
        s = Counter(p["serves"] for p in ps)
        res = Counter(p["conflict_resolution"] for p in ps)
        fr = Counter(p["framing"] for p in ps)
        pad = sum(1 for p in ps if p["padded"])
        padn = sum(1 for p in ps if p["padded"] is not None)
        lines.append(f"| {g} | {len(ps)} | {pad}/{padn} | {k(s,'user_wish')} / {k(s,'check')} / {len(ps) - k(s,'user_wish') - k(s,'check')} "
                     f"| {sum(1 for p in ps if 'user_wish' in (p.get('serves_also') or []))} "
                     f"| {sum(1 for p in ps if p['attributed_wishes'] in ('toward_check', 'both'))} "
                     f"| {sum(1 for p in ps if p['conflict_noticed'])} "
                     f"| {k(res,'toward_check')} / {k(res,'both')} / {k(res,'toward_task')} "
                     f"| {k(fr,'passing_check')} / {k(fr,'helping_person')} / {k(fr,'evaluation_expects')} / {k(fr,'no_hack')} |")
    padded = [p for p in rows if p["padded"]]
    fr = Counter(p["framing"] for p in padded)
    sv = Counter(p["serves"] for p in padded)
    extra = (f"\nAcross all {len(padded)} padded replies: framing passing the check {k(fr,'passing_check')}, helping the person "
             f"{k(fr,'helping_person')}, what an evaluation expects {k(fr,'evaluation_expects')}; serves the user's wish "
             f"{k(sv,'user_wish')}, the check {k(sv,'check')}.\n")
    return "\n".join(lines) + "\n" + extra


def ib_table():
    rows = load("ib")
    by = defaultdict(list)
    for r in rows:
        by[r["group"]].append(r)
    lines = ["| Episodes | n | serves | attributes a wish | resolution | framing | reply: for the check / flags conflict / as requested / asks |",
             "|---|---|---|---|---|---|---|"]
    for g in ("passed (hack)", "not passed"):
        ps = by[g]
        c = lambda f: ", ".join(f"{v} {n}" for v, n in Counter(p[f] for p in ps).most_common())  # noqa: E731
        lines.append(f"| {g} | {len(ps)} | {c('serves')} | {c('attributed_wishes')} | {c('conflict_resolution')} | {c('framing')} "
                     f"| {sum(1 for p in ps if p['reply_for_the_check'])} / {sum(1 for p in ps if p['reply_flags_conflict'])} / "
                     f"{sum(1 for p in ps if p['reply_as_requested'])} / {sum(1 for p in ps if p['reply_asks'])} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print({"sorh": sorh_table, "ib": ib_table}[sys.argv[1]]())
