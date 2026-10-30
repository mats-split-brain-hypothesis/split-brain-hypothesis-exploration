"""Prepare the original-dashboard presentation with complete retained source text.

Reads frozen reviewed cards only, plus one hash-verified later review. No model
calls, experiment reruns or execution of archived candidate code.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path('/Users/biancaganescu/Code/split-brain-hypothesis')
HERE = Path(__file__).resolve().parents[1]
CENSUS = ROOT / 'logs/dashboard_reasoning_census'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def block(label, text):
    assert isinstance(text, str), (label, type(text))
    return {'label': label, 'text': text, 'chars': len(text), 'sha256': sha(text)}


def single(raw, card):
    return {
        'prompt_blocks': [block('Full archived user prompt', raw['prompt'])],
        'answer_blocks': [block('Full stored final answer', raw['reply'])],
        'notes': ['The archived user prompt is complete. The provider/system prompt stack was not retained.',
                  'Full means all retained text; a provider cutoff or empty reply is not repaired here.'],
        'metadata': {k: raw[k] for k in ['provider', 'effort', 'finish'] if raw.get(k) is not None},
    }


def ib(raw, card):
    messages = raw['messages']
    first = next((i for i, m in enumerate(messages) if m['role'] == 'assistant'), len(messages))
    prompts = [block(f"Message {m['index']} · {m['role']} · full initial instruction", m['text'])
               for m in messages[:first] if m['role'] in ('system', 'user')]
    agentic = 'swe_style_humaneval_scorer' in raw['scores']
    if agentic:
        for key, label in [('prompt', 'Initial func.py reference'), ('test', 'Initial test.py reference')]:
            if raw.get('task_files', {}).get(key):
                prompts.append(block(label + ' · task environment, not a separate user message', raw['task_files'][key]))
    for m in messages[first:]:
        if m['role'] == 'user':
            prompts.append(block(f"Message {m['index']} · full later user feedback / intervention", m['text']))
    assistants = [m for m in messages if m['role'] == 'assistant']
    final = assistants[-1] if assistants else None
    answers = []
    if final:
        answers.append(block(f"Message {final['index']} · full terminal assistant text", final['text']))
    notes = []
    notes.append('The prompt column includes every archived initial instruction and later user update. Prior assistant replies and tool feedback are preserved in the intervening-history drawer.')
    if not final or not final['text']:
        notes.append('The terminal assistant message has no visible answer. Earlier progress text is not substituted for a final answer.')
    history = []
    # Exact visible history preserves feedback/tool exposure without duplicating hidden reasoning.
    for m in messages[first:]:
        if m is final:
            continue
        if m['text']:
            history.append(block(f"Message {m['index']} · {m['role']}" + (f" · {m['function']}" if m.get('function') else ''), m['text']))
        if m.get('tool_calls'):
            history.append(block(f"Message {m['index']} · archived tool calls", json.dumps(m['tool_calls'], ensure_ascii=False, indent=2)))
        if m.get('error') is not None:
            error = m['error'] if isinstance(m['error'], str) else json.dumps(m['error'], ensure_ascii=False, indent=2)
            history.append(block(f"Message {m['index']} · recorded tool/message error", error))
        if m.get('other_content'):
            history.append(block(f"Message {m['index']} · other retained content", json.dumps(m['other_content'], ensure_ascii=False, indent=2)))
    if final and final.get('tool_calls'):
        answers.append(block('Terminal assistant tool calls · archived arguments', json.dumps(final['tool_calls'], ensure_ascii=False, indent=2)))
    if final and final.get('error') is not None:
        notes.append('Terminal assistant error: ' + json.dumps(final['error'], ensure_ascii=False))
    if final and final.get('other_content'):
        answers.append(block('Terminal assistant · other retained content', json.dumps(final['other_content'], ensure_ascii=False, indent=2)))
    artifacts = raw.get('submission_artifacts', {})
    modules = artifacts.get('ib_submit_func', [])
    submits = [c for m in messages for c in m.get('tool_calls', []) if c.get('function') == 'submit']
    if agentic:
        notes.append(f'{len(submits)} submit call(s) recorded. A submit marker and the code file are different artifacts.')
        if not submits:
            notes.append('No final submission recorded; the file scorer may still have evaluated the retained module.')
        if modules:
            assert len(modules) == len(submits), card['id']
            answers.append(block(f'Last submitted func.py · submission {len(modules)}', modules[-1]))
        retained = raw['scores']['swe_style_humaneval_scorer'].get('answer')
        if isinstance(retained, str):
            if modules and retained == modules[-1]:
                notes.append('The final retained module is byte-identical to the last submitted module shown above.')
            else:
                answers.append(block('Final retained module · file-scorer artifact', retained))
        notes.append('Initial task files are environment references. The visible-history drawer preserves actual tool views and feedback; tool definitions remain in the complete source record.')
    else:
        notes.append('When present, the full assistant message is the delivered answer. Scorer-extracted code is not substituted: extraction can choose prose or a fallback scaffold.')
    if raw.get('error') or raw.get('limit'):
        notes.append('Recorded ending: ' + json.dumps({'error': raw.get('error'), 'limit': raw.get('limit')}, ensure_ascii=False))
    mc = raw.get('first_model_config') or {}
    metadata = {'recorded_model': mc.get('model'), 'error': raw.get('error'), 'limit': raw.get('limit')}
    return {'prompt_blocks': prompts, 'answer_blocks': answers, 'history_blocks': history,
            'history_label': 'Complete intervening visible messages and tool calls',
            'notes': notes, 'metadata': metadata}


def strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from strings(v)


def later_card(sid):
    path = CENSUS / 'sorh_single/samples' / (sid + '.json')
    raw = json.loads(path.read_text())
    review = json.loads((CENSUS / 'sorh_single/manual_ds_glm/reviews' / (sid + '.json')).read_text())
    for f in ['prompt', 'reasoning', 'reply']:
        assert sha(raw[f]) == review['source_sha256'][f], (sid, f)
    return dict(id=sid, model=raw['model'], prompt_id=raw['prompt_id'], condition=raw['condition'],
                draw=raw['sample'], review_status='full_read', reasoning_availability='stored',
                analysis=review['analysis'], prompt=raw['prompt'],
                reasoning_excerpt='\n\n'.join(e['quote'] for e in review['evidence'] if e['field'] == 'reasoning'),
                output_excerpt=raw['reply'], source_href=path.as_uri(), source_label=sid + ' · complete stored source',
                coverage_note='Complete archived-text review by the current team; this later review is added to the frozen dashboard card snapshot.')


def main():
    content = module('executive_content', HERE / 'notes/executive_summary_content.py')
    editorial = module('dashboard_editorial', HERE / 'notes/dashboard_reasoning_presentation.py')
    switch = module('full_switch_sources', HERE / 'src/dashboard_full_sources_switch.py')
    annotation_path = CENSUS / 'annotations.current.json'
    annotations = json.loads(annotation_path.read_text())
    findings = {f['id']: f for f in content.FINDINGS}
    examples = {e['sid']: e for f in content.FINDINGS for e in f['examples']}
    audit = {'base_annotations_sha256': hashlib.sha256(annotation_path.read_bytes()).hexdigest(),
             'new_model_calls': 0, 'api_spend': 0, 'candidate_code_executed': False,
             'pages': {}, 'sources': {}, 'curated_quotes': []}
    for f in content.FINDINGS:
        page = annotations['pages']['ib.html' if f['dataset'] == 'IB' else 'sorh.html']
        for e in f['examples']:
            if e['sid'] not in page['samples']:
                page['samples'][e['sid']] = later_card(e['sid'])
                # Add the reviewed example to relevant panels, without altering chart data or denominators.
                for gid in f['graphs']:
                    page['graphs'][gid]['sample_ids'].append(e['sid'])
                    page['graphs'][gid]['coverage']['reviewed'] += 1
    for name, page in annotations['pages'].items():
        cards = page['samples']
        for sid, card in cards.items():
            source = Path(unquote(urlparse(card['source_href']).path))
            raw = json.loads(source.read_text())
            if 'normalized_samples' in source.parts:
                full = ib(raw, card)
            elif 'probe_packets' in source.parts:
                full = switch.extract_probe(raw, card)
            elif 'packets' in source.parts:
                full = switch.extract_switch(raw, card)
            else:
                full = single(raw, card)
            for key in ['prompt_blocks', 'answer_blocks', 'history_blocks']:
                full[key] = [block(b['label'], b['text']) for b in full.get(key, [])]
            full['source_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
            card['full_source'] = full
            audit['sources'][sid] = {'path': str(source.relative_to(ROOT)), 'sha256': full['source_sha256'],
                'prompt_chars': sum(b['chars'] for b in full['prompt_blocks']),
                'answer_chars': sum(b['chars'] for b in full['answer_blocks']),
                'history_chars': sum(b['chars'] for b in full['history_blocks'])}
            if sid in examples:
                e = examples[sid]
                assert any(e['reasoning'] in s for s in strings(raw)), sid
                if e.get('output_quote'):
                    assert any(e['output_quote'] in s for s in strings(raw)), sid
                card['illustration'] = e
                audit['curated_quotes'].append(sid)

        def select(entry, fid, limit=2):
            preferred = [e['sid'] for e in findings[fid]['examples'] if e['sid'] in entry['sample_ids']]
            candidates = []
            for e in entry.get('bullet_evidence', []):
                candidates += e.get('representative_sample_ids') or e.get('source_sample_ids', [])[:1]
            candidates += entry['sample_ids']
            ids = list(dict.fromkeys(preferred))
            models = {cards[s]['model'] for s in ids}
            for sid in candidates:
                if len(ids) >= limit:
                    break
                if sid not in ids and sid in cards and cards[sid]['model'] not in models:
                    ids.append(sid); models.add(cards[sid]['model'])
            for sid in candidates:
                if len(ids) >= limit:
                    break
                if sid not in ids and sid in cards:
                    ids.append(sid)
            return ids[:limit]

        for gid, (fid, conclusion) in editorial.GRAPHS[name].items():
            entry = page['graphs'][gid]
            entry['conclusion'] = conclusion
            entry['hypothesis'] = findings[fid]['link']
            entry['featured_ids'] = select(entry, fid)
            if (name, gid) in editorial.FEATURED:
                entry['featured_ids'] = editorial.FEATURED[name, gid]
            entry['heading'] = 'What the reasoning adds'
        for section, (fid, gids) in editorial.SECTIONS[name].items():
            entry = page['sections'][section]
            entry['heading'] = 'Reasoning conclusion'
            entry['conclusion'] = editorial.SECTION_SUMMARIES.get((name, section), findings[fid]['takeaway'])
            entry['hypothesis'] = findings[fid]['link']
            # The original section's own evidence stays first. Add relevant featured cases when needed.
            candidates = [e['sid'] for e in findings[fid]['examples']]
            candidates += [sid for gid in gids for sid in page['graphs'][gid]['featured_ids']]
            entry['sample_ids'] = list(dict.fromkeys(entry['sample_ids'] + candidates))
            entry['featured_ids'] = select(entry, fid, 2)
            if section == 'fits':
                entry['hypothesis'] = 'Together: context-sensitive proxy pursuit is well supported; belief mediation and distinct internal systems are not established by these experiments.'
        if name == 'sorh.html':
            entry = page['sections']['trust']
            old = entry['bullets'][0]
            new = 'All 3,500 retained visible probe explanations are reviewed, including the 1,416 original first-message calls and 420 ancillary controls; those controls remain outside the original graph denominator. Task-trajectory review remains partial. Hidden probe reasoning and full raw probe replies were not stored; explanations were capped by the runner.'
            entry['bullets'][0] = new
            for e in entry.get('bullet_evidence', []):
                if e['text'] == old:
                    e['text'] = new
        page['presentation'] = {
            'intro': 'Your original statements, charts and illustrations are preserved. Added panels give the reasoning conclusion, its link to the split-brain hypothesis, and source examples. Open an example to read the complete archived prompt, selected reasoning and full retained answer.',
            'coverage': 'The all-sample reasoning census remains incomplete. Examples are reviewed cases, not new prevalence estimates. Probe cards show retained visible explanations and labels; their hidden reasoning and full raw answers were not saved.',
        }
        audit['pages'][name] = {'graphs': len(page['graphs']), 'sections': len(page['sections']), 'samples': len(cards),
                              'full_source_cards': sum('full_source' in s for s in cards.values()),
                              'featured_positions': sum(len(e['featured_ids']) for group in ['graphs', 'sections'] for e in page[group].values())}
        for group in ['graphs', 'sections']:
            for key, e in page[group].items():
                assert e['conclusion'] and e['hypothesis'] and e['featured_ids'], (name, key)
                assert set(e['featured_ids']) <= set(e['sample_ids']) <= set(cards), (name, key)
    out = CENSUS / 'annotations.presentation.json'
    out.write_text(json.dumps(annotations, ensure_ascii=False, separators=(',', ':')) + '\n')
    audit['output_sha256'] = hashlib.sha256(out.read_bytes()).hexdigest()
    (CENSUS / 'presentation_audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    print(json.dumps({'output': str(out), 'bytes': out.stat().st_size, 'pages': audit['pages'],
                      'curated_quotes_verified': len(audit['curated_quotes'])}, indent=2))


if __name__ == '__main__':
    main()
