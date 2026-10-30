"""Offline SoRH source index; emits metadata only, never reply/reasoning text."""
import collections
import hashlib
import json
from pathlib import Path
import re

ROOT = Path('/Users/biancaganescu/Code/split-brain-hypothesis')
OUT = Path(__file__).resolve().parents[1] / 'notes'
WORKTREES = ['agent-1-sorh-cues', 'agent-3-sorh-persistence', 'agent-5-grader-definition',
             'agent-6-stakes', 'agent-8-user-facing', 'agent-9-presentation', 'agent-10-audit']


def jl(path):
    if path.exists():
        with path.open() as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)


def relative(path):
    return str(path.relative_to(ROOT))


def main():
    stages = []
    for path in sorted((ROOT / 'logs/sorh_ablation').glob('*/records.jsonl')):
        counts = collections.Counter()
        metadata = collections.defaultdict(set)
        locators = []
        for number, row in enumerate(jl(path), 1):
            fields = {k: row[k] for k in ['stage','prompt_id','row','cell','arm','sample','turn',
                      'finish','model','provider','provider_requested','effort','judge_version'] if k in row}
            fields['line'] = number
            locators.append(fields)
            counts[(str(row.get('cell', row.get('arm'))), str(row.get('turn', '')), str(row.get('finish', '')))] += 1
            for key in ['model','provider','provider_requested','effort','judge_version']:
                if key in row:
                    metadata[key].add(json.dumps(row[key],sort_keys=True))
        run_files = sorted(path.parent.glob('run*.json'))
        run = json.loads(run_files[-1].read_text()) if run_files else {}
        spend = list(jl(path.parent / 'spend.jsonl'))
        by_kind = collections.defaultdict(float)
        for s in spend:
            by_kind[str(s.get('outcome', s.get('kind', 'unknown')))] += float(s.get('usd', s.get('cost', 0)) or 0)
        stages.append(dict(source=relative(path), records=len(locators),
                           metadata={k:sorted(v) for k,v in metadata.items()},
                           run={k:run[k] for k in ['stage','model','max_tokens','command','launched_utc',
                                'planned_records','judge_version','judge_models','judges','cells_file','dry'] if k in run},
                           spend_ledger=relative(path.parent/'spend.jsonl'),
                           recorded_spend_usd=round(sum(by_kind.values()),6) if (path.parent/'spend.jsonl').exists() else None,
                           spend_by_outcome=dict(by_kind),
                           cells=[dict(cell=c,turn=t,finish=f,n=n) for (c,t,f),n in sorted(counts.items())],
                           transcript_locators=locators))
    (OUT/'sorh_stage_metadata_oct27.json').write_text(json.dumps(stages,indent=2)+'\n')
    auxiliary=[]
    for path in sorted((ROOT/'logs/sorh_ablation').rglob('*.jsonl')):
        if path.name not in ['answers.jsonl','judged.jsonl','judged_nometric.jsonl','judged_nometric_nooutput_fix.jsonl']:
            continue
        spend=list(jl(path.parent/'spend.jsonl'))
        # Count lines only: no judge rationales, quotes, or probe answer text.
        with path.open() as f:
            lines=sum(bool(line.strip()) for line in f)
        auxiliary.append(dict(path=relative(path),rows=lines,
                              ledger=relative(path.parent/'spend.jsonl'),
                              ledger_usd=round(sum(float(r.get('usd',r.get('cost',0)) or 0) for r in spend),6)
                              if (path.parent/'spend.jsonl').exists() else None))
    (OUT/'sorh_auxiliary_metadata_oct27.json').write_text(json.dumps(auxiliary,indent=2)+'\n')

    registries = []
    for agent in [1,3,5,6,8]:
        path=ROOT/f'.claude/worktrees/agent-10-audit/notes/experiment_registry/agent{agent}.json'
        raw=json.loads(path.read_text())
        entries=raw.get('experiments',[]) if isinstance(raw,dict) else raw
        for r in entries:
            # Agent3 writing/coding-chat extensions share claim IDs; retain all
            # and let their setting identify extensions rather than call them SoRH.
            if agent in [1,3] or any(s in json.dumps(r).lower() for s in ['sorh','school of reward','1l']):
                registries.append(dict(source=relative(path), **r))
    (OUT/'sorh_legacy_registry_oct27.json').write_text(json.dumps(registries,indent=2)+'\n')

    notes=[]
    locations=[ROOT/'notes']+[ROOT/'.claude/worktrees'/w/'notes' for w in WORKTREES]
    for directory in locations:
        for path in sorted(directory.glob('*.md')):
            raw=path.read_text()
            if not any(s in raw.lower() for s in ['sorh','school of reward']):
                continue
            headings=[dict(line=i,title=l) for i,l in enumerate(raw.splitlines(),1)
                      if re.match(r'^#{1,6} ',l) or re.match(r'^\*\*(?:Results|Pre-registration|Write-up|Correction|#4)',l)]
            refs=sorted(set(re.findall(r'logs/[A-Za-z0-9_./{}*-]+',raw)))
            notes.append(dict(path=relative(path),sha256=hashlib.sha256(raw.encode()).hexdigest(),
                              headings=headings,log_references=refs))
    (OUT/'sorh_note_sources_oct27.json').write_text(json.dumps(notes,indent=2)+'\n')
    pages=json.loads((ROOT/'published_pages/index.json').read_text())
    pages=[{k:r.get(k) for k in ['number','title','slug','updated','kind','dir','problem','database']}
           for r in pages if any(s in (r.get('title','')).lower() for s in ['sorh','school of reward','split-brain','graded'])]
    (OUT/'sorh_page_index_oct27.json').write_text(json.dumps(pages,indent=2)+'\n')
    print(json.dumps(dict(stages=len(stages),records=sum(s['records'] for s in stages),
                          legacy_entries=len(registries),note_copies=len(notes),
                          distinct_note_contents=len({n['sha256'] for n in notes}),pages=len(pages))))
    for s in stages:
        print(Path(s['source']).parent.name,s['records'],s['recorded_spend_usd'])


if __name__=='__main__':
    main()
