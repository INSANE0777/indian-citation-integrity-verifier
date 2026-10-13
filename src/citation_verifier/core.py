"""Evidence-first citation checks for a bounded local judgment corpus."""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import date
from urllib.parse import urlparse
from pathlib import Path
from typing import Any, Iterable

_MAX_TEXT = 20_000
_WORD = re.compile(r"[a-z0-9]+(?:['-][a-z0-9]+)?", re.I)
_QUALIFIERS = re.compile(r"^(?:however|but|provided that|subject to|unless|except|only|save that)\b", re.I)


def canonical_citation(value: str) -> str:
    """Canonicalize punctuation and reporter abbreviations without fuzzy matching."""
    if not isinstance(value, str) or not value.strip() or len(value) > 1000:
        raise ValueError("citation must be a non-empty string of at most 1000 characters")
    text = value.upper().replace("–", "-").replace("—", "-")
    text = re.sub(r"S\s*\.\s*C\s*\.\s*R\s*\.?", "SCR", text)
    text = re.sub(r"S\s*\.\s*C\s*\.\s*C\s*\.?", "SCC", text)
    text = re.sub(r"S\s*\.\s*C\s*\.?", "SC", text)
    text = re.sub(r"A\s*\.\s*I\s*\.\s*R\s*\.?", "AIR", text)
    text = re.sub(r"\bINSC\b", "INSC", text)
    text = re.sub(r"[\[\](){}.,;:]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^(\d{4})\s*INSC\s*(\d+)$", r"\1 INSC \2", text)
    return text


