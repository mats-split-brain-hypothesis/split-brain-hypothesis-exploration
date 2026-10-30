"""Coverage must reject unread, altered, overlapping or missing text."""
import copy
import unittest

from build_dashboard_reasoning_notes import digest, validate_same_sample_reuse, validate_direct_changed_span


class ExactReuseCoverageTests(unittest.TestCase):
    def setUp(self):
        self.source = {'prompt': 'P', 'reasoning': 'éxéxéx', 'reply': 'R'}
        self.manifest = {
            'schema': 'exact-same-sample-direct-source-v1',
            'source_sha256': {f: digest(s) for f, s in self.source.items()},
            'direct_ranges': {'prompt': [[0, 1]], 'reasoning': [[0, 2]], 'reply': [[0, 1]]},
            'direct_chars': {'prompt': 1, 'reasoning': 2, 'reply': 1},
            'exact_reused_chars': {'prompt': 0, 'reasoning': 4, 'reply': 0},
            'maps': [
                {'target_field': 'reasoning', 'target_range': [a, a + 2],
                 'source_field': 'reasoning', 'source_range': [0, 2],
                 'sha256': digest('éx'), 'source_utf8_range': [0, 3],
                 'target_utf8_range': [a // 2 * 3, (a // 2 + 1) * 3]}
                for a in (2, 4)
            ],
        }

    def test_exact_unicode_spans_cover_every_character(self):
        direct, reused = validate_same_sample_reuse(self.source, self.manifest)
        self.assertEqual(direct['reasoning'] + reused['reasoning'], 6)

    def test_unread_source_cannot_supply_coverage(self):
        bad = copy.deepcopy(self.manifest)
        bad['maps'][1]['source_range'] = [2, 4]
        bad['maps'][1]['source_utf8_range'] = [3, 6]
        with self.assertRaises(AssertionError):
            validate_same_sample_reuse(self.source, bad)

    def test_changed_text_is_not_a_match_even_with_updated_hashes(self):
        source = dict(self.source, reasoning='éxéyéx')
        bad = copy.deepcopy(self.manifest)
        bad['source_sha256']['reasoning'] = digest(source['reasoning'])
        bad['maps'][0]['sha256'] = digest('éy')
        with self.assertRaises(AssertionError):
            validate_same_sample_reuse(source, bad)

    def test_missing_overlap_or_wrong_utf8_offsets_are_rejected(self):
        for alteration in ('gap', 'overlap', 'utf8'):
            bad = copy.deepcopy(self.manifest)
            if alteration == 'gap':
                bad['maps'].pop()
            elif alteration == 'overlap':
                bad['maps'].append(copy.deepcopy(bad['maps'][0]))
            else:
                bad['maps'][0]['target_utf8_range'] = [2, 4]
            with self.subTest(alteration=alteration), self.assertRaises(AssertionError):
                validate_same_sample_reuse(self.source, bad)

    def test_direct_changed_text_requires_exact_content_and_read_status(self):
        span = {'range': [1, 3], 'text': 'éx', 'kind': 'direct_read_changed_span'}
        self.assertEqual(validate_direct_changed_span('AéxZ', span), (1, 3))
        for change in ({'text': 'éy'}, {'kind': 'unread'}, {'range': [-1, 3]},
                       {'kind': 'newline_separator'}):
            with self.subTest(change=change), self.assertRaises(AssertionError):
                validate_direct_changed_span('AéxZ', dict(span, **change))


if __name__ == '__main__':
    unittest.main()
