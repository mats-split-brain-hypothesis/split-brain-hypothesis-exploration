"""Offline reading batches for the frozen SoRH census; never invokes a model.

Emitting a batch does not mark it reviewed. A reviewer must read the complete
output and write a separate annotation with evidence before coverage is credited.
"""
import argparse
import hashlib
import json
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--models', nargs='+', required=True)
    parser.add_argument('--condition', nargs='*')
    parser.add_argument('--max-tokens', type=int, default=10000)
    args = parser.parse_args()
    root = args.root
    index = load(root / 'sorh_single/sample_index.json')
    tokens = {s['id']: sum(s['tokens'].values()) for s in
              load(root / 'sorh_single/token_counts.json')['per_sample']}
    reviewed = set()
    for path in (root / 'manual_reviews').glob('*.json'):
        for sample in load(path).get('samples', []):
            if sample.get('reviewer') and sample.get('coverage'):
                reviewed.add(sample['sample_id'])
    rows = [s for s in index if s['model'] in args.models and
            s['id'] not in reviewed and
            (not args.condition or s['condition'] in args.condition)]
    rows.sort(key=lambda s: (tokens[s['id']], s['id']))
    selected = []
    used = 0
    for row in rows:
        count = tokens[row['id']]
        if used + count > args.max_tokens:
            continue
        selected.append(row)
        used += count
    if not selected:
        raise SystemExit('No pending whole sample fits; explicitly read the next large sample in contiguous parts.')
    manifest = {'status': 'emitted_not_reviewed', 'total_raw_field_tokens': used,
                'samples': []}
    for row in selected:
        path = root / 'sorh_single/samples' / (row['id'] + '.json')
        sample = load(path)
        fields = {field: sample[field] for field in ('prompt', 'reasoning', 'reply')}
        manifest['samples'].append({
            'sample_id': row['id'], 'model': row['model'],
            'condition': row['condition'], 'prompt_id': row['prompt_id'],
            'source': str(path),
            'field_chars': {field: len(text) for field, text in fields.items()},
            'field_sha256': {field: hashlib.sha256(text.encode()).hexdigest()
                             for field, text in fields.items()}})
        print('\n=== COMPLETE SAMPLE ' + row['id'] + ' | ' + row['model'] + ' ===')
        for field, text in fields.items():
            print('\n' + field.upper() + ':\n' + text)
        print('\n=== END SAMPLE ' + row['id'] + ' ===')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(f'\nCOMPLETE BATCH: {len(selected)} samples; {used} raw-field tokens.')


if __name__ == '__main__':
    main()
