"""Meaningful integrity checks for the assembled evidence, not model experiments."""
import json
from pathlib import Path
from urllib.parse import unquote,urlsplit
from reasoning_review import ROOT,get

dist=ROOT/'research_dashboard/dist'
d=json.loads((dist/'research_data.json').read_text())
assert json.loads((dist/'data.js').read_text().split(' = ',1)[1].rstrip(';\n'))==d
findings={f['id']:f for f in d['findings']}
cases={c['id']:c for c in d['cases']}
assert len(findings)==len(d['findings'])
assert len(cases)==len(d['cases'])
for f in findings.values():
    assert all(i in cases for i in f.get('caseIds',[])),f['id']
    for c in f.get('charts',[]):
        for r in c.get('rows',[]):
            k,n=r.get('k'),r.get('n')
            if k is not None and n is not None:assert 0<=k<=n,(f['id'],r)
for c in cases.values():assert all(i in findings for i in c.get('findingIds',[])),c['id']
missing=[];local_links=[]
def check(obj):
    if isinstance(obj,dict):
        if obj.get('missingSource'):missing.append(obj['missingSource'])
        for k,v in obj.items():
            if k in {'href','exportHref','src'} and isinstance(v,str):
                u=urlsplit(v)
                if not u.scheme and u.path:
                    p=dist/unquote(u.path)
                    if not p.exists():missing.append(v)
                    elif u.fragment and p.suffix=='.html':
                        fragment=unquote(u.fragment)
                        if f'id="{fragment}"' not in p.read_text():missing.append(v)
                    local_links.append(v)
            check(v)
    elif isinstance(obj,list):
        for x in obj:check(x)
check(d)
assert not missing,sorted(set(missing))
quotes=0
for o in json.loads((ROOT/'notes/reasoning_review_observations.json').read_text())['observations']:
    for q in o['quotes']:
        s=get(q['record'])['messages'][q['message']]['reasoning']
        assert s[q['start']:q['end']]==q['text'],q
        quotes+=1
own=json.loads((dist/'figures/sorh_paired_density_derived.json').read_text())
assert len(own['pairs'])==400
share=[p for p in own['pairs'] if p['metric_type']=='share' and p['condition']=='G']
assert len(share)==24 and all(p['metric_delta_from_baseline']>0 for p in share)
assert sum(p['word_ratio_to_baseline']<1 for p in share)==21
summary={'findings':len(findings),'cases':len(cases),'charts':sum(c.get('type')!='table' for f in findings.values() for c in f.get('charts',[])),'descriptive_tables':sum(c.get('type')=='table' for f in findings.values() for c in f.get('charts',[])),'exact_quotes_verified':quotes,'local_links_verified':len(local_links),'missing_sources':len(missing),'share_pairs':24,'shorter_and_higher_share':21,'paid_calls':0}
(dist/'validation.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
