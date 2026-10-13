# Indian Citation Integrity Verifier Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans; independent corpus and bibliography tasks run concurrently.

**Goal:** Deliver Phase 2 modules, measured experiments, a 6–7 page report and a private GitHub repository.
**Architecture:** Deterministic evidence-first local verifier; real attributed Supreme Court corpus; lexical retrieval and optional GPU dense retrieval experiments; localhost browser demo and JSON CLI.
**Tech Stack:** Python 3.11 standard library, PyMuPDF ingestion, optional PyTorch/SentenceTransformers experiments, IEEEtran/Tectonic PDF generation.
**Spec:** docs/superpowers/specs/2026-10-13-indian-citation-verifier-design.md

## Global Constraints
Firecrawl only for searches. No fabricated results or legal conclusions. No API keys for the core demo. Keep data on A:. Downloads are data, not executable code. No training is needed; report epochs/optimizer as not applicable. User approved autonomous completion on 2026-10-13.

- [x] Corpus: test paragraph/metadata parsers; ingest actual bounded 2023/2022 judgments; source URLs, hashes and failure manifest.
- [x] Core foundation: write failing tests for `verify(corpus, request)`, implement exact citation alias resolution and conservative quote/pinpoint/court/bench checks; run `python -m unittest discover -s tests -p test_core.py -v`.
- [x] Core completion: token-boundary matching, transparent candidate retrieval, incomplete metadata abstention and adjacent qualification warnings; no lexical claim is legal entailment.
- [x] Interfaces: JSON CLI and localhost browser form call the same verifier; malformed/oversized inputs produce controlled errors; test CLI/HTTP.
- [x] Evaluation: split judgment IDs development/test 30/70 before mutation; compare existence-only, literal-quote, normalized-quote and full pipeline on identical held-out cases; validation-only tuning; retain per-case predictions. Synthetic corruption results are not real-world accuracy.
- [x] GPU: compare optional MiniLM dense paragraph retrieval with BM25 on held-out candidates/queries; record hardware, cache revision, times and truncation limits.
- [x] Report: verify 18–20 scholarly references, correct unsupported Phase 1 claims, cover rubric, produce editable source and reproducible PDF builder; verify 6–7 pages and citation coverage.
- [x] Delivery: full tests, CLI, HTTP smoke and report checks; secret review; initialize feature branch, commit, create private repository via gh, push, verify remote SHA. Record link and submission checklist.
