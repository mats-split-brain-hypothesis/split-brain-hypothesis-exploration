"""Plot-ready SoRH numbers from frozen manifests and published numerical tables.

No model calls; no raw model reasoning or reply text is read. Published chart n
fields are NOT sample sizes for length charts (they are chart axis maxima).
"""
from collections import defaultdict, Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import statistics

ROOT=Path('/Users/biancaganescu/Code/split-brain-hypothesis')
OUT=Path(__file__).resolve().parents[1]/'notes'
FROZEN=ROOT/'logs/reasoning_review/2026-10-27'
MODELS=['Qwen 3.8 2.4T','DeepSeek V4 Pro','GLM 5.2','Qwen 3.8 27B']
SHARE={160,559,223,931,573,219}
TERMS={160,450,559,743,702,223,931,573,219,714}


def save(name, rows, **meta):
    (OUT/name).write_text(json.dumps(dict(benchmark='SoRH',generated_utc=datetime.now(timezone.utc).isoformat(),
                                         **meta,rows=rows),indent=2)+'\n')


def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def rel(p): return str(Path(p).relative_to(ROOT))
def ratio(k,n): return k/n if n else None
def sid(r): return r['statement']['id'] if isinstance(r['statement'],dict) else r['statement']
def metric_type(unit):
    row=int(unit.split('_')[-1])
    return 'share' if row in SHARE else 'term_count' if row in TERMS else 'item_count'


def cost_sources(sources):
    paths=[]
    for source in sources:
        if source and source.get('path'):
            p=Path(source['path']).parent/'spend.jsonl'
            if p not in paths: paths.append(p)
    out=[]
    for p in paths:
        cost=None
        if p.exists():
            cost=sum(float(json.loads(l).get('usd',0)or 0)for l in p.open()if l.strip())
        out.append(dict(path=rel(p),usd=round(cost,6)if cost is not None else None,
                        scope='entire shared stage, not attributable to this cell; do not sum across cells'))
    return out


def manifests():
    p=FROZEN/'a1_manifest.json';data=json.loads(p.read_text());groups=defaultdict(list)
    for row in data['rows']:groups[(sid(row),row['version'],row['model'])].append(row)
    cells=[]
    for (statement,condition,model),rows in groups.items():
        active=[r for r in rows if not r['labels'].get('superseded_by_redraw')]
        planned=len({(r['unit'],r['rep'])for r in rows})
        for label in ['padded_v2','padded_old']:
            exclusions=Counter();usable=[]
            for r in active:
                l=r['labels']
                reason=('missing_record' if l.get('missing') or not r.get('source') else
                        'cut_in_reasoning' if l.get('cut_in_reasoning') else
                        'no_applicable_or_parsed_padding_label' if type(l.get(label))is not bool else None)
                if reason: exclusions[reason]+=1
                else: usable.append(r)
            k=sum(r['labels'][label] for r in usable);n=len(usable)
            refs=[r['source']for r in active if r.get('source')]
            cells.append(dict(benchmark='SoRH',view='frozen_manifest',experiment=statement,condition=condition,
                              model=model,metric=label,label_version='final-output/no-metric-v2' if label=='padded_v2' else 'whole-reply-old',
                              k=k,n=n,value=ratio(k,n),planned=planned,usable=n,missing=exclusions['missing_record'],
                              exclusions=dict(exclusions),superseded_rows=len(rows)-len(active),
                              redraws=sum(bool(r['labels'].get('redraw'))for r in active),
                              cut_mid_answer_included=sum(bool(r['labels'].get('cut_mid_answer'))for r in usable),
                              manifest=rel(p),manifest_sha256=digest(p),source_refs=refs,cost_usd=None,
                              shared_cost_sources=cost_sources(refs)))
    p3=FROZEN/'a3_manifest.json';rows3=json.loads(p3.read_text())['rows'];groups3=defaultdict(list)
    for row in rows3:groups3[(row['version'],row['model'])].append(row)
    for (condition,model),rows in groups3.items():
        for label in ['padded_v2','padded_old']:
            for moment in ['r1','r2','final']:
                usable=[r for r in rows if type(r['labels'][label].get(moment))is bool]
                k=sum(r['labels'][label][moment]for r in usable);n=len(usable)
                refs=[s for r in rows for s in r['source']]
                cells.append(dict(benchmark='SoRH',view='frozen_manifest',experiment='#4',condition=condition,
                                  model=model,metric=label+'_'+moment,label_version='final-output/no-metric-v2' if label=='padded_v2' else 'whole-reply-old',
                                  k=k,n=n,value=ratio(k,n),planned=len(rows),usable=n,missing=len(rows)-n,
                                  exclusions={'missing_or_unlabelled_turn':len(rows)-n},incomplete_episodes=sum(not r['complete']for r in rows),
                                  manifest=rel(p3),manifest_sha256=digest(p3),source_refs=refs,cost_usd=None,
                                  shared_cost_sources=cost_sources(refs),
                                  note='r1/r2 are shared across arms; do not pool them as independent replies'))
    save('sorh_manifest_plot_cells_oct27.json',cells,
         note='Frozen source manifests only. Superseded redraw rows excluded. Missing or reasoning-cut replies are not failures. Mean-letter/keyed-car padding is undefined where label is null.')

    # Root's density-versus-length request: one row per prompt/condition/model,
    # deduplicated across statement memberships. Count measures are external judge
    # outputs on the whole reply; they are NOT verified objective scores.
    selected={}
    for r in data['rows']:
        if r['version']not in {'B','G','c3a_conv','c6_quality_first','c7_dont_care'}:continue
        if r['labels'].get('superseded_by_redraw'):continue
        selected[(r['model'],r['unit'],r['version'],r['rep'])]=r
    unitrows=[]
    for (model,unit,condition,rep),r in sorted(selected.items()):
        labels=r['labels'];kind=metric_type(unit)
        unitrows.append(dict(benchmark='SoRH',experiment='density_and_length',model=model,prompt_id=unit,
                             condition=condition,rep=rep,metric_type=kind,words=labels.get('words'),
                             count_or_share=labels.get('count_or_share'),padded_v2=labels.get('padded_v2'),
                             count_definition='external count-judge whole-reply '+('counted-word share in percentage points' if kind=='share' else 'counted terms/items'),
                             padding_definition='external Luna judge on final output only; metric hidden',
                             score_status='external judge measure, not model self-estimate or verified true objective',
                             missing=labels.get('missing'),cut_in_reasoning=labels.get('cut_in_reasoning'),
                             cut_mid_answer=labels.get('cut_mid_answer'),finish=labels.get('finish'),source=r['source']))
    save('sorh_prompt_density_length_oct27.json',unitrows,manifest=rel(p),manifest_sha256=digest(p))
    grouped=defaultdict(list)
    for r in unitrows:grouped[(r['model'],r['condition'],r['metric_type'])].append(r)
    summaries=[]
    for (model,condition,kind),rs in sorted(grouped.items()):
        for measure in ['words','count_or_share']:
            vals=[r[measure]for r in rs if isinstance(r.get(measure),(int,float))and not r['missing']and not r['cut_in_reasoning']]
            summaries.append(dict(benchmark='SoRH',view='frozen_manifest',experiment='density_and_length',model=model,
                                  condition=condition,metric_type=kind,metric='median_'+measure,value=statistics.median(vals)if vals else None,
                                  k=None,n=len(vals),planned=len(rs),usable=len(vals),missing=len(rs)-len(vals),
                                  source='sorh_prompt_density_length_oct27.json',note='Aggregated only within metric type; external judge count/share'))
    save('sorh_density_length_medians_oct27.json',summaries)


