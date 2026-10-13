import os
import subprocess
import sys
import io
import json
import tempfile
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from http.client import HTTPConnection
from pathlib import Path
from urllib.parse import urlsplit

from citation_verifier.__main__ import main
from citation_verifier.web import create_server


def judgment_row():
    return {
        "id": "example-1",
        "case_name": "Example v State",
        "court": "Supreme Court of India",
        "date": "2023-01-01",
        "bench_size": 2,
        "citations": ["2023 INSC 100"],
        "source_url": "https://example.org/judgment.pdf",
        "paragraph_numbering_complete": True,
        "paragraphs": [
            {"number": 1, "page": 1, "text": "The appellant shall pay 100 rupees."}
        ],
    }


class PublicInterfaceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.corpus = self.root / "corpus.jsonl"
        self.corpus.write_text(json.dumps(judgment_row()) + "\n", encoding="utf-8")
        self.request = self.root / "request.json"
        self.request.write_text(
            json.dumps({"citation": "2023 INSC 100", "quote": "The appellant shall pay 100 rupees."}),
            encoding="utf-8",
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def run_cli(self, args, stdin=""):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(args, stdin=io.StringIO(stdin))
        return code, stdout.getvalue(), stderr.getvalue()

    def test_cli_valid_request(self):
        code, stdout, stderr = self.run_cli(
            ["verify", "--corpus", str(self.corpus), "--input", str(self.request)]
        )
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(json.loads(stdout)["status"], "consistent")

    def test_cli_reads_stdin(self):
        code, stdout, stderr = self.run_cli(
            ["verify", "--corpus", str(self.corpus)], self.request.read_text(encoding="utf-8")
        )
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(json.loads(stdout)["status"], "consistent")

    def test_cli_malformed_input_is_json_error(self):
        bad = self.root / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        code, stdout, stderr = self.run_cli(
            ["verify", "--corpus", str(self.corpus), "--input", str(bad)]
        )
        self.assertNotEqual(code, 0)
        self.assertEqual(stdout, "")
        self.assertIn("error", json.loads(stderr))

    def test_cli_missing_corpus_is_json_error(self):
        code, stdout, stderr = self.run_cli(
            ["verify", "--corpus", str(self.root / "missing.jsonl"), "--input", str(self.request)]
        )
        self.assertNotEqual(code, 0)
        self.assertEqual(stdout, "")
        self.assertIn("not found", json.loads(stderr)["error"].lower())

    def test_http_get_and_post_smoke(self):
        server = create_server(self.corpus, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            connection = HTTPConnection(host, port)
            connection.request("GET", "/")
            response = connection.getresponse()
            page = response.read().decode("utf-8")
            self.assertEqual(response.status, 200)
            self.assertIn("Citation Verifier", page)
            connection.close()

            connection = HTTPConnection(host, port)
            connection.request("POST", "/verify", self.request.read_text(encoding="utf-8"), {"Content-Type": "application/json"})
            response = connection.getresponse()
            report = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertEqual(report["status"], "consistent")
            connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_http_missing_corpus_has_clear_message(self):
        server = create_server(self.root / "missing.jsonl", port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            connection = HTTPConnection(host, port)
            connection.request("GET", "/")
            response = connection.getresponse()
            page = response.read().decode("utf-8")
            self.assertEqual(response.status, 200)
            self.assertIn("Local corpus unavailable", page)
            connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()

class CliEncodingTests(unittest.TestCase):
    def test_json_output_survives_ascii_terminal_encoding(self):
        with tempfile.TemporaryDirectory() as folder:
            corpus = Path(folder) / 'corpus.jsonl'
            request = Path(folder) / 'request.json'
            record = judgment_row()
            record['case_name'] = 'Court — example'
            corpus.write_text(json.dumps(record) + '\n', encoding='utf8')
            request.write_text(json.dumps({"citation":"2023 INSC 100","quote":"The appellant shall pay 100 rupees."}), encoding='utf8')
            env = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1] / "src"), 'PYTHONIOENCODING': 'ascii'}
            result = subprocess.run([sys.executable, '-m', 'citation_verifier', 'verify', '--corpus', str(corpus), '--input', str(request)], capture_output=True, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['match']['case_name'], record['case_name'])
