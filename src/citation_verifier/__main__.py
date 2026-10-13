"""Command-line entry point for the local citation verifier."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TextIO


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def _parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(prog="citation-verifier")
    commands = parser.add_subparsers(dest="command", required=True)

    verify = commands.add_parser("verify", help="verify a citation request")
    verify.add_argument("--corpus", required=True, help="path to the local JSONL corpus")
    verify.add_argument("--input", help="request JSON file; reads stdin when omitted")
    verify.add_argument("--pretty", action="store_true", help="indent the JSON result")

    serve = commands.add_parser("serve", help="serve the local browser interface")
    serve.add_argument("--corpus", required=True, help="path to the local JSONL corpus")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    return parser


def _emit_error(message: str, stderr: TextIO) -> None:
    print(json.dumps({"error": message}, ensure_ascii=True), file=stderr)


def _friendly_error(exc: BaseException) -> str:
    if isinstance(exc, FileNotFoundError):
        return f"corpus or input file not found: {exc.filename}"
    if isinstance(exc, PermissionError):
        return f"cannot read corpus or input file: {exc.filename}"
    return str(exc)


def _verify(args: argparse.Namespace, stdin: TextIO) -> int:
    try:
        from .core import Corpus, verify

        corpus = Corpus.load(args.corpus)
        raw_request = Path(args.input).read_text(encoding="utf-8") if args.input else stdin.read()
        request = json.loads(raw_request)
        result = verify(corpus, request)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, ImportError) as exc:
        _emit_error(_friendly_error(exc), sys.stderr)
        return 2
    except Exception as exc:
        _emit_error(f"verification failed: {exc}", sys.stderr)
        return 2

    print(json.dumps(result, indent=2 if args.pretty else None, ensure_ascii=True))
    return 0


def _serve(args: argparse.Namespace) -> int:
    try:
        from .web import create_server

        server = create_server(args.corpus, host=args.host, port=args.port)
    except (OSError, ValueError, ImportError) as exc:
        _emit_error(str(exc), sys.stderr)
        return 2
    try:
        print(f"Serving citation verifier at http://{args.host}:{server.server_address[1]}/")
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        _emit_error(f"server failed: {exc}", sys.stderr)
        return 2
    finally:
        server.server_close()
    return 0


def main(argv: list[str] | None = None, stdin: TextIO | None = None) -> int:
    """Run the CLI and return its process exit code."""
    try:
        args = _parser().parse_args(argv)
    except (ValueError, SystemExit) as exc:
        # argparse uses SystemExit for --help; preserve that successful behavior.
        if isinstance(exc, SystemExit):
            if exc.code == 0:
                return 0
            _emit_error("invalid command-line arguments", sys.stderr)
        else:
            _emit_error(str(exc), sys.stderr)
        return 2
    if args.command == "verify":
        return _verify(args, stdin if stdin is not None else sys.stdin)
    return _serve(args)


if __name__ == "__main__":
    raise SystemExit(main())
