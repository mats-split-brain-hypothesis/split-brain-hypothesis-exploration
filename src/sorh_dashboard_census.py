"""Offline mapping and complete-range reader for the single-turn dashboard census.

This never calls a model. Reading coverage is recorded only by explicit annotate
commands after an agent has read the displayed complete range and written a
semantic annotation. File discovery and hashing are not semantic review.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

ROOT = Path('/Users/biancaganescu/Code/split-brain-hypothesis')
BASE = ROOT/'logs/dashboard_reasoning_census'
OUT = BASE/'sorh_single'
MANIFEST = ROOT/'logs/reasoning_review/2026-10-27/a1_manifest.json'
def load(p): return json.loads(Path(p).read_text())
def digest(s): return hashlib.sha256(s.encode()).hexdigest()
def loc(path,line=None):return str(path)+(f':{line}' if line else '')

def map_samples():
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'samples').mkdir(exist_ok=True)
    data={p.stem:load(p) for p in (BASE/'data').glob('*.json')}
    manifest=load(MANIFEST)['rows']
    active=[r for r in manifest if not r['labels'].get('superseded_by_redraw')]
    source_rows={}
    def put(source,graph,m=None,version=None,unit=None,labels=None):
        p=Path(source['path']);line=source.get('line') if source['kind']=='jsonl' else None
        key=loc(p,line)
        if key not in source_rows:
            source_rows[key]={'source':source,'graphs':set(),'model':m,'condition':version,
                              'prompt_id':unit,'labels':labels or {}}
        source_rows[key]['graphs'].add(graph)
    direct=['sorh_pad1','sorh_pad2','sorh_pad3','sorh_pad5','sorh_bf_padded','sorh_cycles','sorh_tokens']
    graph_cells={g:{r['cell'] for r in data[g]['rows']} for g in direct}
    graph_cells.update({'sorh_bf_paired':{'B','G','G__acceptable','r_student','r_student__teacher_reads'},
        'sorh_f_dense':{'B','G__acceptable'},'sorh_e':{'B'},'sorh_cycles_meta':graph_cells['sorh_cycles'],
        'mi_sorh_floor':{'B','G'},'mi_sorh_split:class_notes':{'r_student'}})
    for graph,cells in graph_cells.items():
        for r in active:
            if r['version'] in cells:
                put(r['source'],graph,r['model'],r['version'],r['unit'],r['labels'])
    for r in active:
        if r['statement']['id']=='mean':put(r['source'],'sorh_mean',r['model'],r['version'],r['unit'],r['labels'])
    # C/D were judged on their original exact source records before redraw overlays.
    for stage,graph in [('talker_doer','sorh_c'),('score_estimate','sorh_d')]:
        for line in (ROOT/'logs/sorh_ablation'/stage/'judged.jsonl').read_text().splitlines():
            r=json.loads(line)
            put({'kind':'jsonl','path':str(ROOT/'logs/sorh_ablation'/r['stage']/'records.jsonl'),'line':r['line']},
                graph,r['model'],r['cell'],r['prompt_id'])
    excluded=[]
    for r in data['sorh_examples']['rows']:
        match=re.fullmatch(r'(logs/.+\.jsonl) line (\d+)',r.get('where',''))
        if not match:continue
        if '/mt' in match[1]:
            excluded.append({'example_id':r['id'],'source':r['where'],'reason':'multi-turn; another owner'})
            continue
        put({'kind':'jsonl','path':str(ROOT/match[1]),'line':int(match[2])},
            'sorh_examples:'+r['id'],r.get('model'),r.get('cell'),r.get('prompt'))
    file_cache={};canonical={};aliases={}
    for source_key,spec in source_rows.items():
        s=spec['source'];path=Path(s['path'])
        if s['kind']=='jsonl':
            if path not in file_cache:file_cache[path]=path.read_text().splitlines()
            raw=file_cache[path][s['line']-1]
        else:raw=path.read_text()
        r=json.loads(raw)
        prompt=r.get('prompt','');reasoning=r.get('reasoning','');reply=r.get('reply','')
        identity=digest(json.dumps([r.get('model',spec['model']),prompt,reasoning,reply],ensure_ascii=False))
        stage=r.get('stage',path.parent.name)
        unit=r.get('prompt_id',spec['prompt_id'])
        condition=r.get('cell',spec['condition'])
        sid=f"{stage}__{condition}__{unit}__s{r.get('sample',0)}__{identity[:10]}"
        sid=re.sub('[^A-Za-z0-9_.-]+','_',sid)
        if identity in aliases:
            item=canonical[aliases[identity]]
            item['sources'].append({'locator':source_key,'record_sha256':digest(raw)})
            item['graphs']=sorted(set(item['graphs'])|spec['graphs'])
            continue
        aliases[identity]=sid
        packet={'id':sid,'model':spec['model'],'model_api':r.get('model'),
            'stage':stage,'condition':condition,'condition_label':spec['condition'],
            'prompt_id':unit,'sample':r.get('sample'),
            'sources':[{'locator':source_key,'record_sha256':digest(raw)}],
            'graphs':sorted(spec['graphs']),'labels':spec['labels'],
            'finish':r.get('finish'),'provider':r.get('provider'),'effort':r.get('effort'),
            'prompt':prompt,'reasoning':reasoning,'reply':reply,
            'sha256':{f:digest(v) for f,v in [('prompt',prompt),('reasoning',reasoning),('reply',reply)]},
            'chars':{'prompt':len(prompt),'reasoning':len(reasoning),'reply':len(reply)},
            'utf8_bytes':{f:len(v.encode()) for f,v in [('prompt',prompt),('reasoning',reasoning),('reply',reply)]},
            'reasoning_status':'present' if reasoning else 'missing'}
        canonical[sid]=packet
    items=sorted(canonical.values(),key=lambda x:(x['condition']!='B',x['model'] or '',str(x['prompt_id']),x['condition'],x['id']))
    for p in items:(OUT/'samples'/f"{p['id']}.json").write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n')
    index=[{k:v for k,v in p.items() if k not in ['prompt','reasoning','reply']} for p in items]
    bygraph=defaultdict(list);bymodel=defaultdict(Counter);bycondition=defaultdict(Counter)
    for p in index:
        for g in p['graphs']:bygraph[g].append(p['id'])
        b=bymodel[p['model']];b['samples']+=1
        for f,n in p['chars'].items():b[f+'_chars']+=n
        for f,n in p['utf8_bytes'].items():b[f+'_bytes']+=n
        b['missing_reasoning']+=p['reasoning_status']=='missing'
        c=bycondition[(p['model'],p['condition_label'])];c['samples']+=1
        for f,n in p['chars'].items():c[f+'_chars']+=n
        for f,n in p['utf8_bytes'].items():c[f+'_bytes']+=n
        c['missing_reasoning']+=p['reasoning_status']=='missing'
        c['finish_length']+=p.get('finish')=='length'
        c['max_reasoning_chars']=max(c['max_reasoning_chars'],p['chars']['reasoning'])
    conditions=[{'model':m,'condition':c,**v} for (m,c),v in sorted(bycondition.items())]
    (OUT/'condition_inventory.json').write_text(json.dumps(conditions,ensure_ascii=False,indent=2)+'\n')
    summary={'scope':'Frozen results_dashboard.original.html sorh.html, single-turn only. Graph reuse deduplicated by complete model/prompt/reasoning/reply hash.',
             'source_manifest':str(MANIFEST),'source_manifest_sha256':digest(MANIFEST.read_text()),
             'unique_samples':len(items),'raw_source_locations':len(source_rows),'models':bymodel,
             'totals':dict(sum(bymodel.values(),Counter())),
             'max_reasoning_chars':max(p['chars']['reasoning'] for p in items),
             'finish_counts':dict(Counter(p.get('finish') for p in items)),
             'dashboard_input':str(BASE/'results_dashboard.original.html'),
             'dashboard_input_sha256':hashlib.sha256((BASE/'results_dashboard.original.html').read_bytes()).hexdigest(),
             'dataset_sources':{g:{'path':str(BASE/'data'/f'{g}.json'),
                                'sha256':hashlib.sha256((BASE/'data'/f'{g}.json').read_bytes()).hexdigest(),
                                'source':data[g].get('source')}
                                for g in data if g in bygraph or g=='sorh_examples'},
             'graph_counts':{g:len(ids) for g,ids in bygraph.items()},
             'excluded_examples':excluded,
             'semantic_reviewed_samples':0,'note':'Indexing, hashing and packet creation are not semantic reading. See annotations.jsonl and progress.json for actual coverage.'}
    (OUT/'sample_index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n')
    (OUT/'graph_sample_map.json').write_text(json.dumps(bygraph,ensure_ascii=False,indent=2)+'\n')
    (OUT/'mapping_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2))

def read_sample(a):
    p=load(OUT/'samples'/f'{a.id}.json');f=a.field;s=p[f]
    end=min(len(s),a.end) if a.end is not None else len(s)
    assert 0<=a.start<=end<=len(s)
    print(json.dumps({k:p[k] for k in ['id','model','condition','prompt_id','graphs','finish']},ensure_ascii=False))
    print(f'FIELD {f} CHAR_RANGE [{a.start},{end}) TOTAL {len(s)} SHA256 {p["sha256"][f]}')
    print(s[a.start:end])
    print(f'END_FIELD {f} CHAR_RANGE [{a.start},{end})')

def status():
    index=load(OUT/'sample_index.json');ap=OUT/'annotations.jsonl'
    anns=[json.loads(s) for s in ap.read_text().splitlines() if s.strip()] if ap.exists() else []
    coverage=defaultdict(lambda:defaultdict(list));completed=set()
    for a in anns:
        for field,ranges in a.get('coverage',{}).items():coverage[a['id']][field]+=ranges
        if a.get('complete'):completed.add(a['id'])
    def union(ranges):
        result=[]
        for start,end in sorted(ranges):
            if result and start<=result[-1][1]:result[-1][1]=max(result[-1][1],end)
            else:result.append([start,end])
        return result
    reads={sid:{f:union(rr) for f,rr in fields.items()} for sid,fields in coverage.items()}
    for r in index:
        if r['id'] not in completed:continue
        assert all(reads[r['id']].get(f)==[[0,n]] or n==0 for f,n in r['chars'].items()),r['id']
    out={'total_samples':len(index),'complete_samples':len(completed),'partial_samples':len(coverage)-len(completed),
         'coverage':reads,'complete_ids':sorted(completed),'annotation_records':len(anns)}
    (OUT/'progress.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in out.items() if k not in ['coverage','complete_ids']},indent=2))

if __name__=='__main__':
    ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='command',required=True)
    sub.add_parser('map');sub.add_parser('status')
    r=sub.add_parser('read');r.add_argument('id');r.add_argument('--field',choices=['prompt','reasoning','reply'],default='reasoning');r.add_argument('--start',type=int,default=0);r.add_argument('--end',type=int)
    a=ap.parse_args()
    if a.command=='map':map_samples()
    elif a.command=='read':read_sample(a)
    else:status()
