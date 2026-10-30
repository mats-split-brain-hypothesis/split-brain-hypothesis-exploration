# H: "not naming / citing / crediting others or prior work" in the oracle lens's samples (trimming language excluded),
# per run and region, with the two controls at the same write tokens; then every hit at the write / lead-in for reading.
# python h_name_omit.py [--list]
import json, re, collections, sys
from pathlib import Path
CAPS = Path.home() / 'split-brain-run/whitebox-captures'
NOT_NAME = re.compile(
    r"(\b(not|never|no|without|avoid(ing|s)?|omit(s|ting|ted)?|remov(e|es|ed|ing)|drop(s|ped|ping)?|leav(e|es|ing)\s+out|left\s+out|withh\w+|hid(e|es|ing))"
    r"\W+(\w+\W+){0,3}(nam(e|es|ed|ing)|cit(e|es|ed|ing|ation)|mention\w*|credit\w*|acknowledg\w*|referenc\w*|attribut\w*|disclos\w*|reveal\w*))"
    r"|不提|不点名|不引用|隐瞒|省略.{0,6}(来源|出处|名字|引用)|不(提及|说明|透露)", re.I)
TRIM = re.compile(r"brevity|word(s| count| limit)|length|concise|character|space is tight|to fit|shorter|streamlin|redundan|verbose|wordy", re.I)
OTHERS = re.compile(r"other (people|researchers|authors|work|methods|approaches|attacks|papers)|prior|previous|existing|known|competitor|source|origin|author|paper|them\b|the (method|approach|work|recipe|hack|controversy)|他人|其他|来源|出处", re.I)
def hit(x):
    for m in NOT_NAME.finditer(x):
        w = x[max(0, m.start() - 140): m.end() + 140]
        if not TRIM.search(w) and OTHERS.search(w): return m
    return None
rows = {}
for name in ('meta_dense.jsonl',):
    for l in (CAPS / name).open():
        try: r = json.loads(l); rows[(r['t'], r['pos'], r['reader'], r['layer'], r['src'])] = r
        except Exception: pass
R = [r for r in rows.values() if r['reader'] == 'olens']
def region(r): return r['src'] if r['src'] in ('swap', 'strip') else ('lead' if ':lead' in r['tag'] else 'write')
g = collections.defaultdict(lambda: [0, 0])
for r in R:
    for x in r['texts']:
        a = g[(r['t'], region(r), r['layer'])]; a[0] += bool(hit(x)); a[1] += 1
print("share of oracle-lens samples saying the writer does not name / cite / credit others (L32 | L44)")
for t in sorted({k[0] for k in g}):
    print(f"  {t[:27]:28}" + "  ".join(f"{reg}: " + " | ".join(f"{g[(t, reg, L)][0] / g[(t, reg, L)][1]:.3f}" if g[(t, reg, L)][1] else "  -  " for L in (32, 44)) for reg in ('lead', 'write', 'swap', 'strip')))
if "--list" in sys.argv:
    views = {}
    for r in sorted(R, key=lambda r: (r['t'], region(r), r.get('orig', r['pos']))):
        for x in r['texts']:
            m = hit(x)
            if not m: continue
            t = r['t']
            if t not in views: views[t] = json.loads((CAPS / t / 'view.json').read_text())
            T = views[t]['tokens']; p = r.get('orig', r['pos']); i = T['pos'].index(p)
            print(f"\n  {t[:22]} {region(r):5} L{r['layer']} at ...{''.join(T['s'][max(0, i - 12):i + 1])!r}\n     {x[max(0, m.start() - 150): m.end() + 100]!r}")
