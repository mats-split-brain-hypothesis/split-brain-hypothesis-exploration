"""Render only the newly generated branch messages, with source context linked separately."""
import json,re
from pathlib import Path
from inspect_ai.log import read_eval_log
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'logs/ib_momentum_aisi/2026-10-24'
def fence(s,kind='text'):
    marker='`'*max(3,1+max((len(m[0]) for m in re.finditer(r'`+',s)),default=0))
    return marker+kind+'\n'+s+'\n'+marker+'\n'
def main():
    log_path=next((OUT/'runs').glob('*.eval'));log=read_eval_log(log_path,resolve_attachments=True)
    dest=OUT/'readable';dest.mkdir(exist_ok=True)
    rows=[]
    for sample in log.samples:
        md=sample.metadata;prefix=json.loads((OUT/f"prefix_{md['stage']}.json").read_text());cut=len(prefix['messages'])
        parts=[f"# {sample.id}\n",f"Source: `{log_path}`; epoch {sample.epoch}.\n",
               f"Historical context: `{OUT/f'prefix_{md['stage']}.json'}`. {cut} messages, through raw node {prefix['raw_cut']-1}.\n",
               'Below: researcher intervention, separate probe question where applicable, and all newly generated messages and tool results. Historical reasoning is not repeated.\n']
        for i,m in enumerate(sample.messages[cut:],cut):
            parts.append(f'## Message {i} — {m.role}\n')
            if isinstance(m.content,str):parts.append(fence(m.content))
            else:
                for c in m.content:
                    if c.type=='reasoning':parts.extend(['### Logged model reasoning\n',fence(c.reasoning)])
                    elif c.type=='text':parts.extend(['### Visible text\n',fence(c.text)])
            for call in getattr(m,'tool_calls',None) or []:
                parts.append(f'### Tool call: {call.function}\n')
                for k,v in call.arguments.items():parts.extend([f'**{k}**\n',fence(v if isinstance(v,str) else json.dumps(v,indent=2))])
        path=dest/f'{sample.id}.md';path.write_text('\n'.join(parts));rows.append(dict(id=sample.id,path=str(path),new_messages=len(sample.messages)-cut))
    (dest/'index.json').write_text(json.dumps(rows,indent=2)+'\n');print('Rendered',len(rows),'completed samples')
if __name__=='__main__':main()
