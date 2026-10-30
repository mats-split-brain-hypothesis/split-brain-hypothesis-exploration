"""Offline bookkeeping for direct, full-text SoRH semantic reading.

This helper does not infer semantics. It emits complete fields and validates
human-authored annotations against exact source substrings and field hashes.
"""
import argparse
import hashlib
import json
from pathlib import Path

BASE = Path('/Users/biancaganescu/Code/split-brain-hypothesis/logs/dashboard_reasoning_census')
OUT = BASE / 'sorh_single' / 'manual_ds_glm'
FIELDS = ('prompt', 'reasoning', 'reply')

def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')

def source(sid):
    return json.loads((BASE / 'sorh_single/samples' / (sid + '.json')).read_text())

def roots():
    rows = json.loads((BASE / 'sorh_single/sample_index.json').read_text())
    return sorted((r for r in rows if r['model'] in ('DeepSeek V4 Pro', 'GLM 5.2')),
                  key=lambda r: (sum(r['chars'].values()), r['id']))

def completed():
    result = {}
    for p in sorted((OUT / 'reviews').glob('*.json')):
        d = json.loads(p.read_text())
        result[d['sample_id']] = d
    # Parent's actual full reads may be reused, with original authorship retained.
    for name in ('sleep_b_vague_checked.json', 'gratitude_checked_three_models.json'):
        p = BASE / 'manual_reviews' / name
        if p.exists():
            for d in json.loads(p.read_text())['samples']:
                if d['model'] in ('DeepSeek V4 Pro', 'GLM 5.2'):
                    s = source(d['sample_id'])
                    if d['source_sha256'] == s['sha256'] and all(d['coverage'][f] == [[0, len(s[f])]] for f in FIELDS):
                        result.setdefault(d['sample_id'], {**d, 'imported_review_path': str(p)})
    return result

def status():
    rows, done = roots(), completed()
    summary = {'planned':len(rows), 'completed':len(done), 'pending':len(rows)-len(done),
               'review_method':'direct full-text Codex agent reading; no API calls',
               'models':{}, 'completed_ids':sorted(done)}
    for model in ('DeepSeek V4 Pro', 'GLM 5.2'):
        rs = [r for r in rows if r['model']==model]
        ds = [r for r in rs if r['id'] in done]
        summary['models'][model] = {'planned':len(rs),'complete':len(ds),
          'full_field_chars_complete':sum(sum(r['chars'].values()) for r in ds),
          'full_field_chars_total':sum(sum(r['chars'].values()) for r in rs)}
    dump(OUT / 'progress.json', summary)
    for path in (OUT / 'batches').glob('*.json'):
        batch = json.loads(path.read_text())
        batch['reviewed_ids'] = [r['id'] for r in batch['samples'] if r['id'] in done]
        batch['status'] = ('complete_direct_reviews_saved' if len(batch['reviewed_ids']) == len(batch['samples'])
                           else 'emitted_for_direct_reading_not_yet_complete')
        dump(path, batch)
    print(json.dumps(summary, indent=2))

def emit(batch, limit):
    path = OUT / 'batches' / (batch + '.json')
    if path.exists():
        rows = json.loads(path.read_text())['samples']
    else:
        done = completed()
        rows = [r for r in roots() if r['id'] not in done][:limit]
        dump(path, {'status':'emitted_for_direct_reading_not_yet_reviewed', 'samples':rows})
    for r in rows:
        s = source(r['id'])
        print('\n===== SAMPLE '+s['id']+' | '+s['model']+' | '+s['condition']+' =====')
        for f in FIELDS:
            print('\n--- '+f+' [0:'+str(len(s[f]))+'] ---\n'+s[f])
        print('\n===== END SAMPLE '+s['id']+' =====')

def save(path):
    annotations = json.loads(Path(path).read_text())
    for a in annotations:
        s = source(a['sample_id'])
        evidence = []
        for e in a['evidence']:
            field, quote = e['field'], e['quote']
            start = s[field].find(quote)
            assert start >= 0, (a['sample_id'], field, quote)
            assert s[field].find(quote,start+1)<0 or 'occurrence' in e, 'Ambiguous quote needs occurrence'
            for _ in range(e.get('occurrence',0)):
                start = s[field].find(quote,start+1)
                assert start >= 0
            evidence.append({**e, 'start':start, 'end':start+len(quote)})
        assert a.pop('all_fields_read') is True
        record = {**a, 'reviewer':'scenario_audit direct full-text reading',
          'model':s['model'], 'condition':s['condition'], 'prompt_id':s['prompt_id'],
          'coverage':{f:[[0,len(s[f])]] for f in FIELDS}, 'source_sha256':s['sha256'],
          'source_path':str(BASE/'sorh_single/samples'/(s['id']+'.json')),
          'source_missing_fields':[f for f in FIELDS if not s[f]],
          'finish':s['finish'], 'source_cuts':{k:s['labels'].get(k) for k in ('cut_in_reasoning','cut_mid_answer')},
          'evidence':evidence, 'scope':'One physical source record. Semantic descriptions do not establish objective quality or causal mechanisms.'}
        dump(OUT/'reviews'/(s['id']+'.json'),record)
    status()

if __name__=='__main__':
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='cmd',required=True)
    e=sub.add_parser('emit');e.add_argument('batch');e.add_argument('--limit',type=int,default=8)
    s=sub.add_parser('save');s.add_argument('path');sub.add_parser('status')
    a=p.parse_args()
    if a.cmd=='emit':emit(a.batch,a.limit)
    elif a.cmd=='save':save(a.path)
    else:status()