def published():
    base=ROOT/'published_pages/HsCSuEFhu8ruyso8XiQSHw';out=[]
    for p in sorted(base.glob('embed_*.jsx')):
        code=p.read_text();m=re.search(r"data-claude-component=['\"]([^'\"]+)",code)
        if not m or not m[1].startswith('sorh4-')or 'data:['not in code:continue
        component=m[1]
        try: rows,_=json.JSONDecoder().raw_decode(code[code.index('data:[')+5:])
        except ValueError:continue
        if not rows or not isinstance(rows[0],dict)or 'k0'not in rows[0]:continue
        length='length'in component
        for row in rows:
            for i,model in enumerate(MODELS):
                value=row.get(f'k{i}');display=row.get(f't{i}')
                denominator=row.get(f'n{i}')
                if not isinstance(value,(int,float)):continue
                if length: metric='median_reported_reasoning_tokens';k=None;n=None
                elif 'probe'in component or 'Probe'in row.get('group',''):metric='realness_probe';k=value;n=denominator
                elif 'hes'in component:metric='hesitates'if 'Hesitates'in row.get('group','')else'spirals';k=value;n=denominator
                elif 'mean'in component:metric='mean_letter';k=value;n=denominator
                else:metric='padded_v2';k=value;n=denominator
                out.append(dict(benchmark='SoRH',view='canonical_published',experiment=component,condition=row['label'],group=row.get('group'),
                                model=model,metric=metric,value=value if length else ratio(k,n),k=k,n=n,
                                planned=None,usable=n,missing=None,exclusions='not recoverable from rendered cell alone',
                                display=display,source=rel(p),source_sha256=digest(p),cost_usd=None,
                                note='n fields in source are axis maxima, not sample sizes'if length else'Published denominator retained; do not substitute 20/15 for missing-label cells'))
    save('sorh_published_plot_cells_oct27.json',out,note='Actual published JSX, not potentially stale builder sources. Quotes omitted.')


