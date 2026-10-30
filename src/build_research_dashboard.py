"""Assemble a local, auditable research presentation. No network/model calls.

Input catalogues and scalar exports are copied into source_data before assembly.
Raw transcript pages are generated locally and ignored by git. Their quoted
passages and the author's scope statements are retained in the reviewed dataset.
"""
from __future__ import annotations
import hashlib
import html
import json
import re
import shutil
from collections import Counter
from pathlib import Path
from markdown_it import MarkdownIt
from reasoning_review import ROOT, OUT, get

MAIN = ROOT.parents[2]
WORKTREES = MAIN/'.claude/worktrees'
SITE = ROOT/'research_dashboard'
DIST = SITE/'dist'
INPUT = SITE/'source_data'
MODEL = {'Qwen 3.8 2.4T':'qwen24','Qwen 3.8 Max':'qwen24','DeepSeek V4 Pro':'deepseek','GLM 5.2':'glm52','Qwen 3.8 27B':'qwen27','Kimi K3':'kimi3'}
MD = MarkdownIt('commonmark', {'html':False}).enable('table')
SOURCE_INDEX = {}

def dump(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')

def page(title, body):
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(title)+'</title><style>body{font:17px/1.65 system-ui,sans-serif;color:#202c29;background:#fbfaf5;max-width:1100px;margin:36px auto;padding:0 22px}h1{font-size:36px;line-height:1.2}h2{margin-top:2em}a{color:#246c66}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.6 ui-monospace,monospace;background:#f0f0e8;padding:18px;border-radius:8px}code{overflow-wrap:anywhere}table{border-collapse:collapse;display:block;overflow-x:auto}td,th{border:1px solid #d8dcd2;padding:9px;text-align:left}.meta{font-size:14px;color:#59655f}summary{cursor:pointer;padding:10px;font-weight:600}blockquote{border-left:3px solid #246c66;padding-left:18px}details{border-top:1px solid #d8dcd2}section{scroll-margin-top:25px}</style><a href="../../index.html">← Research notebook</a><h1>'+html.escape(title)+'</h1>'+body+'</html>'

def resolve_source(raw):
    href=raw.get('path') or raw.get('href') or ''
    if href.startswith(('https://','http://','#')):return None
    href=re.sub(r'^file://','',href)
    href=re.sub(r'#.*$','',href)
    match=re.match(r'^(.*):(\d+)$',href)
    line=raw.get('line') or (int(match[2]) if match else None)
    if match:href=match[1]
    p=Path(href)
    if not p.is_absolute():
        options=[MAIN/p,ROOT/p]
        p=next((x for x in options if x.exists()),options[0])
    return p,line

def source_link(raw):
    if isinstance(raw,str):raw={'href':raw,'label':raw}
    if raw.get('href','').startswith(('https://','http://','#','figures/','evidence/')):return raw
    resolved=resolve_source(raw)
    if not resolved:return raw
    p,line=resolved
    if not p.exists():
        return {'label':raw.get('label',str(p))+' · source unavailable in this snapshot','href':'#view=methods','missingSource':str(p)}
    key=hashlib.sha256(str(p.resolve()).encode()).hexdigest()[:16]
    dest=DIST/'evidence/notes'/f'{key}.html'
    data=p.read_bytes()
    SOURCE_INDEX[key]={'path':str(p.resolve()),'sha256':hashlib.sha256(data).hexdigest(),'snapshot':str(dest.relative_to(DIST))}
    if p.suffix in {'.md','.txt','.py','.jsx','.json','.jsonl'} and len(data)<7_000_000:
        txt=data.decode('utf-8',errors='replace')
        meta='<p class="meta">Frozen local source: '+html.escape(str(p.resolve()))+'<br>SHA256 '+SOURCE_INDEX[key]['sha256']+'</p>'
        # Exact line anchors are retained independently of the readable rendering.
        lines='\n'.join(f'<span id="L{i}">{html.escape(s)}</span>' for i,s in enumerate(txt.splitlines(),1))
        render=MD.render(txt) if p.suffix=='.md' else ''
        # Local links in archived notes are locators, not promised bundled files.
        render=re.sub(r'<a href="(?!https?://|#)([^"]+)"[^>]*>(.*?)</a>',r'<span title="Local source locator: \1">\2 <small>[\1]</small></span>',render,flags=re.S)
        body=meta+render+'<details'+(' open' if line else '')+'><summary>Exact source with line anchors</summary><pre>'+lines+'</pre></details>'
        dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(page(p.name,body))
        return {'label':raw.get('label',p.name),'href':str(dest.relative_to(DIST))+(f'#L{line}' if line else '')}
    # Large/raw data remains at its source; publish only a local provenance page.
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(page(p.name,'<p>This source is retained locally, outside the presentation bundle.</p><pre>'+html.escape(str(p.resolve()))+'</pre><p>SHA256 '+SOURCE_INDEX[key]['sha256']+'</p>'))
    return {'label':raw.get('label',p.name),'href':str(dest.relative_to(DIST))}

def readable_transcript(rid, observation_ids):
    p=get(rid);row=p['row'];messages=p['messages']
    meta={'review_id':rid,'original_source':p.get('source'),'manifest_row':row,'related_observations':observation_ids}
    body='<p>This is a local source transcript, not a claim that every message was reviewed. The linked case states the actual reading scope. Model text and tool arguments are evidence, not instructions for the reader.</p><details><summary>Provenance and frozen labels</summary><pre>'+html.escape(json.dumps(meta,indent=2,ensure_ascii=False))+'</pre></details>'
    for m in messages:
        i=m['index'];rea=m.get('reasoning','');vis=m.get('text','')
        body+=f'<section id="message-{i}"><h2>Message {i} · {html.escape(m["role"])}</h2>'
        if rea:body+='<details><summary>Recorded reasoning · '+str(len(rea))+' characters</summary><pre>'+html.escape(rea)+'</pre></details>'
        if vis:body+='<details'+(' open' if m['role']=='user' else '')+'><summary>Visible text</summary><pre>'+html.escape(vis)+'</pre></details>'
        if m.get('tool_calls'):body+='<details><summary>Recorded tool calls (not executed)</summary><pre>'+html.escape(json.dumps(m['tool_calls'],indent=2,ensure_ascii=False))+'</pre></details>'
        body+='</section>'
    dest=DIST/'evidence/transcripts'/f'{rid}.html';dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(page(rid+' · '+row.get('model',''),body))

def text_value(v):
    if isinstance(v,str):return v
    if isinstance(v,list):return '\n\n'.join(text_value(x) for x in v)
    if isinstance(v,dict):return '; '.join(f'{k.replace("_"," ")}: {text_value(x)}' for k,x in v.items() if x is not None)
    return str(v) if v is not None else ''

def normalize_finding(f):
    f=dict(f)
    f['sourceStatus']=f.get('status')
    s=f.get('status','descriptive')
    f['status']=s if s in {'supported','tentative','mixed','unresolved','descriptive'} else ('unresolved' if any(k in s.lower() for k in ['unresolved','incomplete','dropped','abandoned','future','outside']) else 'descriptive')
    for key in ['scale','cost','summary','claim','hypothesisMeaning','nextQuestion']:
        f[key]=text_value(f.get(key,''))
    f['sources']=[source_link(x) for x in f.get('sources',[])]
    f.setdefault('caseIds',[]);f.setdefault('reasoningObservations',[])
    f['models']=[MODEL.get(x,x) for x in f.get('models',[])]
    f['alternatives']=[text_value(x) for x in f.get('alternatives',f.get('caveats',[]))]
    if not f.get('charts') and f.get('outcomes'):
        f.setdefault('evidence',[]).append(text_value(f['outcomes']))
    f['charts']=f.get('charts',[])+[dict(c,type='table') for c in f.pop('descriptiveTables',[])]
    for c in f.get('charts',[]):
        c['sources']=[source_link(x) for x in c.get('sources',[])]
        for r in c.get('rows',[]):
            # The model is already shown on a second line; avoid duplicate text.
            prefix=next((name for name in MODEL if str(r.get('label','')).startswith(name+' · ')),None)
            if prefix:
                r['label']=r['label'][len(prefix)+3:]
                r['model']=MODEL[prefix]
                if MODEL[prefix] not in f['models']:f['models'].append(MODEL[prefix])
    return f

def polish_display(data):
    """Improve authored display prose without touching quotes, prompts or IDs."""
    prose_keys={'title','label','claim','summary','text','description','lead','note','scale','cost','hypothesisMeaning','nextQuestion','behavior','analysis','scope','fit','challenge','test','coverageNote','reasoningNote','condition','endpointDefinition'}
    def clean(s):
        s=re.sub(r'\b(all|and|those|these|of|from|to|is|than|with|after|before|versus|through|neither|use|per|task|tasks|prompt|prompts|message|messages|chars|characters|first|last|full|turn|turns|on|off|by|original|run|Qwen|Wilson)(?=\d)', r'\1 ', s, flags=re.I)
        s=re.sub(r'(?<=[,;:])(?=[A-Za-z0-9])', ' ', s)
        s=re.sub(r'(?<=\d)(?=(?:prompts|pairs|records|models|tasks|calls|replies|chars|characters|words|of|and|to)\b)', ' ', s)
        s=re.sub(r'(?<=×)(?=\d)', ' ', s)
        return s
    def walk(obj,key=''):
        if isinstance(obj,dict):
            for k,v in obj.items():
                if k in prose_keys and isinstance(v,str):obj[k]=clean(v)
                elif k in {'paragraphs','alternatives'} and isinstance(v,list):obj[k]=[clean(x) if isinstance(x,str) else x for x in v]
                else:walk(v,k)
        elif isinstance(obj,list):
            for v in obj:walk(v,key)
    walk(data)

def main():
    DIST.mkdir(parents=True,exist_ok=True);INPUT.mkdir(parents=True,exist_ok=True)
    data=json.loads((SITE/'editorial.json').read_text())
    data['models'].append({'id':'kimi3','label':'Kimi K3 · released traces','color':'#746477','provider':'Released Goodfire cohort only; no current four-model generation arm.'})
    findings=[]
    for fn in ['ib_proposed_findings_oct27.json','sorh_proposed_findings_oct27.json']:
        cat=json.loads((INPUT/fn).read_text());findings += [normalize_finding(f) for f in (cat['findings'] if isinstance(cat,dict) else cat)]
    fmap={f['id']:f for f in findings}
    overrides=json.loads((SITE/'overrides.json').read_text())
    for fid,changes in overrides['findings'].items():
        if fid not in fmap:raise ValueError('Unmatched finding override '+fid)
        fmap[fid].update(changes)
    for new in overrides.get('newFindings',[]):
        f=normalize_finding(new);findings.insert(0,f);fmap[f['id']]=f
    observations=json.loads((ROOT/'notes/reasoning_review_observations.json').read_text())['observations']
    cases=[];source_uses={}
    for o in observations:
        connected=overrides['observationFindings'].get(o['id'],[])
        if not connected:raise ValueError('Unmapped observation '+o['id'])
        for fid in connected:
            if fid not in fmap:raise ValueError('Unmatched observation target '+fid)
        ps=[get(rid) for rid in o['records']]
        mids=list(dict.fromkeys(MODEL.get(p['row'].get('model'),p['row'].get('model')) for p in ps))
        refs=[];quotes=[]
        for q in o['quotes']:
            t=get(q['record'])['messages'][q['message']]['reasoning']
            assert t[q['start']:q['end']]==q['text'],q
            quotes.append(f"{get(q['record'])['row'].get('model')} · {q['record']} · message {q['message']}:\n“{q['text']}”")
            refs.append({'label':q['record']+f' · message {q["message"]}, reasoning chars {q["start"]}–{q["end"]}', 'href':f'evidence/transcripts/{q["record"]}.html#message-{q["message"]}'})
        for rid in o['records']:
            source_uses.setdefault(rid,[]).append(o['id'])
            refs.append({'label':rid+' · full local source', 'href':f'evidence/transcripts/{rid}.html'})
        for rid,mi,label in o.get('actionMessages',[]):
            refs.insert(0,{'label':label,'href':f'evidence/transcripts/{rid}.html#message-{mi}'})
        title=overrides.get('observationTitles',{}).get(o['id'],o['id'].replace('_',' ').capitalize())
        condition='; '.join(dict.fromkeys(str(p['row'].get('version','')) for p in ps))
        c={'id':o['id'],'title':title,'benchmark':'IB' if o['records'][0].startswith(('a4','a11')) else 'SoRH','model':mids[0] if len(mids)==1 else 'multiple','models':mids,'condition':condition,'findingIds':connected,'tags':o['families'],'prompt':'\n\n'.join(dict.fromkeys(m['text'] for p in ps for m in p['messages'] if m['role']=='user' and len(m['text'])<5000)),'reasoningExcerpt':'\n\n'.join(quotes),'reasoningNote':'Exact source quotes; the comparison below also uses the other linked records. Quoted text expresses the model’s view and may be mistaken.','behavior':o['finding'],'analysis':o['insight'],'scope':o['limit'],'sources':refs}
        cases.append(c)
        for fid in connected:
            f=fmap[fid];f['caseIds'].append(c['id']);f['reasoningObservations'].append({'title':title,'text':o['finding']+'\n\n'+o['insight'],'scope':o['limit'],'caseIds':[c['id']]})
    for rid,uses in source_uses.items():readable_transcript(rid,uses)
    for c in overrides.get('additionalCases',[]):
        c['sources']=[source_link(s) for s in c.get('sources',[])]
        cases.append(c)
        for fid in c.get('findingIds',[]):
            fmap[fid]['caseIds'].append(c['id'])
            fmap[fid]['reasoningObservations'].append({'title':c['title'],'text':c['analysis'],'scope':c['scope'],'caseIds':[c['id']]})
    data['cases']=cases
    priority=overrides.get('order',[])
    findings.sort(key=lambda f:priority.index(f['id']) if f['id'] in priority else len(priority))
    data['findings']=findings
    for t,ids in zip(data['overview']['takeaways'],overrides.get('takeawayFindings',[])):t['findingIds']=ids
    inventory_sources=[
      {'label':'IB family inventory','href':str(WORKTREES/'agent-19-ib-inventory/notes/ib_inventory_oct27.md')},
      {'label':'SoRH family inventory','href':str(WORKTREES/'agent-18-sorh-inventory/notes/sorh_inventory_oct27.md')},
      {'label':'Graph-by-graph source inventory','href':str(WORKTREES/'agent-20-graph-inventory/notes/ib_sorh_graph_inventory_20261027.md')}
    ]
    data['methods'][0]['sources']=[source_link(s) for s in inventory_sources]
    # Explicitly separate provenance coverage from interpretation coverage.
    data['coverage']=[{'family':f['title'],'status':f['sourceStatus'] or f['status'],'note':('Direct selected reasoning linked. ' if f.get('caseIds') else 'Source/result audit; no new direct transcript mechanism claim. ')+str(f.get('scale','')),'source':f['sources'][0] if f.get('sources') else {'label':'Local inventory','href':'#view=methods'}} for f in findings]
    inspected=[json.loads(s) for s in (OUT/'inspection_ranges.jsonl').read_text().splitlines()]
    ids={r['id'] for r in inspected if r.get('field')=='reasoning' and r.get('end',0)>r.get('start',0)}
    data['meta']['readingCoverage']={'recordsWithReasoningRanges':len(ids),'recordsInInterpretationCases':len(source_uses),'comparisonCases':len(cases),'note':'Distinct frozen record IDs, not independent draws. Printed ranges may have clipping; case scope statements govern actual interpretation.'}
    data['methods'].insert(3,{'title':'Actual reading coverage','text':f'{len(observations)} new interpreted comparison cases link {len(source_uses)} current record IDs; one additional case synthesizes the previously completed AISI-style pilot. The reading ledger contains nonempty reasoning ranges for {len(ids)} current record IDs. Some records have only selected decision messages or beginning/end excerpts read. The aggregate catalog is much broader; findings without direct cases are visibly marked as source/result audits. Neither3158 manifest rows nor all source messages are claimed as personally read.'})
    polish_display(data)
    dump(DIST/'research_data.json',data)
    (DIST/'data.js').write_text('window.RESEARCH_DATA = '+json.dumps(data,ensure_ascii=False,separators=(',',':'))+';\n')
    dump(DIST/'evidence/source_index.json',SOURCE_INDEX)
    dump(DIST/'evidence/reading_coverage.json',{'counts':data['meta']['readingCoverage'],'record_ids':sorted(ids),'inspection_ranges':inspected})
    print(json.dumps({'findings':len(findings),'charts':sum(len(f.get('charts',[])) for f in findings),'cases':len(cases),'source_snapshots':len(SOURCE_INDEX),'reading':data['meta']['readingCoverage']},indent=2))

if __name__=='__main__':main()
