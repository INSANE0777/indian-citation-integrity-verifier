import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('runner', Path(__file__).resolve().parents[1]/'scripts/run_experiments.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

class RunnerTests(unittest.TestCase):
    def test_retrieval_queries_are_bounded_and_from_source(self):
        row={'id':'one','paragraphs':[{'number':8,'text':' '.join('word'+str(n) for n in range(80))}]}
        qs=runner.retrieval_queries([row])
        self.assertEqual(len(qs),1)
        self.assertEqual(qs[0]['gold_paragraph'],8)
        self.assertLess(len(qs[0]['query'].split()),48)
        self.assertTrue(set(qs[0]['query'].split()) <= set(row['paragraphs'][0]['text'].split()))
    def test_rank_summary_and_gold(self):
        summary=runner.rank_summary([{'rank':1},{'rank':3},{'rank':6}])
        self.assertAlmostEqual(summary['recall_at_1'],1/3)
        self.assertAlmostEqual(summary['recall_at_5'],2/3)
        self.assertAlmostEqual(summary['mrr'],(1+1/3+1/6)/3)
