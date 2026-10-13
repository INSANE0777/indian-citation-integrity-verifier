# Indian Citation Integrity Verifier Design

**Date:** 2026-10-13

## Goal

Deliver a reproducible Phase 2 mini-project that accepts an Indian case citation and quoted proposition, matches it against a local corpus of Supreme Court judgments, and reports existence, citation-field, paragraph, quotation, and mechanical support checks with evidence.

## Scope

The implementation covers the Phase 1 commitments:

1. Confirm whether the cited judgment exists in the local corpus.
2. Parse common Indian citation forms (neutral, SCC, AIR, SCR, SCALE-style aliases where supplied in metadata).
3. Validate court and bench metadata when present.
4. Validate pinpoint paragraphs when present.
5. Locate the relied-on paragraph by lexical retrieval.
6. Compare the submitted quote with judgment text and flag exact, normalized, partial, or unsupported matches.
7. Flag selective quotation when the supplied quote omits immediately adjacent qualifying language, using a transparent context heuristic.
8. Run a labelled evaluation set containing correct and deliberately altered citations and report accuracy, precision, recall, F1, and confusion counts.

Out of scope: legal advice, ratio/obiter classification, full citator treatment tracking, unbounded web scraping, paid database access, and generative drafting.

## Architecture

A small standard-library Python package provides focused modules:

- `core.py`: corpus validation, canonical citation index, quotation checks and evidence-bearing verification.
- `evaluation.py`: controlled cases, judgment-disjoint splits, metrics and retrieval comparisons.
- `__main__.py` and `web.py`: shared-engine CLI and localhost browser interface.
- `scripts/ingest_corpus.py`: resumable real-data acquisition and provenance.
- `report/`: editable IEEE paper and measured-result inputs.

The CLI is the public demonstration surface. It reads JSON from files or stdin and emits JSON reports, so the same engine can be used by a notebook, web UI, or later API without rewriting the core logic.

## Data Contract

Judgments are JSONL objects with:

- `id`: stable corpus identifier.
- `case_name`: displayed case name.
- `court`: court string.
- `date`: ISO date.
- `bench_size`: integer when known.
- `citations`: list of citation aliases.
- `paragraphs`: list of `{number, text}` objects.

Verification requests are JSON objects with `citation`, optional `court`, optional `bench_size`, optional `pinpoint`, `proposition`, and optional `quote`.

Reports include `status`, `match`, `findings`, `evidence`, and a `limitations` list. Each finding has a stable `code`, severity, human-readable message, and supporting evidence.

## Error Handling and Safety

Malformed corpus rows and requests fail with actionable validation errors and non-zero CLI exit codes. Empty or missing text never receives a false positive. The report explicitly states that a local corpus cannot establish completeness and that automated similarity is not a legal conclusion. Input is treated as data; no downloaded document or generated text is executed.

## Testing and Evaluation

Tests cover citation parsing, normalization, exact/normalized/partial quote matching, paragraph retrieval, court/bench/pinpoint failures, selective-context warnings, and evaluation metrics. The corpus contains real, attributed Supreme Court judgments. Benchmark corruptions are synthetic; their source judgments are not. Optional GPU retrieval is a measured comparison, not an entailment verdict. A localhost browser interface and CLI demonstrate the same core function. The report separates demonstration metrics from claims about production legal accuracy.

## Deliverables

- Source package and CLI.
- Demo corpus and labelled evaluation set.
- Unit tests and a self-check command.
- README with setup, usage, limitations, and viva walkthrough.
- Six-to-seven-page IEEE-style final report source plus generated PDF when the local PDF toolchain permits it.
- GitHub repository containing the complete reproducible project.
