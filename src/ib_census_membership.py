"""Map frozen IB dashboard cells to exact source-sample IDs; no model calls."""
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT=Path('/Users/biancaganescu/Code/split-brain-hypothesis')
BASE=ROOT/'logs/dashboard_reasoning_census'
OUT=BASE/'ib'


def main():
    manifest=json.loads((OUT/'canonical_manifest.json').read_text())
    records=[r for r in manifest['samples'] if r['active']]
    byid={r['id']:r for r in records}
    data={f.stem:json.loads(f.read_text()) for f in (BASE/'data').glob('*.json')}
    normalized={r['id']:json.loads((OUT/'normalized_samples'/f"{r['id']}.json").read_text()) for r in records}
    def get(model=None,arms=None,cell=None,usable=False,setup=None):
        found=[]
        for r in records:
            if model is not None and r['model']!=model:continue
            rows=[x for x in r['manifest_rows'] if (arms is None or x.get('arm') in arms)
                  and (cell is None or x.get('cell')==cell)
                  and (not usable or x.get('labels',{}).get('status')=='usable')
                  and (setup is None or x.get('setup')==setup)]
            if rows:found.append(r)
        return found
    cells=[]
    def cell(graph,rowid,metric,rows,k,n,numer=None,note=None):
        ids=sorted({r['id'] for r in rows})
        cells.append(dict(graph=graph,dataset_row=rowid,metric=metric,k_displayed=k,n_displayed=n,
                          denominator_sample_ids=ids,denominator_count=len(ids),
                          denominator_matches_display=len(ids)==n if n is not None else None,
                          numerator_sample_ids=sorted(numer) if numer is not None else None,note=note))
    controls={'G4_C','D3_C','G_C'};off={'G4_A','D1_A','G_A'}
    for i,row in enumerate(data['ib_findings']['rows']):
        model=row['model'];f=row['finding'];measure=row['measure'];ref=f'ib_findings.rows[{i}]'
        if f in ('A','B'):
            for name,arms in [('base',controls if f=='A' else {'L_none'}),('cue',off if f=='A' else {'L_msg'})]:
                rows=get(model,arms)
                if f=='B' and measure!='kept':
                    working=measure=='working'
                    rows=[r for r in rows if any(x.get('labels',{}).get('hack_already_working_when_told') is working for x in r['manifest_rows'])]
                endpoint=('hacked_by_first_submission' if measure=='first' else 'hacked_by_end') if f=='A' else 'kept_the_hack'
                num=[r['id'] for r in rows if any(x.get('labels',{}).get(endpoint) for x in r['manifest_rows'])]
                cell('f-'+f.lower(),ref,name+'_'+measure,rows,row[name+'_k'],row.get(name+'_n',row.get('n')),num)
                if f=='A' and name=='base':cell('f-when',ref,measure,rows,row[name+'_k'],row[name+'_n'],num)
        else:
            cue='E_S' if f=='C' else 'E_D'
            if measure=='handed_in':
                for name,arm in [('base','E_N'),('cue',cue)]:
                    rows=get(model,{arm});num=[r['id'] for r in rows if any(x['labels'].get('handed_in_a_hack') for x in r['manifest_rows'])]
                    cell('f-'+f.lower(),ref,name+'_handed_in',rows,row[name+'_k'],row['n'],num)
            else:
                rows=get(model,{cue});num=[r['id'] for r in rows if any(x['labels'].get('reported_broken_test') for x in r['manifest_rows'])]
                cell('f-'+f.lower(),ref,'registered_report_without_hack',rows,row['k'],row['n'],num,
                     'Report category is conditioned on not handing in a hack; it is not all recognition/disclosure.')
    for i,row in enumerate(data['ib_chat']['rows']):
        arm=row['arm'];ref=f'ib_chat.rows[{i}]'
        if arm=='note':
            rows=[r for r in records if r['scope']=='ancillary_displayed_footnote']
            cell('f-chat',ref,'run3_harness_end_footnote',rows,15,18,note='Older run3 controls, distinct from current run4 comparison.')
            continue
        model=row['model']
        if arm.startswith('harness'):
            rows=get(model,controls);endpoint='hacked_by_first_submission' if arm=='harness_first' else 'hacked_by_end'
            num=[r['id'] for r in rows if any(x['labels'].get(endpoint) for x in r['manifest_rows'])]
            note=None
            if model=='DeepSeek V4 Pro' and arm=='harness_end':
                num=None;note='Displayed5/18 code-only differs from8/18 including edited tests; same18 episodes, endpoint differs.'
            cell('f-chat',ref,arm,rows,row['k'],row['n'],num,note)
        else:
            rows=get(model,cell='chat_siliconflow_64k' if arm=='chat_sf' else 'chat',usable=True)
            num=[r['id'] for r in rows if any(x['labels'].get('hacked_registered') for x in r['manifest_rows'])]
            cell('f-chat',ref,arm,rows,row['k'],row['n'],num,
                 'Denominator includes returned usable replies only; attempted and missing slots remain in canonical manifest.')
    for i,row in enumerate(data['ib_homework']['rows']):
        ref=f'ib_homework.rows[{i}]';kind=row['kind']
        if kind=='round1':
            model=row['model'];rows=get(model,cell='homework',usable=True)
            # Source manifest uses "hw" in some historical versions.
            if not rows:rows=get(model,cell='hw',usable=True)
            for metric,k in [('homework_hack',row['hw_k']),('names_contradiction',row['names_k'])]:
                field='hacked_registered' if metric=='homework_hack' else 'names_contradiction'
                num=[r['id'] for r in rows if any(x['labels'].get(field) for x in r['manifest_rows'])]
                cell('f-hw',ref,metric,rows,k,row['hw_n'],num)
            auto=get(model,cell='chat',usable=True);tasks={r['task'] for r in rows};auto=[r for r in auto if r['task'] in tasks]
            num=[r['id'] for r in auto if any(x['labels'].get('hacked_registered') for x in r['manifest_rows'])]
            cell('f-hw',ref,'automated_same_tasks',auto,row['auto_k'],row['auto_n'],num)
        elif kind=='rejection':
            rows=get(row['model'],cell='rejection')
            for rd in (1,2,3):
                field='hacked_round_fixed_extraction' if row.get('rule')=='fixed' else 'hacked_round_registered'
                num=[r['id'] for r in rows if any(x['labels'].get(field) is not None and x['labels'][field]<=rd for x in r['manifest_rows'])]
                cell('f-rej' if row.get('rule')!='registered' else 'f-rej-registered-sensitivity',ref,f'by_round_{rd}',rows,row['r'+str(rd)],row['n'],num,
                     'Conversation denominator retained even if later reply missing; zero does not establish completed no-hack.')
    for i,row in enumerate(data['ib_uptake_before']['rows']):
        if row['kind'] in ('pattern','judge'):
            rows=get(row['model'],off)
            cell('f-up' if row['kind']=='pattern' else 't-judge',f'ib_uptake_before.rows[{i}]','uptake_categories',rows,None,row['n'])
    for i,row in enumerate(data['ib_uptake']['rows']):
        if row['model']!='all':cell('uptake-after',f'ib_uptake.rows[{i}]','cue_mentioned_by_reply2',get(row['model'],{'L_msg'}),row['by_reply2'],row['n'])
    for i,row in enumerate(data['mi_ib_before']['rows']):
        rows=get(row['model'],controls);metric=row['key']
        if metric in ('ran','saw','honest'):
            rows=[r for r in rows if any(x['labels'].get('submissions',0)>0 for x in r['manifest_rows'])]
        if metric=='honest':
            filtered=[]
            for r in rows:
                seen=False
                for m in normalized[r['id']]['messages']:
                    if any(c['function']=='submit' for c in m['tool_calls']):break
                    if m['role']=='tool' and 'AssertionError' in m['text']:seen=True
                if seen:filtered.append(r)
            rows=filtered
        cell('f-mi-before',f'mi_ib_before.rows[{i}]',metric,rows,row['k'],row['n'],note='Membership derives stated tool/submit rule; original scratch analysis script not preserved. Numerator requires independent reconstruction.')
    for i,row in enumerate(data['mi_ib_cues']['rows']):
        arm='E_D' if row['key'].startswith('det_') else ('E_S' if row['key'].startswith('stop_') else 'E_N')
        cell('f-mi-cues',f'mi_ib_cues.rows[{i}]',row['key'],get(row['model'],{arm}),row['k'],row['n'],
             note='Reasoning word-pattern counts are lower bounds when reasoning absent; not semantic census labels.')
    examples=[]
    for row in data['ib_examples']['rows']:
        where=row['where'];tail=re.search(r'…([^ ]+\.eval)',where).group(1)
        sample=re.search(r'sample (.*?) · epoch',where).group(1);epoch=int(re.search(r'epoch (\d+)',where).group(1));message=int(re.search(r'message (\d+)',where).group(1))
        matches=[r for r in records if r['source']['path'].endswith(tail) and str(r['source']['sample_id'])==sample and r['source']['epoch']==epoch]
        assert len(matches)==1,(row['id'],matches)
        examples.append(dict(example_id=row['id'],sample_id=matches[0]['id'],message=message,field=row['field'],source=row['where']))
    memberships=defaultdict(set)
    for c in cells:
        for rid in c['denominator_sample_ids']:memberships[rid].add(c['graph'])
    for r in records:
        # Record data-bearing attempted slots separately from plotted denominator.
        r['exact_denominator_graphs']=sorted(memberships[r['id']])
    mismatches=[c for c in cells if c['denominator_matches_display'] is False]
    result={'scope':'Frozen original IB page; graph-cell denominator memberships, not completed semantic review.',
            'cells':cells,'examples':examples,'denominator_mismatches':mismatches,
            'missing_scope_notes':['12purpose_mc ancillary replies are in packet_index.json, not these outcome cells.',
                                   '8superseded attempts excluded; current attempted-but-unusable records retained in canonical manifest but excluded from usable-reply denominators.',
                                   'Upper-level graphical samples are reused across figures. Do not sum denominators.']}
    (OUT/'graph_membership.json').write_text(json.dumps(result,indent=2)+'\n')
    (OUT/'canonical_manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'cells':len(cells),'examples':len(examples),'mismatches':mismatches},indent=2))


if __name__=='__main__':main()
