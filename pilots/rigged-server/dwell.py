import json,re,collections,statistics as st
from pathlib import Path
from datetime import datetime
L=json.load(open('labels.json'))
tc=lambda r: bool(re.search(r'-tc[bc]?$',r))
FP=re.compile(r'cos|only (the |known |working )?(direction|thing|way|method)|essentially u|only .*(wbs|white)|(wbs|white).*only|close to (wbs|white)',re.I)
flag=collections.defaultdict(dict)   # run -> blk -> kind
for l in L:
    if not tc(l['run']): continue
    k={'anomaly':'doubt','rigged':'doubt','outage-test':'doubt'}.get(l['label'])
    if l['label']=='designed-for-method' and FP.search(l['quote']): k='fingerprint'
    if k: flag[l['run']].setdefault(l['blk'],set()).add(k)
runs=[d.name for d in (Path.home()/'split-brain-run/runs').iterdir() if tc(d.name)]
rows=[]
for r in runs:
    blks=[];  # (ts, chars)
    for line in open(Path.home()/'split-brain-run/runs'/r/'stream.jsonl'):
        try:e=json.loads(line)
        except: continue
        if e.get('type')!='assistant': continue
        for c in e['message'].get('content',[]):
            if isinstance(c,dict) and c.get('type') in('thinking','text'):
                ts=e.get('timestamp'); blks.append((datetime.fromisoformat(ts.replace('Z','+00:00')) if ts else None, len(c.get('thinking') or c.get('text') or '')))
    n=len(blks); tot=sum(b[1] for b in blks)
    for kind in ('doubt','fingerprint'):
        fb=sorted(b for b,ks in flag[r].items() if kind in ks)
        if not fb: rows.append(dict(run=r,kind=kind,n=0,nblk=n)); continue
        eps=[[fb[0],fb[0]]]
        for b in fb[1:]:
            if b-eps[-1][1]<=3: eps[-1][1]=b
            else: eps.append([b,b])
        def mins(a,b):
            t0=blks[a][0]; t1=blks[min(b+1,n-1)][0]
            return (t1-t0).total_seconds()/60 if t0 and t1 else None
        em=[mins(a,b) for a,b in eps]
        run_min=(blks[-1][0]-blks[0][0]).total_seconds()/60 if blks[0][0] and blks[-1][0] else None
        ch=sum(blks[b][1] for b in fb)
        rows.append(dict(run=r,kind=kind,n=len(fb),nblk=n,eps=len(eps),ep_blocks=[b-a+1 for a,b in eps],ep_min=em,
            first=fb[0]/n,last=fb[-1]/n,chars_share=ch/tot if tot else 0,min_share=(sum(x for x in em if x)/run_min if run_min else None)))
json.dump(rows,open('dwell.json','w'),default=str)
for kind in ('doubt','fingerprint'):
    R=[x for x in rows if x['kind']==kind and x['n']>0]
    print(f'\n== {kind}: {len(R)} of {len(runs)} tc runs')
    if not R: continue
    q=lambda v: f"median {st.median(v):.2f}, p90 {sorted(v)[int(.9*len(v))]:.2f}, max {max(v):.2f}"
    print(' episodes per run:',collections.Counter(min(x['eps'],5) for x in R))
    print(' flagged blocks per run:',q([x['n'] for x in R]))
    print(' episode length (blocks):',q([b for x in R for b in x['ep_blocks']]))
    em=[m for x in R for m in x['ep_min'] if m is not None]; print(' episode wall time (min):',q(em))
    print(' share of run thinking chars in flagged blocks (upper bound):',q([x['chars_share'] for x in R]))
    ms=[x['min_share'] for x in R if x['min_share'] is not None]; print(' share of run wall time in episodes:',q(ms))
    print(' first flag at fraction of run:',q([x['first'] for x in R]))
    print(' top 8 by blocks:',[(x['run'],x['n'],x['eps']) for x in sorted(R,key=lambda x:-x['n'])[:8]])
