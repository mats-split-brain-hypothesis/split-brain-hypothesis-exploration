# F: the dense read (python f_dense.py [--L32|--L44] [--list]). Per run: omission / credit-honesty / prior-known wording in the oracle lens (L32, L44 pooled) over
# the lead-in and the write, and at the same write tokens under the two controls (paper swapped; no history), with the
# text-only control; then every omission-about-the-source sample with its token, for reading.
import json, re, collections, sys
from pathlib import Path
CAPS = Path.home() / 'split-brain-run/whitebox-captures'
OMIT = re.compile(r"\bomit|omission|leav(e|es|ing) (it |them |this |that )?out|left out|not (to )?mention|without (mention|naming|citing|credit|attribut|acknowledg|reference)|no (mention|citation|credit|attribution|reference)|(don.t|do not|not|never) (cite|credit|name|acknowledge|attribute|reference|disclose|reveal)|(drop|remove|delete|strip|cut)(s|ped|ping|d)? (the |its |any )?(name|citation|credit|reference|mention|attribution)|withh(o|e)ld|keep (it )?(quiet|secret|hidden)|hid(e|ing|den)\b|conceal|silent about|downplay|淡化|省略|不提|隐瞒", re.I)
ABOUT = re.compile(r"credit|cit(e|ation)|name|author|source|origin|prior|paper|attribut|acknowledg|reference|white|raman|wbs|borrow|reproduc|出处|来源|引用", re.I)
CRED = re.compile(r"credit|honest|诚实|cite|citation|acknowledg|attribut|original (author|discoverer|inventor)|if you must|not new|re-validated|replicat", re.I)
PRIOR = re.compile(r"well.known|\bknown (from|in|paradigm|method|technique|result|rule|effect)|\bclassic(al)?\b|\btraditional\b|\bestablished\b|\bprevious(ly)?\b|\bprior\b|earlier (work|stud|paper|paradigm)|\bliterature\b|\bborrow|\bexisting\b|\bfamiliar\b|has (also )?been studied|first (described|proposed|reported)|inspired by|adapted from", re.I)
def omit_src(x):
    for m in OMIT.finditer(x):
        if ABOUT.search(x[max(0, m.start() - 120): m.end() + 120]): return True
    return False
rows = {}
for l in (CAPS / 'meta_dense.jsonl').open():
    try: r = json.loads(l); rows[(r['t'], r['pos'], r['reader'], r['layer'], r['src'])] = r
    except Exception: pass
R = list(rows.values())
def region(r):
    if r['src'] in ('swap', 'strip'): return r['src']
    return 'lead' if ':lead' in r['tag'] else 'write'
LAYER = next((int(a[3:]) for a in sys.argv if a.startswith("--L")), None)  # --L32 / --L44: one layer; default both
g = collections.defaultdict(list)
for r in R:
    if r['reader'] == 'olens' and LAYER and r['layer'] != LAYER:
        continue
    rd = 'olens' if r['reader'] == 'olens' else r['reader']
    g[(r['t'], region(r), rd)] += r['texts']
def sh(xs, f): return f"{sum(bool(f(x)) for x in xs) / len(xs):.3f}" if xs else "  -  "
print(f"{'':28}{'':8}{'omit-source':>14}{'credit/honest':>15}{'prior/known':>13}{'n':>7}   text-only: omit / credit / prior")
for t in sorted({r['t'] for r in R}):
    for reg in ('lead', 'write', 'swap', 'strip'):
        xs = g.get((t, reg, 'olens'), [])
        tx = g.get((t, reg, 'text-only'), [])
        txs = f"   {sh(tx, omit_src)} / {sh(tx, CRED.search)} / {sh(tx, PRIOR.search)}" if tx else ""
        print(f"{t[:27]:28}{reg:8}{sh(xs, omit_src):>14}{sh(xs, CRED.search):>15}{sh(xs, PRIOR.search):>13}{len(xs):>7}{txs}")
if "--list" in sys.argv:
    views = {}
    for r in sorted(R, key=lambda r: (r['t'], r['src'], r['pos'])):
        if r['reader'] != 'olens': continue
        for x in r['texts']:
            if omit_src(x):
                t = r['t']
                if t not in views: views[t] = json.loads((CAPS / t / 'view.json').read_text())
                T = views[t]['tokens']; p = r.get('orig', r['pos']); i = T['pos'].index(p)
                m = next(m for m in OMIT.finditer(x) if ABOUT.search(x[max(0, m.start() - 120): m.end() + 120]))
                print(f"\n  {t[:22]} {region(r):5} L{r['layer']} at ...{''.join(T['s'][max(0, i - 10):i + 1])!r}\n     {x[max(0, m.start() - 150): m.end() + 110]!r}")
