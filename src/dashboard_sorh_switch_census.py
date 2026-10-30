"""Metadata-only census for the frozen original dashboard's SoRH switch/probes.

Never marks a transcript read. No network or model calls. Resolves explicit copy
provenance, preserves source lines/hashes, and separates absent probe reasoning
from its retained (possibly clipped) visible explanation.
"""
import collections
import hashlib
import json
from pathlib import Path

ROOT = Path('/Users/biancaganescu/Code/split-brain-hypothesis')
OUT = ROOT / 'logs/dashboard_reasoning_census/sorh_switch'
BASE = ROOT / 'logs/sorh_ablation'
STAGES = ['mt', 'mt_deepseek_64k', 'mt_glm52', 'mt_qwen27b',
          'mt_nobody_qwen24t', 'mt_nobody_deepseek', 'mt_nobody_glm52', 'mt_nobody_qwen27b',
          'mt20_qwen24t', 'mt20_deepseek', 'mt20_glm52', 'mt20_qwen27b']
ARMS = {'cue10_off', 'cue10_on', 'cue10_nobody'}
MODEL = {'mt': 'qwen24', 'mt_deepseek_64k': 'deepseek', 'mt_glm52': 'glm52', 'mt_qwen27b': 'qwen27',
         'mt_nobody_qwen24t': 'qwen24', 'mt_nobody_deepseek': 'deepseek', 'mt_nobody_glm52': 'glm52', 'mt_nobody_qwen27b': 'qwen27',
         'mt20_qwen24t': 'qwen24', 'mt20_deepseek': 'deepseek', 'mt20_glm52': 'glm52', 'mt20_qwen27b': 'qwen27'}


def sha(value):
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def write_jsonl(path, rows):
    with path.open('w') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')


def load(path):
    return [(i, line, json.loads(line)) for i, line in enumerate(path.read_text().splitlines(), 1) if line]


def switch_manifest():
    index, files, occurrences = {}, {}, []
    for stage in STAGES:
        path = BASE / stage / 'records.jsonl'
        files[str(path)] = {'sha256': sha(path.read_bytes()), 'bytes': path.stat().st_size}
        for line, raw, r in load(path):
            key = '/'.join(str(r[k]) for k in ['stage', 'arm', 'prompt_id', 'sample', 'turn'])
            assert key not in index
            index[key] = {'data': r, 'source': {'path': str(path), 'line': line, 'row_sha256': sha(raw)}}
            if r['arm'] in ARMS:
                occurrences.append(key)

    def canonical(key):
        seen = set()
        while index[key]['data'].get('copied_from'):
            assert key not in seen
            seen.add(key)
            key = index[key]['data']['copied_from']
            assert key in index, key
        return key

    aliases = collections.defaultdict(list)
    for key in occurrences:
        target = canonical(key)
        # Dedup is provenance-based, with a separate byte check, not a topic or
        # keyword-based grouping that could conflate independent generations.
        for field in ['reasoning', 'reply']:
            assert index[key]['data'].get(field) == index[target]['data'].get(field), (key, target, field)
        aliases[target].append(key)
    turns = []
    for key, keys in sorted(aliases.items()):
        r = index[key]['data']
        history = []
        for t in range(1, r['turn']):
            previous = key.rsplit('/', 1)[0] + '/' + str(t)
            assert previous in index
            history.append({'turn_id': previous, 'canonical_turn_id': canonical(previous), 'source': index[previous]['source']})
        turns.append({'sample_id': key, 'kind': 'behavior_turn', 'cohort': '20_prompt' if r['stage'].startswith('mt20_') else '3_prompt_5_draw',
                      'model': MODEL[r['stage']], 'prompt_id': r['prompt_id'], 'arm': r['arm'], 'draw': r['sample'], 'turn': r['turn'],
                      'source': index[key]['source'], 'source_file_sha256': files[index[key]['source']['path']]['sha256'],
                      'fields': {k: {'chars': len(r.get(k) or ''), 'utf8_bytes': len((r.get(k) or '').encode()), 'sha256': sha(r.get(k) or '')} for k in ['prompt', 'reasoning', 'reply']},
                      'finish': r.get('finish'), 'usage': r.get('usage'),
                      'aliases': keys, 'conversation_ids': sorted({k.rsplit('/', 1)[0] for k in keys}),
                      'prior_turns_for_full_input': history,
                      'reasoning_availability': 'stored' if r.get('reasoning') else 'empty',
                      'review_status': 'not_read', 'reasoning_read_chars': 0})
    occurrence_rows = [{'turn_id': key, 'canonical_turn_id': canonical(key), 'source': index[key]['source']} for key in sorted(occurrences)]
    by_conv = collections.defaultdict(list)
    for row in occurrence_rows:
        by_conv[row['turn_id'].rsplit('/', 1)[0]].append(row)
    conv = []
    for key, rows in sorted(by_conv.items()):
        r = index[rows[0]['turn_id']]['data']
        turns_present = sorted(int(row['turn_id'].rsplit('/', 1)[1]) for row in rows)
        conv.append({'sample_id': key, 'kind': 'conversation', 'model': MODEL[r['stage']],
                     'cohort': '20_prompt' if r['stage'].startswith('mt20_') else '3_prompt_5_draw',
                     'prompt_id': r['prompt_id'], 'arm': r['arm'], 'draw': r['sample'],
                     'planned_turns': 5, 'stored_turns': turns_present, 'missing_turns': [t for t in range(1, 6) if t not in turns_present],
                     'turns': rows, 'review_status': 'not_read'})
    write_jsonl(OUT / 'canonical_turns.jsonl', turns)
    write_jsonl(OUT / 'turn_occurrences.jsonl', occurrence_rows)
    write_jsonl(OUT / 'conversations.jsonl', conv)
    return turns, conv, files