def numeric_tables():
    # All cells come from existing summaries. Ratios and scalar values are parsed
    # mechanically; table column and section remain attached to avoid conflating
    # e.g. paired differences, medians and proportions.
    paths=[ROOT/'.claude/worktrees/agent-1-sorh-cues/notes'/name for name in [
        'sorh_hesitation_spiral_results_20_redraws.md','sorh_models20_reasoning_length_redraws.md',
        'sorh_page_means_redraws.md','sorh_split_brain_bf_results.md','sorh_reader_checks_results.md']]
    paths.append(ROOT/'.claude/worktrees/agent-10-audit/notes/sorh_split_brain_cd_results.md')
    out=[];tables=[]
    for p in paths:
        section='';header=None
        for number,line in enumerate(p.read_text().splitlines(),1):
            if line.startswith('## '):section=line[3:];header=None
            if not line.startswith('|'):continue
            values=[v.strip()for v in line.strip().strip('|').split('|')]
            if all(re.fullmatch(r'[-: ]+',v)for v in values):continue
            if header is None:header=values;continue
            if len(values)!=len(header):continue
            row=dict(zip(header,values));tables.append(dict(source=rel(p),line=number,section=section,values=row))
            for field,text in row.items():
                if field==header[0]:continue
                cleaned=text.replace(',','').replace('**','')
                fraction=re.match(r'^(\d+)/(\d+)(?:\D|$)',cleaned)
                scalar=re.match(r'^([+-]?\d+(?:\.\d+)?)(?:\s|$)',cleaned)
                if not fraction and not scalar:continue
                k,n=(int(fraction[1]),int(fraction[2]))if fraction else(None,None)
                value=ratio(k,n)if fraction else float(scalar[1])
                model=field if field in MODELS else row.get('model',row.get('probe',row.get('coder')))
                condition=row.get('cell',row.get('version',row.get('new vs ref',values[0])))
                out.append(dict(benchmark='SoRH',view='numerical_source_table',experiment=p.stem,condition=condition,
                                model=model,metric=section if field in MODELS else section+' / '+field,
                                value=value,k=k,n=n,planned=20 if field in MODELS and '20'in p.stem else None,
                                usable=n,missing=None,exclusions='see source table and section caveats',display=text,
                                source=rel(p),line=number,source_sha256=digest(p),cost_usd=None))
    save('sorh_numerical_source_cells_oct27.json',out,note='Exact table display retained. Missing/planned is null unless stated; k/n only for actual fractions. Do not aggregate different metrics.')
    save('sorh_numerical_source_tables_oct27.json',tables)


def probes():
    # Existing parsed categorical labels only; omit raw answers/explanations.
    base=ROOT/'logs/sorh_ablation';out=[]
    selected=[base/'probe/answers.jsonl']
    selected+=list(base.glob('*_probe/first/answers.jsonl'))+list(base.glob('*_probe/switch/answers.jsonl'))
    selected+=list((base/'nobody_probe').glob('*/answers.jsonl'))
    for p in selected:
        if not p.exists():continue
        groups=defaultdict(list)
        for line in p.open():
            if line.strip():
                r=json.loads(line)
                groups[(r.get('cell'),r.get('model'),r.get('probe'))].append({k:r.get(k)for k in
                    ['prompt_id','sample','answer','provider','effort','usd']})
        for (condition,model,probe),rs in groups.items():
            counts=Counter(str(r['answer'])for r in rs if r['answer']not in [None,''])
            known=sum(counts.values());cost=sum(float(r['usd']or 0)for r in rs)
            categories=['Real']if probe=='purpose_mc'else sorted(counts)
            for answer in categories:
                k=counts[answer]
                out.append(dict(benchmark='SoRH',view='parsed_probe_answers',experiment=str(p.parent.relative_to(base)),
                                condition=condition,model=model,metric=probe+':'+answer,value=ratio(k,known),k=k,n=known,
                                planned=None,records=len(rs),usable=known,missing=len(rs)-known,
                                exclusions={'unparsed':len(rs)-known},providers=sorted({str(r['provider'])for r in rs}),
                                efforts=sorted({str(r['effort'])for r in rs}),cost_usd=round(cost,6),
                                cost_scope='all answers for this condition/model/probe; shared across categorical rows',
                                source=rel(p),source_sha256=digest(p)))
            if probe=='purpose_mc':
                units=defaultdict(list)
                for r in rs:units[r['prompt_id']].append(r['answer'])
                eligible=[answers for answers in units.values()if len(answers)==3 and all(a is not None for a in answers)]
                k=sum(answers.count('Real')>=2 for answers in eligible);n=len(eligible)
                out.append(dict(benchmark='SoRH',view='parsed_probe_answers',experiment=str(p.parent.relative_to(base)),
                                condition=condition,model=model,metric='contexts_at_least_2_of_3_Real',value=ratio(k,n),k=k,n=n,
                                planned=len(units),usable=n,missing=len(units)-n,source=rel(p),source_sha256=digest(p),
                                cost_usd=round(cost,6),cost_scope='same source answers as pooled rate; do not count twice',
                                unit_note='input prompt_id; switch contexts include replicate histories, not independent task prompts'))
    save('sorh_probe_plot_cells_oct27.json',out,
         note='Categorical parsed labels only. Fresh-copy medium-effort probes do not establish the behavior-run latent belief. Missing planned calls cannot be inferred from answer file alone.')


if __name__=='__main__':
    manifests();published();numeric_tables();probes()
    print('Wrote 8 SoRH-only numerical artifacts; no model reasoning or reply text read.')