def normalized_text(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("text must be a string")
    value = unicodedata.normalize("NFKC", value).replace("’", "'").replace("‘", "'")
    return " ".join(_WORD.findall(value.casefold()))


def _validate_paragraph(row: Any, where: str) -> dict[str, Any]:
    if not isinstance(row, dict) or not isinstance(row.get("number"), int) or isinstance(row.get("number"), bool):
        raise ValueError(f"{where}: paragraph number must be an integer")
    if row["number"] < 1 or not isinstance(row.get("text"), str) or not row["text"].strip():
        raise ValueError(f"{where}: paragraph number/text invalid")
    out = {"number": row["number"], "text": row["text"].strip()}
    if row.get("page") is not None:
        if not isinstance(row["page"], int) or row["page"] < 1:
            raise ValueError(f"{where}: page must be a positive integer")
        out["page"] = row["page"]
    return out


class Corpus:
    def __init__(self, rows: Iterable[dict[str, Any]]):
        self.rows = []
        self.by_citation: dict[str, list[dict[str, Any]]] = {}
        ids: set[str] = set()
        for index, row in enumerate(rows, 1):
            if not isinstance(row, dict):
                raise ValueError(f"row {index}: expected object")
            for field in ("id", "case_name", "court", "date", "source_url", "paragraphs"):
                if not row.get(field):
                    raise ValueError(f"row {index}: missing {field}")
            for field in ("id", "case_name", "court", "date", "source_url"):
                if not isinstance(row[field], str) or not row[field].strip():
                    raise ValueError(f"row {index}: {field} must be a non-empty string")
            if not isinstance(row["paragraphs"], list):
                raise ValueError(f"row {index}: paragraphs must be a list")
            try:
                date.fromisoformat(row["date"])
            except ValueError as exc:
                raise ValueError(f"row {index}: date must be ISO YYYY-MM-DD") from exc
            url = urlparse(row["source_url"])
            if url.scheme not in {"http", "https"} or not url.netloc:
                raise ValueError(f"row {index}: source_url must be an HTTP(S) URL")
            bench = row.get("bench_size")
            if bench is not None and (type(bench) is not int or bench < 1):
                raise ValueError(f"row {index}: bench_size must be a positive integer or null")
            if type(row.get("paragraph_numbering_complete", False)) is not bool:
                raise ValueError(f"row {index}: paragraph_numbering_complete must be boolean")
            if row["id"] in ids:
                raise ValueError(f"row {index}: duplicate id {row['id']}")
            ids.add(row["id"])
            paragraphs = [_validate_paragraph(p, f"row {index}") for p in row["paragraphs"]]
            if len(paragraphs) > 100000:
                raise ValueError(f"row {index}: too many paragraphs")
            numbers = [p["number"] for p in paragraphs]
            if not paragraphs or len(numbers) != len(set(numbers)):
                raise ValueError(f"row {index}: paragraphs must be non-empty and uniquely numbered")
            citations = row.get("citations") or []
            if not isinstance(citations, list) or not all(isinstance(c, str) and c.strip() for c in citations):
                raise ValueError(f"row {index}: citations must be a list of strings")
            clean = dict(row)
            clean["paragraphs"] = paragraphs
            clean["citations"] = citations
            if "sha256" in clean and (not isinstance(clean["sha256"], str) or not re.fullmatch(r"[0-9a-fA-F]{64}", clean["sha256"])):
                raise ValueError(f"row {index}: sha256 must be a 64-character hexadecimal string")
            self.rows.append(clean)
            for key in {canonical_citation(citation) for citation in citations}:
                self.by_citation.setdefault(key, []).append(clean)

    @classmethod
    def load(cls, path: str | Path) -> "Corpus":
        rows, lines = [], []
        with open(path, encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    rows.append(json.loads(line))
                    lines.append(line_number)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"line {line_number}: invalid JSON ({exc.msg})") from exc
        try:
            return cls(rows)
        except ValueError as exc:
            message = re.sub(r"row (\d+)", lambda m: f"line {lines[int(m[1])-1]}", str(exc))
            raise ValueError(message) from exc

    def resolve(self, citation: str) -> list[dict[str, Any]]:
        return list(self.by_citation.get(canonical_citation(citation), []))


def _finding(code: str, severity: str, message: str, **evidence: Any) -> dict[str, Any]:
    result = {"code": code, "severity": severity, "message": message}
    if evidence:
        result["evidence"] = evidence
    return result


def _paragraph_evidence(row: dict[str, Any], paragraph: dict[str, Any], match_type: str = "verified") -> dict[str, Any]:
    return {"number": paragraph["number"], "page": paragraph.get("page"), "text": paragraph["text"], "source_url": row["source_url"], "match_type": match_type}


def _retrieve(row: dict[str, Any], query: str) -> list[tuple[float, dict[str, Any]]]:
    wanted = set(normalized_text(query).split())
    scored = []
    for p in row["paragraphs"]:
        words = set(normalized_text(p["text"]).split())
        score = len(wanted & words) / max(1, len(wanted))
        scored.append((score, p))
    return sorted(scored, key=lambda x: (-x[0], x[1]["number"]))


def _validate_request(request: Any) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise ValueError("request must be an object")
    citation = request.get("citation")
    if not isinstance(citation, str) or not citation.strip() or len(citation) > 1000:
        raise ValueError("request.citation must be a non-empty string of at most 1000 characters")
    unknown = set(request) - {"citation", "quote", "proposition", "court", "bench_size", "pinpoint"}
    if unknown:
        raise ValueError("unknown request field(s): " + ", ".join(sorted(unknown)))
    quote = request.get("quote")
    proposition = request.get("proposition")
    if quote is not None and not normalized_text(quote):
        raise ValueError("request.quote must contain at least one alphanumeric token")
    if proposition is not None and not normalized_text(proposition):
        raise ValueError("request.proposition must contain at least one alphanumeric token")
    if quote is None and proposition is None:
        raise ValueError("request requires quote or proposition")
    for name, value in (("quote", quote), ("proposition", proposition), ("court", request.get("court"))):
        if value is not None and (not isinstance(value, str) or not value.strip() or len(value) > _MAX_TEXT):
            raise ValueError(f"request.{name} must be a non-empty string of at most {_MAX_TEXT} characters")
    for name in ("pinpoint", "bench_size"):
        value = request.get(name)
        if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 1):
            raise ValueError(f"request.{name} must be a positive integer")
    return dict(request)


