"""Small, dependency-free HTTP interface for citation verification."""
from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

_MAX_BODY = 256 * 1024
_MAX_EVIDENCE_TEXT = 12_000


class _Handler(BaseHTTPRequestHandler):
    server_version = "CitationVerifier/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        return

    @property
    def app(self) -> "_Application":
        return self.server.app  # type: ignore[attr-defined]

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path != "/":
            self._send(HTTPStatus.NOT_FOUND, "application/json; charset=utf-8", b'{"error":"not found"}')
            return
        self._send(HTTPStatus.OK, "text/html; charset=utf-8", self.app.page)

    def do_POST(self) -> None:
        if self.path != "/verify":
            self._send(HTTPStatus.NOT_FOUND, "application/json; charset=utf-8", b'{"error":"not found"}')
            return
        length_header = self.headers.get("Content-Length")
        try:
            length = int(length_header) if length_header is not None else -1
        except ValueError:
            length = -1
        if length < 0 or length > _MAX_BODY:
            self._json_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "request body must be at most 256 KB")
            return
        try:
            request = json.loads(self.rfile.read(length))
            report = self.app.verify(request)
            report = _limit_evidence(report)
        except json.JSONDecodeError as exc:
            self._json_error(HTTPStatus.BAD_REQUEST, f"invalid JSON: {exc.msg}")
            return
        except ValueError as exc:
            self._json_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except OSError as exc:
            self._json_error(HTTPStatus.SERVICE_UNAVAILABLE, str(exc))
            return
        self._send_json(HTTPStatus.OK, report)

    def _json_error(self, status: int, message: str) -> None:
        self._send_json(status, {"error": message})

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        self._send(status, "application/json; charset=utf-8", json.dumps(payload, ensure_ascii=False).encode("utf-8"))


def _limit_evidence(report: dict[str, Any]) -> dict[str, Any]:
    limited = dict(report)
    evidence = []
    for item in report.get("evidence", []):
        item = dict(item)
        if isinstance(item.get("text"), str):
            item["text"] = item["text"][:_MAX_EVIDENCE_TEXT]
        evidence.append(item)
    limited["evidence"] = evidence
    return limited


class _Application:
    def __init__(self, corpus_path: str | Path, page: bytes):
        self.corpus_path = Path(corpus_path)
        self.page = page
        self._corpus = None
        self._load_error = None
        try:
            from .core import Corpus

            self._corpus = Corpus.load(self.corpus_path)
        except (OSError, UnicodeError, ValueError, ImportError) as exc:
            self._load_error = str(exc)

    def verify(self, request: Any) -> dict[str, Any]:
        if self._corpus is None:
            raise OSError(f"local corpus unavailable: {self._load_error}")
        try:
            from .core import verify

            return verify(self._corpus, request)
        except ImportError as exc:
            raise OSError(f"citation verifier core unavailable: {exc}") from exc


def _page(corpus_path: str | Path) -> bytes:
    template = Path(__file__).with_name("web.html").read_text(encoding="utf-8")
    try:
        from .core import Corpus

        Corpus.load(corpus_path)
        message = ""
    except (OSError, UnicodeError, ValueError, ImportError) as exc:
        message = f"<p class=\"notice\" role=\"status\">Local corpus unavailable: {_escape(str(exc))}</p>"
    return template.replace("<!-- CORPUS_STATUS -->", message).encode("utf-8")


def _escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def create_server(corpus_path: str | Path, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    """Create a server without starting its serving loop."""
    app = _Application(corpus_path, _page(corpus_path))

    class Server(ThreadingHTTPServer):
        allow_reuse_address = True

    server = Server((host, port), _Handler)
    server.app = app  # type: ignore[attr-defined]
    return server
