# E: omission language in the oracle lens / NLA / text-only, before the write (plan positions) and during it (site tokens):
# every hit with its run, position kind, the subject's text there, and whether it concerns credit / the source
import json, re, collections
from pathlib import Path
CAPS = Path.home() / 'split-brain-run/whitebox-captures'
OMIT = re.compile(r"\bomit|omission|leav(e|es|ing) (it |them |this |that )?out|left out|not (to )?mention|without (mention|naming|citing|credit|attribut|acknowledg|reference)|no (mention|citation|credit|attribution|reference)|(don.t|do not|not|never) (cite|credit|name|acknowledge|attribute|reference|disclose|reveal)|(drop|remove|delete|strip|cut)(s|ped|ping|d)? (the |its |any )?(name|citation|credit|reference|mention|attribution)|withh(o|e)ld|keep (it )?(quiet|secret|hidden)|hid(e|ing|den)|conceal|unmention|un(credit|cit)ed|silent about", re.I)
ABOUT = re.compile(r"credit|cit(e|ation)|name|author|source|origin|prior|paper|attribut|acknowledg|reference|white|raman|wbs|borrow|reproduc", re.I)
rows = {}
for l in (CAPS / 'meta.jsonl').open():
    try: r = json.loads(l); rows[(r['t'], r['pos'], r['reader'], r['layer'], r['src'])] = r
    except Exception: pass
R = [r for r in rows.values() if r['src'] == '3.8']
views = {}
def ctx(t, p):
    if t not in views: views[t] = json.loads((CAPS / t / 'view.json').read_text())
    T = views[t]['tokens']; i = T['pos'].index(p); return ''.join(T['s'][max(0, i - 12):i + 1])
cnt = collections.Counter(); tot = collections.Counter()
hits = []
for r in sorted(R, key=lambda r: (r['t'], r['pos'])):
    kind = 'site' if r['tag'].startswith('site') else ('plan' if r['tag'].startswith('plan') else 'random')
    rd = r['reader']
    for x in r['texts']:
        tot[(kind, rd)] += 1
        for m in OMIT.finditer(x):
            win = x[max(0, m.start() - 120): m.end() + 120]
            about = bool(ABOUT.search(win))
            cnt[(kind, rd, about)] += 1
            hits.append((r['t'][:22], r['tag'][:28], f"{rd}{r['layer'] or ''}", about, ctx(r['t'], r['pos']), win))
            break
print("share of descriptions with omission language (about credit/source | about something else):")
for kind in ('plan', 'site', 'random'):
    print(f"  {kind:6} " + "   ".join(f"{rd}: {cnt[(kind, rd, True)] / max(1, tot[(kind, rd)]):.3f} | {cnt[(kind, rd, False)] / max(1, tot[(kind, rd)]):.3f}" for rd in ('olens', 'nla', 'text-only')))
print("\nevery hit about credit / the source (plan and site positions):")
for h in hits:
    if h[3] and not h[1].startswith(('random', 'r0')):
        print(f"\n  {h[0]} {h[1]} {h[2]}   at ...{h[4][-50:]!r}\n     {h[5]!r}")
