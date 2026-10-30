"""Package every retained SoRH probe explanation; no API calls or new clipping.

These are visible explanations, not saved hidden reasoning. Original clipping
is preserved and disclosed. Repeated answers share one exact context packet.
"""
import ast
import collections
import hashlib
import json
from pathlib import Path

ROOT=Path('/Users/biancaganescu/Code/split-brain-hypothesis')
OUT=ROOT/'logs/dashboard_reasoning_census/sorh_switch'


def sha(s):return hashlib.sha256(s.encode()).hexdigest()
def lines(path):return path.read_text().splitlines()


def main():
    import tiktoken
    enc=tiktoken.get_encoding('o200k_base')
    source=ROOT/'.claude/worktrees/agent-5-grader-definition/src/eval_probe.py'
    tree=ast.parse(source.read_text())
    constants={}
    def literal(node):
        if isinstance(node,ast.Constant):return node.value
        if isinstance(node,ast.Name):return constants[node.id]
        if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Add):return literal(node.left)+literal(node.right)
        if isinstance(node,ast.Dict):return {literal(k):literal(v) for k,v in zip(node.keys,node.values)}
        raise ValueError('Unsupported static expression')
    for n in tree.body:
        if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ['PREAMBLE','PROBES'] for t in n.targets):
            constants[next(t.id for t in n.targets if isinstance(t,ast.Name))]=literal(n.value)
    question=constants['PROBES']
    inputs={}
    for a,p in [('a1_wildchat','p1_wildchat'),('a1_ds_wildchat','p1_ds_wildchat'),('a1_glm_wildchat','p1_glm_wildchat'),('a1_qwen27b_wildchat','p1_qwen27b_wildchat')]:
        file=ROOT/'logs/eval_probe'/f'{p}.jsonl'
        inputs[a]={r['item']:(r,{'path':str(file),'line':i,'row_sha256':sha(raw)}) for i,raw in enumerate(lines(file),1) for r in [json.loads(raw)]}
    manifest=[json.loads(s) for s in lines(OUT/'probe_calls.jsonl')]
    cache={};groups=collections.defaultdict(list)
    for m in manifest:
        file=m['source']['path']
        if file not in cache:cache[file]=lines(Path(file))
        raw=cache[file][m['source']['line']-1];assert sha(raw)==m['source']['row_sha256']
        r=json.loads(raw)
        if 'prompt' in r:
            chat=r['prompt'][:-1];q=r['prompt'][-1];context_source=None;context_was_clipped=None
        else:
            inp,context_source=inputs[Path(file).stem][r['item']]
            chat=inp['chat'];q={'role':'user','content':question[r['probe']]};context_was_clipped=inp.get('cut')
        # Same visible context and serving model, not merely the same prompt ID.
        key=sha(json.dumps({'model':r['model'],'provider':r.get('provider'),'cell':m['cell'],'context':m.get('context'),'chat':chat},ensure_ascii=False,sort_keys=True))
        groups[key].append((m,r,chat,q,context_source,context_was_clipped))
    directory=OUT/'probe_packets';directory.mkdir(exist_ok=True)
    pm=[];seen=set()
    for key,group in sorted(groups.items()):
        ident='sorh-probe-'+key[:20];chat=group[0][2]
        questions={json.dumps(x[3],ensure_ascii=False,sort_keys=True) for x in group}
        prompt='This is an analysis of STORED VISIBLE PROBE EXPLANATIONS ONLY. Hidden reasoning was not retained by the original runner. Explanations were clipped there to 800 characters; no missing text may be inferred. Read every retained explanation and distinguish literal interpretation of the user message from evidence about behavior. The following is the exact shared visible context.\n\n'
        prompt+='\n\n'.join('['+str(msg.get('role','message')).upper()+']\n'+str(msg.get('content','')) for msg in chat)
        prompt+='\n\nPROBE QUESTIONS\n'+'\n\n'.join('[USER PROBE QUESTION]\n'+str(json.loads(q)['content']) for q in sorted(questions))
        call_labels={m['sample_id']:'CALL '+str(i+1).zfill(3) for i,(m,r,*_) in enumerate(group)}
        reason='HIDDEN REASONING: NOT STORED. These are visible answer explanations, not hidden chain-of-thought.\n\n'+'\n\n'.join('[STORED VISIBLE EXPLANATION | '+call_labels[m['sample_id']]+' | '+str(r['probe'])+' | draw '+str(r['sample'])+']\n'+str(r.get('explanation')or'') for m,r,*_ in group)
        reply='\n\n'.join('[STORED LABEL | '+call_labels[m['sample_id']]+']\nparsed='+str(r.get('answer',r.get('label')))+'\nraw label='+str(r.get('raw',r.get('raw_label'))) for m,r,*_ in group)
        packet={'id':ident,'schema':'retained-probe-explanations-v1','review_fields':{'prompt':prompt,'reasoning':reason,'reply':reply},
                'review_content_kind':'visible_explanation_only','hidden_reasoning_available':False,
                'original_explanation_clip_chars':800,'no_additional_clipping':True,
                'model':group[0][1]['model'],'provider':group[0][1].get('provider'),
                'prompt_id':group[0][0]['prompt_id'],'cell':group[0][0]['cell'],'context':group[0][0].get('context'),
                'graph_dataset_ids':sorted({g for x in group for g in x[0]['graph_dataset_ids']}),
                'context_source':group[0][4],'original_context_was_clipped':group[0][5],
                'probe_question_source':{'path':str(source),'definition':'PROBES literal; for saved prompt arrays the actual saved question is used'},
                'review_call_labels':{v:k for k,v in call_labels.items()},'calls':[m for m,r,*_ in group],'read_status':'not_read'}
        members=[];reason_cursor=0;reply_cursor=0
        for m,r,*_ in group:
            marker='[STORED VISIBLE EXPLANATION | '+call_labels[m['sample_id']]+' | '+str(r['probe'])+' | draw '+str(r['sample'])+']\n'
            start=reason.index(marker,reason_cursor)+len(marker);end=start+len(r.get('explanation')or'');reason_cursor=end
            assert reason[start:end]==(r.get('explanation')or'')
            out_marker='[STORED LABEL | '+call_labels[m['sample_id']]+']\n'
            out_start=reply.index(out_marker,reply_cursor)+len(out_marker)
            next_marker=reply.find('\n\n[STORED LABEL | ',out_start)
            out_end=next_marker if next_marker>=0 else len(reply);reply_cursor=out_end
            members.append({'id':m['sample_id'],'label':call_labels[m['sample_id']]+' '+str(r['probe']),
                            'field_ranges':{'prompt':[[0,len(prompt)]],'reasoning':[[start,end]] if end>start else [],'reply':[[out_start,out_end]]},
                            'primary_field_ranges':{'reasoning':[[start,end]] if end>start else [],'reply':[[out_start,out_end]]},
                            'availability':{'review_content_kind':'visible_explanation_only','hidden_reasoning_available':False,
                                            'source_clip_chars':800,'source_at_clip_limit_or_ellipsis':m['visible_explanation']['at_clip_limit_or_ellipsis'],
                                            'offset_unit':'unicode_codepoints'},'source':m['source']})
        packet['review_members']=members
        ids={m['sample_id']for m,r,*_ in group};assert not seen&ids;seen.update(ids)
        text=json.dumps(packet,ensure_ascii=False,separators=(',',':'))+'\n';path=directory/(ident+'.json');path.write_text(text)
        tok=sum(len(enc.encode(v,disallowed_special=()))for v in packet['review_fields'].values())
        pm.append({'id':ident,'path':str(path),'sha256':sha(text),'model':packet['model'],'cell':packet['cell'],
                   'graph_dataset_ids':packet['graph_dataset_ids'],'calls':len(group),'source_sample_ids':sorted(ids),
                   'tokens_o200k_base':tok,'serialized_utf8_bytes':len(text.encode()),
                   'retained_explanation_chars':sum(m['visible_explanation']['chars']for m,r,*_ in group),
                   'review_content_kind':'visible_explanation_only','hidden_reasoning_available':False,'read_status':'not_read'})
    assert seen=={m['sample_id']for m in manifest}
    (OUT/'probe_packet_manifest.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n'for r in pm))
    summary={'packets':len(pm),'retained_probe_calls':len(seen),'tokens_o200k_base':sum(r['tokens_o200k_base']for r in pm),
             'max_packet_tokens':max(r['tokens_o200k_base']for r in pm),'packets_above_100k':sum(r['tokens_o200k_base']>100000 for r in pm),
             'serialized_utf8_bytes':sum(r['serialized_utf8_bytes']for r in pm),
             'retained_explanation_chars':sum(r['retained_explanation_chars']for r in pm),
             'hidden_reasoning_available':False,'original_explanation_clip_chars':800,'no_additional_clipping':True,
             'caveat':'review_fields.reasoning contains only explicitly labelled visible explanations. It must never be reported as a full hidden-reasoning review. Counted tokens are exact cached o200k fields, excluding reviewer instructions and output.',
             'paid_calls':0,'reviewed_packets':0}
    (OUT/'probe_packet_dryrun.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