def probe_manifest():
    specifications = []
    def add(rel, graphs, cells=None, probe=None, role='graph_sample'):
        specifications.append((ROOT / rel, graphs, cells, probe, role))
    # Three switch arms, old and redone. Every MC draw and who-checks call counts.
    add('logs/sorh_ablation/probe/answers.jsonl', ['sorh_switch_probe'], {'mt_cue10_off_switch', 'mt_cue10_on_switch'})
    for family in ['ds', 'glm', 'q27']:
        add(f'logs/sorh_ablation/{family}_probe/switch/answers.jsonl', ['sorh_switch_probe'])
    for family in ['qwen', 'deepseek', 'glm', 'qwen27b']:
        add(f'logs/sorh_ablation/nobody_probe/{family}/answers.jsonl', ['sorh_switch_probe'])
        add(f'logs/sorh_ablation/redo4_probe/{family}/answers.jsonl', ['sorh_switch_probe20'])
    # First-message realness graph: B, G, classroom, and real-user anchors.
    add('logs/sorh_ablation/probe/answers.jsonl', ['sorh_probe'], {'B', 'G'}, 'purpose_mc')
    add('logs/sorh_ablation/realness_candidates/answers.jsonl', ['sorh_probe'], {'r_student'}, 'purpose_mc')
    add('logs/sorh_ablation/realness_candidates/step3/answers.jsonl', ['sorh_probe'], {'r_student'}, 'purpose_mc')
    for family in ['ds', 'glm', 'q27']:
        add(f'logs/sorh_ablation/{family}_probe/first/answers.jsonl', ['sorh_probe'], {'B', 'G', 'r_student'}, 'purpose_mc')
    for name in ['a1_wildchat', 'a1_ds_wildchat', 'a1_glm_wildchat', 'a1_qwen27b_wildchat']:
        add(f'logs/eval_probe/{name}.jsonl', ['sorh_probe'], None, 'purpose_mc')
    # Seven condition cells; the eighth dataset row is a derived maximum.
    add('logs/sorh_ablation/probe/answers.jsonl', ['sorh_probe3'],
        {'c4_auto', 'c4_manager', 'c4_own', 'c5_eval', 'c5_real', 'c5_training', 'c7_dont_care'}, 'purpose_mc')
    output, files = {}, {}
    for path, graphs, cells, probe, role in specifications:
        files[str(path)] = {'sha256': sha(path.read_bytes()), 'bytes': path.stat().st_size}
        for line, raw, r in load(path):
            if cells is not None and r.get('cell') not in cells:
                continue
            if probe is not None and r.get('probe') != probe:
                continue
            key = str(path.relative_to(ROOT)) + ':' + str(line)
            if key in output:
                output[key]['graph_dataset_ids'] = sorted(set(output[key]['graph_dataset_ids'] + graphs))
                continue
            exp = r.get('explanation') or ''
            output[key] = {'sample_id': key, 'kind': 'probe_call', 'graph_dataset_ids': graphs, 'scope_role': role,
                           'source': {'path': str(path), 'line': line, 'row_sha256': sha(raw)},
                           'source_file_sha256': files[str(path)]['sha256'],
                           'model': r.get('model'), 'provider': r.get('provider'), 'effort': r.get('effort'),
                           'prompt_id': r.get('prompt_id', r.get('id')), 'cell': r.get('cell', 'wildchat'),
                           'context': r.get('context'), 'probe': r.get('probe'), 'draw': r.get('sample'),
                           'parsed_answer': r.get('answer', r.get('label')), 'raw_label': r.get('raw', r.get('raw_label')),
                           'finish': r.get('finish_reason'), 'reasoning_tokens_reported': r.get('reasoning_tokens'),
                           'reasoning_availability': 'not_stored_by_runner', 'reasoning_chars': 0,
                           'visible_explanation': {'chars': len(exp), 'sha256': sha(exp), 'runner_clip_limit': 800,
                                                   'at_clip_limit_or_ellipsis': len(exp) >= 800 or exp.endswith('…')},
                           'review_status': 'not_read', 'limitation': 'No reasoning field retained. Explanation is model-visible answer text, clipped by the runner; raw is only the raw label.'}
    rows = list(output.values())
    write_jsonl(OUT / 'probe_calls.jsonl', rows)
    return rows, files


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    turns, conv, files = switch_manifest()
    probes, probe_files = probe_manifest()
    files.update(probe_files)
    summary = {'date': '2026-10-27', 'scope': 'Original frozen sorh.html: old3x5 and new20x1 switch arms; visible realness/who-checks probe datasets.',
               'conversations': len(conv), 'stored_turn_occurrences': sum(len(c['turns']) for c in conv),
               'unique_canonical_turns': len(turns), 'canonical_reasoning_chars': sum(r['fields']['reasoning']['chars'] for r in turns),
               'canonical_reasoning_utf8_bytes': sum(r['fields']['reasoning']['utf8_bytes'] for r in turns),
               'prompt_chars': sum(r['fields']['prompt']['chars'] for r in turns), 'reply_chars': sum(r['fields']['reply']['chars'] for r in turns),
               'by_cohort': {c: {'conversations': sum(x['cohort'] == c for x in conv), 'canonical_turns': sum(x['cohort'] == c for x in turns),
                                'reasoning_chars': sum(x['fields']['reasoning']['chars'] for x in turns if x['cohort'] == c)} for c in ['20_prompt', '3_prompt_5_draw']},
               'by_model': {m: {'canonical_turns': sum(x['model'] == m for x in turns), 'reasoning_chars': sum(x['fields']['reasoning']['chars'] for x in turns if x['model'] == m)} for m in ['qwen24', 'deepseek', 'glm52', 'qwen27']},
               'probe_calls': len(probes), 'probe_by_dataset': dict(collections.Counter(g for r in probes for g in r['graph_dataset_ids'])),
               'probe_reasoning_stored': 0, 'probe_visible_explanation_chars': sum(r['visible_explanation']['chars'] for r in probes),
               'probe_explanations_at_limit_or_ellipsis': sum(r['visible_explanation']['at_clip_limit_or_ellipsis'] for r in probes),
               'reviewed_samples': 0, 'reviewed_reasoning_chars': 0,
               'deduplication': 'Explicit copied_from chains; verifies reasoning and reply equality. Every alias keeps source line. Independent generations are not merged by topic. Canonical reasoning hashes allow cross-agent reuse checks.',
               'source_files': files}
    (OUT / 'inventory_summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    for name in ['annotations.jsonl', 'read_ranges.jsonl']:
        (OUT / name).touch(exist_ok=True)
    print(json.dumps({k:v for k,v in summary.items() if k != 'source_files'}, indent=2))


if __name__ == '__main__':
    main()
