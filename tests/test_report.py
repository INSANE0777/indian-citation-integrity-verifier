import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('build_report', Path(__file__).resolve().parents[1] / 'scripts/build_report.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

class ReportTests(unittest.TestCase):
    def test_latex_escape_preserves_plain_text(self):
        self.assertEqual(build.tex('A&B_50%'), r'A\&B\_50\%')

    def test_measurements_come_from_recorded_results(self):
        text = build.measurements()
        self.assertIn(r'\newcommand{\CorpusCount}{385}', text)
        self.assertIn(r'\newcommand{\TestCount}{2,421}', text)
        self.assertIn('0.986', text)
        self.assertNotIn('1110a243fdf4706b3f48f1d95db1a4f5529b4d41', text)