def verify(corpus: Corpus, request: dict[str, Any]) -> dict[str, Any]:
    request = _validate_request(request)
    findings: list[dict[str, Any]] = []
    matches = corpus.resolve(request["citation"])
    if not matches:
        findings.append(_finding("NOT_IN_CORPUS", "warning", "The citation was not found in this local corpus; this does not establish that the case is fabricated."))
        return {"status": "unresolved", "match": None, "findings": findings, "evidence": [], "limitations": ["The bounded local corpus is not a completeness oracle."]}
    if len(matches) > 1:
        findings.append(_finding("AMBIGUOUS_CITATION", "warning", "The citation resolves to more than one corpus record; verification abstains."))
        return {"status": "unresolved", "match": None, "findings": findings, "evidence": [], "limitations": ["Duplicate aliases require source-level disambiguation."]}
    row = matches[0]
    match = {k: row[k] for k in ("id", "case_name", "court", "date", "bench_size", "citations", "source_url", "metadata_url", "sha256", "paragraph_numbering_complete") if k in row}
    court_aliases = {"sc": "supreme court of india", "sci": "supreme court of india", "supreme court": "supreme court of india"}
    requested_court = " ".join((request.get("court") or "").casefold().split())
    if requested_court and court_aliases.get(requested_court, requested_court) != row["court"].casefold():
        findings.append(_finding("COURT_MISMATCH", "error", "The requested court does not match corpus metadata.", requested=request["court"], observed=row["court"]))
    if request.get("bench_size") is not None and row.get("bench_size") is None:
        findings.append(_finding("BENCH_UNRESOLVED", "warning", "The corpus has no bench-size metadata for this judgment."))
    elif request.get("bench_size") is not None and request["bench_size"] != row.get("bench_size"):
        findings.append(_finding("BENCH_MISMATCH", "error", "The requested bench size does not match corpus metadata.", requested=request["bench_size"], observed=row["bench_size"]))
    evidence: list[dict[str, Any]] = []
    quote = request.get("quote")
    quote_match = "not_requested" if not quote else "unsupported"
    if request.get("pinpoint") is not None:
        target = next((p for p in row["paragraphs"] if p["number"] == request["pinpoint"]), None)
        if target is None:
            code = "PINPOINT_UNRESOLVED" if not row.get("paragraph_numbering_complete", False) else "PINPOINT_NOT_FOUND"
            findings.append(_finding(code, "warning", "The pinpoint paragraph could not be verified from this extraction.", requested=request["pinpoint"]))
        elif quote and f" {normalized_text(quote)} " not in f" {normalized_text(target['text'])} ":
            findings.append(_finding("PINPOINT_QUOTE_MISMATCH", "error", "The quote is not present in the requested pinpoint paragraph.", pinpoint=request["pinpoint"]))
    if quote:
        needle = normalized_text(quote)
        for p in row["paragraphs"]:
            if needle and f" {needle} " in f" {normalized_text(p['text'])} ":
                evidence.append(_paragraph_evidence(row, p))
                if quote in p["text"]:
                    quote_match = "exact"
                elif quote_match != "exact":
                    quote_match = "normalized"
        if not evidence:
            ranked = _retrieve(row, quote)
            if ranked and ranked[0][0] >= 0.3:
                evidence.append(_paragraph_evidence(row, ranked[0][1], "candidate"))
                quote_match = "partial"
            findings.append(_finding("QUOTE_MISMATCH", "error", "The supplied quote was not found as a normalized contiguous passage in this judgment."))
        elif len(needle.split()) >= 4 and len(evidence) == 1:
            p = next(p for p in row["paragraphs"] if p["number"] == evidence[0]["number"])
            exact = p["text"].casefold().find(quote.strip().casefold())
            suffix = p["text"][exact + len(quote.strip()):] if exact >= 0 else ""
            if exact < 0:
                normalized = normalized_text(p["text"])
                suffix = normalized[normalized.find(needle) + len(needle):]
            if _QUALIFIERS.search(suffix.strip()):
                findings.append(_finding("CONTEXT_REVIEW", "warning", "The quote is followed by qualifying language; inspect the full paragraph before relying on it."))
            next_p = next((q for q in row["paragraphs"] if q["number"] == p["number"] + 1), None)
            if next_p and _QUALIFIERS.match(next_p["text"].strip()):
                evidence.append(_paragraph_evidence(row, next_p, "context"))
                findings.append(_finding("CONTEXT_REVIEW", "warning", "The next paragraph begins with qualifying language; inspect adjacent context before relying on the quote."))
    elif request.get("proposition"):
        ranked = _retrieve(row, request["proposition"])
        if ranked and ranked[0][0] > 0:
            evidence.append(_paragraph_evidence(row, ranked[0][1], "retrieved"))
        findings.append(_finding("PROPOSITION_REVIEW", "warning", "The proposition was retrieved lexically; this tool does not determine legal entailment."))
    if request.get("proposition") and quote:
        findings.append(_finding("PROPOSITION_REVIEW", "warning", "A matching quote does not establish that the separately supplied proposition is supported; legal review is required."))
    status = "inconsistent" if any(f["severity"] == "error" for f in findings) else "review" if findings else "consistent"
    return {"status": status, "quote_match": quote_match, "match": match, "findings": findings, "evidence": evidence[:5], "limitations": ["Text overlap is not a determination of legal meaning or binding force."]}
