import tempfile
import unittest
from pathlib import Path

from citation_verifier.core import Corpus, canonical_citation, verify


def judgment(id='a'):
    return dict(id=id, case_name='Example v State', court='Supreme Court of India', date='2023-01-01',
                bench_size=2, citations=['2023 INSC 100', '[2023] 1 SCR 10', '(2023) 2 SCC 30', 'AIR 2023 SC 40', '(2023) 1 SCALE 50'],
                source_url='https://example.org/judgment.pdf', paragraph_numbering_complete=True,
                paragraphs=[dict(number=1, page=1, text='The appellant shall pay 100 rupees within thirty days.'),
                            dict(number=2, page=1, text='The remedy is available. However, the application must be timely.'),
                            dict(number=3, page=2, text='The court does not permit unrestricted detention.')])


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.corpus = Corpus([judgment()])

    def request(self, **kwargs):
        return dict(citation='2023 INSC 100', quote='The appellant shall pay 100 rupees within thirty days.', **kwargs)

    def codes(self, result):
        return {x['code'] for x in result['findings']}

    def test_canonical_reporters(self):
        for a,b in [('2023INSC100','2023 INSC 100'),('[2023] 1 S.C.R. 10','(2023) 1 SCR 10'),
                    ('AIR 2023 S.C. 40','A.I.R. 2023 SC 40'),('(2023) 2 SCC 30','2023 2 S.C.C. 30')]:
            self.assertEqual(canonical_citation(a),canonical_citation(b))

    def test_normalized_quote_and_evidence(self):
        r=verify(self.corpus, dict(citation='[2023] 1 S.C.R. 10', quote='The appellant\nshall pay 100 rupees within thirty days.'))
        self.assertEqual(r['status'],'consistent')
        self.assertEqual(r['evidence'][0]['number'],1)
        self.assertIn('source_url',r['match'])

    def test_negation_is_never_normalized_away(self):
        r=verify(self.corpus,dict(citation='2023 INSC 100',quote='The court does permit unrestricted detention.'))
        self.assertIn('QUOTE_MISMATCH',self.codes(r))

    def test_mismatched_numeric_quote(self):
        r=verify(self.corpus,dict(citation='2023 INSC 100',quote='The appellant shall pay 900 rupees within thirty days.'))
        self.assertIn('QUOTE_MISMATCH',self.codes(r))

    def test_wrong_court_bench_pinpoint(self):
        r=verify(self.corpus,self.request(court='Delhi High Court',bench_size=5,pinpoint=999))
        self.assertTrue({'COURT_MISMATCH','BENCH_MISMATCH','PINPOINT_NOT_FOUND'} <= self.codes(r))

    def test_quote_in_other_paragraph(self):
        r=verify(self.corpus,self.request(pinpoint=3))
        self.assertIn('PINPOINT_QUOTE_MISMATCH',self.codes(r))
        self.assertEqual(r['evidence'][0]['number'],1)

    def test_selective_quote(self):
        r=verify(self.corpus,dict(citation='2023 INSC 100',quote='The remedy is available.'))
        self.assertEqual(r['status'],'review')
        self.assertIn('CONTEXT_REVIEW',self.codes(r))

    def test_full_qualification_not_flagged(self):
        r=verify(self.corpus,dict(citation='2023 INSC 100',quote='The remedy is available. However, the application must be timely.'))
        self.assertEqual(r['status'],'consistent')

    def test_missing_local_citation_is_unresolved_not_fabricated(self):
        r=verify(self.corpus,dict(citation='2099 INSC 99',quote='An example quote.'))
        self.assertEqual(r['status'],'unresolved')
        self.assertIn('NOT_IN_CORPUS',self.codes(r))

    def test_ambiguous_alias_abstains(self):
        r=verify(Corpus([judgment('a'),judgment('b')]),self.request())
        self.assertEqual(r['status'],'unresolved')
        self.assertIn('AMBIGUOUS_CITATION',self.codes(r))

    def test_name_only_not_silently_fuzzy_resolved(self):
        r=verify(self.corpus,dict(citation='Example vs State',proposition='A payment is required'))
        self.assertEqual(r['status'],'unresolved')

    def test_proposition_only_is_not_entailment(self):
        r=verify(self.corpus,dict(citation='2023 INSC 100',proposition='Everyone may detain anybody'))
        self.assertEqual(r['status'],'review')
        self.assertIn('PROPOSITION_REVIEW',self.codes(r))

    def test_incomplete_numbering_abstains_on_missing_pinpoint(self):
        row=judgment(); row['paragraph_numbering_complete']=False
        r=verify(Corpus([row]),self.request(pinpoint=900))
        self.assertIn('PINPOINT_UNRESOLVED',self.codes(r))

    def test_input_validation(self):
        for req in [None, [], {}, {'citation':''},self.request(pinpoint=True),self.request(bench_size=0),self.request(pinpoint='2'),dict(citation='x',quote='a'*20001)]:
            with self.subTest(request=str(req)[:80]),self.assertRaises(ValueError): verify(self.corpus,req)

    def test_duplicate_paragraphs_and_ids_rejected(self):
        row=judgment(); row['paragraphs'].append(row['paragraphs'][0])
        with self.assertRaises(ValueError): Corpus([row])
        with self.assertRaises(ValueError): Corpus([judgment(),judgment()])

    def test_bad_corpus_line_has_location(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.jsonl'; p.write_text('{}\n',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'line 1'): Corpus.load(p)

    def test_word_boundaries(self):
        r=verify(self.corpus,dict(citation='2023 INSC 100',quote='restricted detention'))
        self.assertIn('QUOTE_MISMATCH',self.codes(r))

    def test_non_sc_air_is_not_sc(self):
        r=verify(self.corpus,dict(citation='AIR 2023 DEL 40',quote='a judgment'))
        self.assertEqual(r['status'],'unresolved')

    def test_no_numbered_paragraphs_fails(self):
        row=judgment(); row['paragraphs']=[]
        with self.assertRaises(ValueError): Corpus([row])

    def test_duplicate_alias_within_same_record_not_ambiguous(self):
        row=judgment(); row['citations'].append('2023INSC100')
        self.assertEqual(verify(Corpus([row]),self.request())['status'],'consistent')

    def test_unknown_bench_requires_review(self):
        row=judgment(); row['bench_size']=None
        r=verify(Corpus([row]),self.request(bench_size=2))
        self.assertIn('BENCH_UNRESOLVED',self.codes(r))

    def test_matching_quote_does_not_validate_separate_proposition(self):
        r=verify(self.corpus,self.request(proposition='Everyone is exempt from payment'))
        self.assertIn('PROPOSITION_REVIEW',self.codes(r))

    def test_normalized_quote_still_checks_context(self):
        r=verify(self.corpus,dict(citation='2023 INSC 100',quote='the remedy   is available'))
        self.assertIn('CONTEXT_REVIEW',self.codes(r))

    def test_adjacent_qualifier_exposed(self):
        row=judgment(); row['paragraphs'][0]['text']='The remedy is available to litigants.'
        row['paragraphs'][1]['text']='However, the application must be timely.'
        r=verify(Corpus([row]),dict(citation='2023 INSC 100',quote='The remedy is available to litigants.'))
        self.assertIn('CONTEXT_REVIEW',self.codes(r))
        self.assertIn(2,[p['number'] for p in r['evidence']])

    def test_mismatch_returns_candidate_not_verified_match(self):
        r=verify(self.corpus,dict(citation='2023 INSC 100',quote='The appellant shall pay 900 rupees within thirty days.'))
        self.assertTrue(r['evidence'])
        self.assertEqual(r['evidence'][0]['match_type'],'candidate')

    def test_punctuation_only_quote_rejected(self):
        with self.assertRaises(ValueError): verify(self.corpus,dict(citation='2023 INSC 100',quote='...'))

    def test_citation_length_and_unknown_fields(self):
        with self.assertRaises(ValueError): verify(self.corpus,dict(citation='a'*3000,quote='text'))
        with self.assertRaises(ValueError): verify(self.corpus,self.request(pinpont=3))

    def test_candidate_is_not_a_pinpoint_quote_match(self):
        r=verify(self.corpus,dict(citation='2023 INSC 100',quote='The appellant shall pay 900 rupees within thirty days.',pinpoint=999))
        self.assertNotIn('PINPOINT_QUOTE_MISMATCH',self.codes(r))

    def test_invalid_corpus_types_are_value_errors(self):
        for key,value in [('id',[]),('id',1),('case_name',True),('paragraphs','bad'),('bench_size',False),('source_url','javascript:alert(1)'),('date','yesterday'),('paragraph_numbering_complete','yes')]:
            row=judgment(); row[key]=value
            with self.subTest(field=key),self.assertRaises(ValueError): Corpus([row])

    def test_physical_line_number_in_corpus_error(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.jsonl'; p.write_text('\n{}\n',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'line 2'): Corpus.load(p)

    def test_repeated_quote_with_correct_pinpoint_is_valid(self):
        row=judgment(); row['paragraphs'][2]['text']=row['paragraphs'][0]['text']
        r=verify(Corpus([row]),self.request(pinpoint=3))
        self.assertNotIn('PINPOINT_QUOTE_MISMATCH',self.codes(r))

    def test_court_alias_is_accepted(self):
        self.assertEqual(verify(self.corpus,self.request(court='SC'))['status'],'consistent')

    def test_hash_and_metadata_url_are_returned(self):
        row=judgment(); row.update(sha256='a'*64,metadata_url='https://example.org/meta.json')
        r=verify(Corpus([row]),self.request())
        self.assertEqual(r['match']['sha256'],'a'*64)
        self.assertEqual(r['match']['metadata_url'],row['metadata_url'])

    def test_smart_apostrophe_and_ligature_normalization(self):
        row=judgment(); row['paragraphs'][0]['text']='The court’s ﬁnding remains applicable.'
        r=verify(Corpus([row]),dict(citation='2023 INSC 100',quote="The court's finding remains applicable."))
        self.assertEqual(r['status'],'consistent')

    def test_unsupported_non_english_quote_not_dropped(self):
        with self.assertRaises(ValueError): verify(self.corpus,dict(citation='2023 INSC 100',quote='नहीं'))

    def test_null_optional_court_is_accepted(self):
        self.assertEqual(verify(self.corpus,self.request(court=None))['status'],'consistent')

    def test_quote_match_quality_does_not_certify_candidates(self):
        exact=verify(self.corpus,self.request())
        normalized=verify(self.corpus,dict(citation='2023 INSC 100',quote='the appellant shall pay 100 rupees within thirty days'))
        partial=verify(self.corpus,dict(citation='2023 INSC 100',quote='The appellant shall pay 900 rupees within thirty days.'))
        self.assertEqual(exact['quote_match'],'exact')
        self.assertEqual(normalized['quote_match'],'normalized')
        self.assertEqual(partial['quote_match'],'partial')
        self.assertEqual(partial['status'],'inconsistent')

    def test_missing_incomplete_pinpoint_does_not_escalate_found_quote(self):
        row=judgment(); row['paragraph_numbering_complete']=False
        result=verify(Corpus([row]), self.request(pinpoint=999))
        self.assertEqual(result['status'],'review')
        self.assertNotIn('PINPOINT_QUOTE_MISMATCH',self.codes(result))
