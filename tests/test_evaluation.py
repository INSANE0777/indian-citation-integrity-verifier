import json
import tempfile
import unittest
from pathlib import Path

from citation_verifier.core import Corpus
from citation_verifier.evaluation import (
    classification_metrics,
    evaluate_cases,
    generate_mutations,
    rank_bm25,
    split_judgment_ids,
)


def row(jid, *, court="Supreme Court of India", bench_size=2, complete=True):
    return {
        "id": jid,
        "case_name": f"Case {jid} v State",
        "court": court,
        "date": "2023-01-01",
        "bench_size": bench_size,
        "citations": [f"2023 INSC {100 + int(jid[1:])}"],
        "source_url": f"https://example.org/{jid}.pdf",
        "paragraph_numbering_complete": complete,
        "paragraphs": [
            {"number": 1, "page": 1, "text": "The appellant shall pay the amount within thirty days."},
            {"number": 2, "page": 1, "text": "The remedy is available. However, the application must be timely."},
            {"number": 3, "page": 2, "text": "The court shall provide notice to the respondent."},
        ],
    }


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.corpus = Corpus([row(f"j{i}") for i in range(10)])

    def test_split_is_seeded_id_disjoint_and_30_70(self):
        first = split_judgment_ids(self.corpus, seed=42)
        second = split_judgment_ids(self.corpus, seed=42)
        self.assertEqual(first, second)
        dev, test = first
        self.assertEqual(len(dev), 3)
        self.assertEqual(len(test), 7)
        self.assertTrue(set(dev).isdisjoint(test))
        self.assertEqual(set(dev) | set(test), {f"j{i}" for i in range(10)})

    def test_mutations_are_controlled_and_labelled(self):
        cases = generate_mutations(self.corpus, judgment_ids=["j0"])
        categories = {case["category"] for case in cases}
        self.assertTrue({
            "clean_quote", "whitespace_quote", "wrong_court", "wrong_bench",
            "quote_corruption", "wrong_pinpoint", "absent_local_citation",
            "selective_quote", "missing_pinpoint",
        } <= categories)
        self.assertTrue(all(case["synthetic"] is True for case in cases))
        self.assertTrue(all(case["request"]["citation"] == "2023 INSC 100" for case in cases if case["category"] != "absent_local_citation"))
        absent = next(c for c in cases if c["category"] == "absent_local_citation")
        self.assertEqual(absent["expected_status"], "unresolved")
        self.assertEqual(absent["evaluation_group"], "triage")
        missing = next(c for c in cases if c["category"] == "missing_pinpoint")
        self.assertEqual(missing["evaluation_group"], "extraction_uncertainty")
        selective = next(c for c in cases if c["category"] == "selective_quote")
        self.assertEqual(selective["evaluation_group"], "human_review")

    def test_metrics_include_multiclass_confusion_and_binary_groups(self):
        expected = ["consistent", "inconsistent", "review", "unresolved"]
        predicted = ["consistent", "review", "review", "unresolved"]
        result = classification_metrics(expected, predicted, labels=expected)
        self.assertEqual(result["count"], 4)
        self.assertEqual(result["accuracy"], 0.75)
        self.assertEqual(result["confusion"]["inconsistent"]["review"], 1)
        self.assertEqual(result["per_class"]["inconsistent"]["recall"], 0.0)
        self.assertIn("human_review", result["grouped"])
        self.assertIn("definite_discrepancy", result["grouped"])

    def test_bm25_ranking_returns_relevant_paragraph_first(self):
        ranked = rank_bm25(
            ["The appellant shall pay the amount within thirty days.", "The court shall provide notice."],
            "appellant pay amount",
        )
        self.assertEqual(ranked[0]["index"], 0)
        self.assertGreater(ranked[0]["score"], ranked[1]["score"])

    def test_evaluate_cases_reports_predictions_retrieval_and_timings(self):
        cases = generate_mutations(self.corpus, judgment_ids=["j0"])
        report = evaluate_cases(self.corpus, cases, baselines=("citation_existence", "literal_quote", "normalized_quote", "full_verifier"))
        self.assertEqual(report["case_count"], len(cases))
        self.assertEqual(set(report["baselines"]), {"citation_existence", "literal_quote", "normalized_quote", "full_verifier"})
        for baseline in report["baselines"].values():
            self.assertIn("accuracy", baseline["metrics"])
            self.assertIn("timings_ms", baseline)
            self.assertIn("evidence_retrieval_recall", baseline)
        self.assertEqual(len(report["cases"]), len(cases))
        self.assertTrue(all("predictions" in case for case in report["cases"]))


if __name__ == "__main__":
    unittest.main()

class EvaluationRegressionTests(unittest.TestCase):
    def test_missing_pinpoint_actually_contains_missing_number(self):
        corpus = Corpus([row('j0', complete=False)])
        case = next(c for c in generate_mutations(corpus, judgment_ids=['j0']) if c['category']=='missing_pinpoint')
        self.assertGreater(case['request']['pinpoint'], 3)
        self.assertIn('quote', case['request'])

    def test_retrieval_recall_excludes_cases_without_gold(self):
        corpus=Corpus([row('j0')])
        cases=generate_mutations(corpus, judgment_ids=['j0'])
        clean=next(c for c in cases if c['category']=='clean_quote')
        absent=next(c for c in cases if c['category']=='absent_local_citation')
        result=evaluate_cases(corpus,[clean,absent],baselines=('full_verifier',))
        self.assertEqual(result['baselines']['full_verifier']['evidence_retrieval_recall'],1.0)

    def test_attention_metric_includes_unresolved(self):
        metric=classification_metrics(['consistent','unresolved'],['consistent','unresolved'])
        self.assertEqual(metric['grouped']['attention']['tp'],1)
        self.assertEqual(metric['grouped']['attention']['accuracy'],1.0)
