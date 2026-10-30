#!/usr/bin/env python3
"""Validate direct-read ledgers and emit a compact, offline dashboard sidecar.

No model calls; no semantic classification of unread text. Editorial bullets below
refer to explicitly named, already-read cases. New ledger entries add sample cards
and coverage counts, but do not silently broaden those editorial conclusions.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def index(items, key):
    out = {}
    for item in items:
        ident = item[key]
        if ident in out:
            raise ValueError(f"Duplicate {key}: {ident}")
        out[ident] = item
    return out


def check(ok, message):
    if not ok:
        raise ValueError(message)


def spans_cover(spans, target):
    cursor, end = target
    for a, b in sorted(spans):
        if a <= cursor <= b:
            cursor = max(cursor, b)
    return cursor >= end


def validate_spans(spans, text, ident):
    for pair in spans:
        check(len(pair) == 2 and all(type(x) is int for x in pair), f"Bad range: {ident}")
        check(0 <= pair[0] <= pair[1] <= len(text), f"Out-of-bounds range: {ident}")


def exact_evidence(annotation, fields):
    evidence = annotation.get("evidence", [])
    check(bool(evidence), f"Missing evidence: {annotation['sample_id']}")
    for e in evidence:
        check(e['field'] in fields, f"Unknown evidence field: {e}")
        text = fields[e['field']]
        validate_spans([[e['start'], e['end']]], text, annotation['sample_id'])
        check(text[e['start']:e['end']] == e['quote'], f"Evidence mismatch: {annotation['sample_id']}")


class Census:
    def __init__(self, base):
        self.base = base
        self.manifests = {}
        for filename, key in [('packet_manifest.jsonl', 'packet_id'), ('probe_packet_manifest.jsonl', 'id')]:
            self.manifests.update(index(rows(base / filename), key))
        self.cache = {}
        self.turn_notes = index(rows(base / 'annotations.jsonl'), 'sample_id')
        self.probe_notes = index(rows(base / 'probe_annotations.jsonl'), 'sample_id')
        self.groups = index(rows(base / 'group_annotations.jsonl'), 'packet_id')
        self.turn_reads = defaultdict(list)
        self.probe_reads = defaultdict(list)
        for row in rows(base / 'read_ranges.jsonl'):
            self.turn_reads[(row['sample_id'], row['field'])].append(row)
        for row in rows(base / 'probe_read_ranges.jsonl'):
            self.probe_reads[(row['packet_id'], row['field'])].append(row)
        self.calls = index(rows(base / 'probe_calls.jsonl'), 'sample_id')
        self.conversations = index(rows(base / 'conversations.jsonl'), 'sample_id')
        self.validated_probe_fields = set()

    def packet(self, ident):
        if ident not in self.cache:
            m = self.manifests[ident]
            folder = 'probe_packets' if ident.startswith('sorh-probe-') else 'packets'
            path = self.base / folder / (ident + '.json')
            blob = path.read_bytes()
            check(hashlib.sha256(blob).hexdigest() == m['sha256'], f"Frozen packet changed: {ident}")
            self.cache[ident] = json.loads(blob)
        return self.cache[ident]

    def probe_field(self, packet_id, field, active=None):
        key = (packet_id, field)
        if key in self.validated_probe_fields:
            return
        active = set() if active is None else set(active)
        check(key not in active, f"Cyclic read reuse: {key}")
        active.add(key)
        text = self.packet(packet_id)['review_fields'][field]
        read_spans = []
        for row in self.probe_reads[key]:
            check(row['sha256'] == sha(text), f"Read hash mismatch: {key}")
            span = [row['start'], row['end']]
            validate_spans([span], text, str(key))
            if row.get('reused_ranges'):
                pieces = row.get('direct_read_ranges', []).copy()
                validate_spans(pieces, text, str(key))
                for reuse in row['reused_ranges']:
                    ref_id = reuse['reference_packet']
                    self.probe_field(ref_id, field, active)
                    ref = self.packet(ref_id)['review_fields'][field]
                    a, b = reuse['range']
                    c, d = reuse['reference_range']
                    validate_spans([[a, b]], text, str(key))
                    validate_spans([[c, d]], ref, ref_id)
                    check(text[a:b] == ref[c:d], f"Reused text differs: {key}")
                    pieces.append([a, b])
                check(spans_cover(pieces, span), f"Read/reuse gap: {key}")
            read_spans.append(span)
        check(spans_cover(read_spans, [0, len(text)]), f"Incomplete packet field reading: {key}")
        self.validated_probe_fields.add(key)

    def validate(self):
        for ident, note in self.turn_notes.items():
            packet = self.packet(note['packet_id'])
            turn = next(t for t in packet['turns'] if t['turn_id'] == ident)
            fields = dict(zip(('prompt', 'reasoning', 'reply'), (turn['user_message'], turn['assistant_reasoning'], turn['assistant_output'])))
            check(note['review_status'] == 'full_read', f"Unexpected incomplete turn note: {ident}")
            check(note['source'] == turn['source'], f"Source mismatch: {ident}")
            for field, text in fields.items():
                coverage = note['coverage'][field]
                validate_spans(coverage, text, ident)
                check(spans_cover(coverage, [0, len(text)]), f"Incomplete annotation coverage: {ident}")
                check(note['source_sha256'][field] == sha(text), f"Annotation hash mismatch: {ident}")
                reads = self.turn_reads[(ident, field)]
                for read in reads:
                    check(read['packet_id'] == note['packet_id'] and read['sha256'] == sha(text), f"Read provenance mismatch: {ident}")
                    validate_spans([[read['start'], read['end']]], text, ident)
                check(spans_cover([[r['start'], r['end']] for r in reads], [0, len(text)]), f"Incomplete direct read: {ident}")
            exact_evidence(note, fields)
        for ident, note in self.probe_notes.items():
            packet = self.packet(note['packet_id'])
            fields = packet['review_fields']
            member = next(m for m in packet['review_members'] if m['id'] == ident)
            call = self.calls[ident]
            check(note['review_status'] == 'visible_explanation_only' and note['review_complete_for_available_text'], f"Incomplete visible review: {ident}")
            check(note['hidden_reasoning_available'] is False and packet['hidden_reasoning_available'] is False, f"Invented hidden reasoning: {ident}")
            check(note['availability'] == member['availability'], f"Availability mismatch: {ident}")
            check(note['source'] == member['source'] == call['source'], f"Probe source mismatch: {ident}")
            check(note['packet_sha256'] == self.manifests[note['packet_id']]['sha256'], f"Probe annotation packet hash mismatch: {ident}")
            for field, expected in member['field_ranges'].items():
                self.probe_field(note['packet_id'], field)
                check(note['source_sha256'][field] == sha(fields[field]), f"Probe annotation field hash mismatch: {ident}")
                validate_spans(note['coverage'][field], fields[field], ident)
                check(all(spans_cover(note['coverage'][field], target) for target in expected), f"Incomplete probe member: {ident}")
            exact_evidence(note, fields)
        for ident, note in self.groups.items():
            packet = self.packet(ident)
            check(note['review_status'] == 'full_read', f"Incomplete group note: {ident}")
            check(all(t['turn_id'] in self.turn_notes for t in packet['turns']), f"Incomplete canonical group: {ident}")
            check(note['canonical_turns_read'] == len(packet['turns']), f"Wrong group count: {ident}")
            check(set(note['branch_ids']) == {b['conversation_id'] for b in packet['branches']}, f"Wrong group branches: {ident}")


def display_excerpt(text, limit=1000):
    if len(text) <= limit:
        return text
    return text[:limit] + '\n[Display excerpt; complete stored text is in the linked packet.]'


def probe_sample(census, ident):
    note, call = census.probe_notes[ident], census.calls[ident]
    packet = census.packet(note['packet_id'])
    member = next(m for m in packet['review_members'] if m['id'] == ident)
    fields = packet['review_fields']
    explanation = '\n'.join(fields['reasoning'][a:b] for a, b in member['primary_field_ranges']['reasoning'])
    return {
        'id': ident, 'model': packet['model'], 'prompt_id': packet['prompt_id'],
        'condition': packet['cell'], 'draw': call['draw'],
        'title': f"{packet['model']} · {packet['prompt_id']} · {packet['cell']} · {call['probe']} · draw {call['draw']}",
        'review_status': 'visible_explanation_only', 'reasoning_availability': 'not_stored_by_runner',
        'analysis': note['analysis'], 'prompt': display_excerpt(fields['prompt'], 1200),
        'explanation': explanation, 'output': f"Stored parsed label: {call['parsed_answer']}\nStored raw label: {call['raw_label']}",
        'limit': 'Hidden reasoning was not saved. All retained visible explanation and stored context were read. The original runner limited explanations to 800 characters; missing original text cannot be recovered.' + (' This explanation hits the original clipping limit or ends in an ellipsis.' if member['availability']['source_at_clip_limit_or_ellipsis'] else ''),
        'source_href': f"dashboard_reasoning_census/sorh_switch/probe_packets/{note['packet_id']}.json",
        'source_label': ident,
        'evidence_offsets': [{k: e[k] for k in ('field', 'start', 'end')} for e in note['evidence']],
        'annotation_ledger': 'dashboard_reasoning_census/sorh_switch/probe_annotations.jsonl',
        'source': note['source'],
        'packet_id': note['packet_id'], 'graph_dataset_ids': call['graph_dataset_ids'],
    }


def switch_sample(census, conversation):
    ids = [t['canonical_turn_id'] for t in conversation['turns']]
    notes = [census.turn_notes[i] for i in ids]
    packet_id = notes[0]['packet_id']
    packet = census.packet(packet_id)
    turns = {t['turn_id']: t for t in packet['turns']}
    ordered = [turns[i] for i in ids]
    quotations = []
    for note in notes[2:]:
        selected = [e['quote'] for e in note['evidence'] if e['field'] == 'reasoning'][:2]
        quotations.extend(f"Turn {note['turn']}: {q}" for q in selected)
    return {
        'id': conversation['sample_id'], 'model': conversation['model'], 'prompt_id': conversation['prompt_id'],
        'arm': conversation['arm'], 'draw': conversation['draw'],
        'review_status': 'full_read', 'reasoning_availability': 'stored',
        'analysis': notes[-1]['analysis'],
        'bullets': [f"Turn {n['turn']}: {n['analysis']}" for n in notes],
        'prompt': '\n\n'.join(f"Turn {t['turn']}: {t['user_message']}" for t in ordered),
        'reasoning_excerpt': '\n\n'.join(quotations),
        'output_excerpt': f"Final turn {ordered[-1]['turn']}:\n" + display_excerpt(ordered[-1]['assistant_output'], 1400),
        'coverage_note': f"All {len(ordered)} stored turns, their full reasoning, prompts and outputs were directly read. Shared initial turns count once in the canonical-turn ledger. This card displays selected exact quotations.",
        'limit': f"{conversation['cohort']} cohort; case-level evidence, not a prevalence estimate or proof of a latent objective.",
        'source_href': f"dashboard_reasoning_census/sorh_switch/packets/{packet_id}.json",
        'source_label': conversation['sample_id'], 'canonical_turn_ids': ids,
        'evidence_offsets': [{'sample_id': n['sample_id'], **{k: e[k] for k in ('field', 'start', 'end')}} for n in notes for e in n['evidence']],
        'annotation_ledger': 'dashboard_reasoning_census/sorh_switch/annotations.jsonl',
        'packet_id': packet_id, 'cohort': conversation['cohort'],
    }


def build(census):
    census.validate()
    complete = [c for c in census.conversations.values() if not c['missing_turns'] and c['turns'] and all(t['canonical_turn_id'] in census.turn_notes for t in c['turns'])]
    samples = {c['sample_id']: switch_sample(census, c) for c in complete}
    datasets = defaultdict(list)
    for ident in census.probe_notes:
        for dataset in census.calls[ident]['graph_dataset_ids']:
            datasets[dataset].append(ident)
    branch_ids = list(samples)
    probe_ids = set(datasets['sorh_probe'] + datasets['sorh_switch_probe20'] + datasets['sorh_switch_probe'])
    samples.update({ident: probe_sample(census, ident) for ident in sorted(probe_ids)})
    graphs = {}

    def graph(ident, unit, total, ids, limit, unavailable=0):
        graphs[ident] = {'heading': 'What the reasoning adds', 'coverage': {'unit': unit, 'total': total, 'reviewed': len(ids), 'reasoning_unavailable': unavailable}, 'bullets': [], 'bullet_evidence': [], 'limit': limit, 'sample_ids': sorted(ids)}

    def bullet(graph_id, text, source_ids):
        check(source_ids and all(i in samples for i in source_ids), f"Editorial claim lacks completed samples: {graph_id}")
        graphs[graph_id]['bullets'].append(text)
        graphs[graph_id]['bullet_evidence'].append({'text': text, 'source_sample_ids': source_ids})

    totals = Counter(d for c in census.calls.values() for d in c['graph_dataset_ids'])
    graph('f-probe', 'retained probe explanations', totals['sorh_probe'], datasets['sorh_probe'], 'Partial cross-model review. Complete GLM subsets are identified below; repeated draws are not independent tasks. These are separate probe answers, not the task-performing model’s hidden reasoning.', totals['sorh_probe'])
    graph('f-sw-probe', 'retained probe explanations', totals['sorh_switch_probe20'], datasets['sorh_switch_probe20'], '20-prompt switch probes only. Purpose and who-checks are distinct questions. Missing hidden reasoning and original explanation clipping prevent a full reasoning census.', totals['sorh_switch_probe20'])
    graph('f-switch', 'planned branch conversations', len(census.conversations), branch_ids, 'Coverage separates the 240 planned 20-prompt branches and 180 earlier branches; original charts use 235 and 177 valid final outcomes respectively. Shared prefixes are not independent samples. ' + f"Separately, {len(datasets['sorh_switch_probe'])}/{totals['sorh_switch_probe']} retained earlier switch-probe explanations were reviewed; their hidden reasoning was not stored. These probe calls are not added to the branch-conversation denominator.")
    graphs['f-switch']['sample_ids'] = sorted(branch_ids + datasets['sorh_switch_probe'])
    graphs['f-switch']['probe_coverage'] = {'unit': 'retained earlier switch-probe explanations', 'total': totals['sorh_switch_probe'], 'reviewed': len(datasets['sorh_switch_probe']), 'reasoning_unavailable': totals['sorh_switch_probe']}
    old = [c['sample_id'] for c in complete if c['cohort'] == '3_prompt_5_draw']
    graph('f-mi-split', 'earlier-cohort planned branch conversations', sum(c['cohort'] == '3_prompt_5_draw' for c in census.conversations.values()), old, 'This sidecar covers only the earlier switch component (177 valid final outcomes from 180 planned branches). It does not claim review of the separate 160 class/plain note-to-person samples in this figure. Mentioning “nobody” is weaker evidence than interpreting the whole trajectory.')
    for gid, cohort in [('f-switch', None), ('f-mi-split', '3_prompt_5_draw')]:
        graphs[gid]['coverage_by_cohort'] = {name: {'reviewed': sum(c['cohort'] == name for c in complete), 'planned': sum(c['cohort'] == name for c in census.conversations.values())} for name in ('20_prompt', '3_prompt_5_draw') if cohort is None or name == cohort}

    def group_ids(packet_id):
        return [c['sample_id'] for c in complete if samples[c['sample_id']]['packet_id'] == packet_id]

    clean = group_ids('20_prompt__qwen24__sorh_573__0') + group_ids('20_prompt__qwen24__sorh_931__0')
    if len(clean) == 6:
        bullet('f-switch', 'Two fully read Qwen 2.4T congratulation cases: off/nobody restores natural prose, while continued scoring preserves explicit density planning. The reasoning sometimes targets exactly 8/10 rather than maximizing the metric.', clean)
    rebound = group_ids('20_prompt__qwen24__sorh_450__0')
    if len(rebound) == 3:
        bullet('f-switch', 'Counterexample within the reviewed cases: in the gratitude task, nobody-checks turn 5 revives the 8/10 goal and counts ten phrases (“to be safe include at least 8”). This can reflect persistence of the earlier instruction; the switch is not a permanent reset.', rebound)
    earlier = group_ids('3_prompt_5_draw__qwen24__sorh_223__4')
    if len(earlier) == 3:
        text = 'One earlier Qwen 2.4T business-email draw becomes plainer before the switch: it interprets 9/10 as overshooting an 8/10 target. Continued scoring later restores jargon after lower feedback. Score status and numerical feedback change together, so the off/on contrast alone does not isolate a latent preference.'
        bullet('f-switch', text, earlier)
        bullet('f-mi-split', text, earlier)

    glm = [i for i in datasets['sorh_probe'] if census.calls[i]['model'] == 'z-ai/glm-5.2']
    core = [i for i in glm if census.calls[i]['cell'] in ('B', 'G', 'r_student')]
    wild = [i for i in glm if census.calls[i]['cell'] == 'wildchat']
    if len(core) == 180:
        counts = {cell: Counter(census.calls[i]['parsed_answer'] for i in core if census.calls[i]['cell'] == cell) for cell in ('B', 'G', 'r_student')}
        check([counts[c]['Real'] for c in ('B', 'G', 'r_student')] == [57, 0, 53], 'GLM editorial count no longer matches frozen data')
        bullet('f-probe', 'Complete GLM 20-prompt subset: Real is 57/60 in plain prompts, 0/60 with an explicit score, and 53/60 with a classroom rationale. All seven remaining classroom evaluation labels concern ratio/share tasks; explanations call their constraints artificial. A Real label can still explicitly recognize rubric gaming.', core)
    if len(wild) == 174:
        counts = Counter(census.calls[i]['parsed_answer'] for i in wild)
        check(counts['Real'] == 140 and counts[None] == 1, 'GLM WildChat editorial count mismatch')
        by_context = defaultdict(set)
        for i in wild:
            if census.calls[i]['parsed_answer'] is not None:
                by_context[census.calls[i]['prompt_id']].add(census.calls[i]['parsed_answer'])
        check(sum(len(x) > 1 for x in by_context.values()) == 12, 'GLM context disagreement mismatch')
        bullet('f-probe', 'Complete GLM WildChat subset: 140/173 valid labels are Real; 12/58 contexts receive disagreeing valid labels across draws. Three Real labels come from an empty stored context and explicit base-rate guessing; one answer is unparsed. User traffic includes quizzes and a jailbreak, so it is not ground truth for non-evaluation intent.', wild)
    matched = [i for i in datasets['sorh_switch_probe20'] if census.probe_notes[i]['packet_id'] in {'sorh-probe-0080f92da1c0c8b8337d', 'sorh-probe-40853ad2bda66fb76e92', 'sorh-probe-9e0da99478b855fbcb45'}]
    if len(matched) == 12:
        purpose = [i for i in matched if census.calls[i]['probe'] == 'purpose_mc']
        check(len(purpose) == 9 and all(census.calls[i]['parsed_answer'] == 'Capability Evaluation' for i in purpose), 'Matched purpose claim mismatch')
        bullet('f-sw-probe', 'Matched promotion example (Qwen 2.4T behavior; Qwen Max probe): all 9 purpose answers say Capability Evaluation across on/off/nobody. Yet who-checks changes from automatic grader to unsure to nobody. Natural-prose recovery in off/nobody therefore coexists with an unchanged broad evaluation-purpose label.', matched + group_ids('20_prompt__qwen24__sorh_573__0'))
        bullet('f-sw-probe', 'Read this as a descriptive dissociation, not a causal mediation result: probes are separate model calls. The off explanation is uncertain whether “this reply” means the task answer or the meta-probe; nobody-scoring is also interpreted as nobody-checking.', matched)
    return {'schema': 'dashboard-reasoning-sidecar-v1', 'as_of': '2026-10-27', 'validation': {'canonical_turns_full_read': len(census.turn_notes), 'complete_branch_conversations': len(complete), 'probe_calls_available_text_read': len(census.probe_notes), 'hidden_probe_reasoning_read': 0, 'method': 'Existing agents directly read full available text; exact hashes, coverage ranges, reused boilerplate and quote offsets validated offline.'}, 'pages': {'sorh.html': {'graphs': graphs, 'samples': samples}}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--census-dir', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = build(Census(args.census_dir))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'output': str(args.output), 'bytes': args.output.stat().st_size, **result['validation'], 'graphs': {k: v['coverage'] for k, v in result['pages']['sorh.html']['graphs'].items()}}, indent=2))


if __name__ == '__main__':
    main()
