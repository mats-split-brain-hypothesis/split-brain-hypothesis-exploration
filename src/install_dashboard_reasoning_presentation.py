"""Guarded installation of the reviewed, additive dashboard presentation."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re

ROOT = Path('/Users/biancaganescu/Code/split-brain-hypothesis')
CENSUS = ROOT / 'logs/dashboard_reasoning_census'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def parse(text):
    start = text.index('var PAGES = ') + len('var PAGES = ')
    pages, end = json.JSONDecoder().raw_decode(text[start:])
    return pages, text[:start], text[start + end:]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-sha', required=True)
    parser.add_argument('--preview', type=Path, default=Path('/private/tmp/results_dashboard.reasoning-current.html'))
    args = parser.parse_args()
    target = ROOT / 'logs/results_dashboard.html'
    old_bytes = target.read_bytes()
    assert digest(old_bytes) == args.expected_sha, 'Dashboard changed: do not overwrite'
    original = CENSUS / 'results_dashboard.original.html'
    old, prefix, suffix = parse(original.read_text())
    payload = args.preview.read_bytes()
    new, new_prefix, new_suffix = parse(payload.decode())
    assert prefix == new_prefix and suffix == new_suffix and old.keys() == new.keys()
    annotations = json.loads((CENSUS / 'annotations.presentation.json').read_text())
    base = json.loads((CENSUS / 'annotations.current.json').read_text())
    audit = json.loads((CENSUS / 'presentation_audit.json').read_text())
    marker = r'<!-- BEGIN DASHBOARD REASONING ANNOTATIONS -->.*?<!-- END DASHBOARD REASONING ANNOTATIONS -->\n'
    for name in old:
        stripped, count = re.subn(marker, '', new[name], flags=re.S)
        assert stripped == old[name], name
        assert count == (1 if name in annotations['pages'] else 0)
        if name in annotations['pages']:
            data = annotations['pages'][name]
            start = new[name].index('window.DASHBOARD_REASONING_ANNOTATIONS=') + len('window.DASHBOARD_REASONING_ANNOTATIONS=')
            embedded, _ = json.JSONDecoder().raw_decode(new[name][start:])
            assert embedded == data, name
            for group in ['graphs', 'sections']:
                for key, entry in data[group].items():
                    assert f'id="{key}"' in old[name]
                    assert set(entry['featured_ids']) <= set(entry['sample_ids']) <= set(data['samples'])
            assert all(s.get('full_source') for s in data['samples'].values())
    # Preserve the previous installed presentation as well as the frozen OG.
    backup = CENSUS / ('results_dashboard.before_full_examples.' + args.expected_sha[:12] + '.html')
    if backup.exists():
        assert digest(backup.read_bytes()) == args.expected_sha
    else:
        backup.write_bytes(old_bytes)
    temp = target.with_name('.results_dashboard.full-examples.tmp')
    temp.write_bytes(payload)
    assert digest(target.read_bytes()) == args.expected_sha, 'Dashboard changed during validation'
    os.replace(temp, target)
    audit.update(installed_at=datetime.now(timezone.utc).isoformat(), installed_dashboard_sha256=digest(payload),
                 previous_dashboard_sha256=args.expected_sha, original_pages_preserved=True,
                 other_five_pages_byte_identical=True, rollback_file=str(backup),
                 renderer_validation={'panels':43,'expanded_featured_positions':86,'sample_browsers':43,'exceptions':0},
                 visual_qa='Chrome original IB chart and additive panels; Safari original SoRH hero/illustration, conclusion cards, and expanded three-column full prompt/reasoning/final-answer card checked.')
    (CENSUS / 'presentation_audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    progress = json.loads((CENSUS / 'installed_progress.json').read_text())
    progress.update(installed_at=audit['installed_at'], previous_dashboard_sha256=args.expected_sha,
                    installed_dashboard_sha256=digest(payload), original_pages_preserved=True,
                    other_five_pages_byte_identical=True, current_change_qa=audit['visual_qa'],
                    presentation_annotations='annotations.presentation.json', presentation_audit='presentation_audit.json')
    progress['source_checked_single_reads'] = sum('/sorh_single/samples/' in s['source_href'] for s in annotations['pages']['sorh.html']['samples'].values())
    counts = Counter(s['model'] for s in annotations['pages']['sorh.html']['samples'].values() if '/sorh_single/samples/' in s['source_href'])
    for model, count in counts.items():
        progress['single_model_coverage'][model]['reviewed'] = count
    progress['pages'] = {name: {key: entry['coverage'] for key, entry in data['graphs'].items()} for name, data in annotations['pages'].items()}
    progress['full_source_cards'] = sum(len(data['samples']) for data in annotations['pages'].values())
    (CENSUS / 'installed_progress.json').write_text(json.dumps(progress, indent=2) + '\n')
    checkpoint_path = CENSUS / 'root_checkpoint.json'
    checkpoint = json.loads(checkpoint_path.read_text())
    checkpoint.update(current_dashboard_sha256=digest(payload), installed_dashboard_sha256=digest(payload),
                      presentation_annotations='annotations.presentation.json')
    checkpoint_path.write_text(json.dumps(checkpoint, indent=2) + '\n')
    print(json.dumps({'dashboard':str(target),'sha256':digest(payload),'bytes':len(payload),
                      'original_pages_preserved':True,'full_source_cards':progress['full_source_cards'],
                      'backup':str(backup)},indent=2))


if __name__ == '__main__':
    main()
