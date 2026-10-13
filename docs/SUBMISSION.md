# Phase 2 submission checklist

## Deliverables

- Final report: [`report/Final_Report.pdf`](../report/Final_Report.pdf), seven IEEE-style pages.
- Editable source and rebuild instructions: [`report/main.tex`](../report/main.tex), [`report/BUILD.md`](../report/BUILD.md).
- Complete implementation: [`src/citation_verifier/`](../src/citation_verifier/) and [`scripts/`](../scripts/).
- Real attributed data: [`data/corpus.jsonl`](../data/corpus.jsonl), [`data/manifest.json`](../data/manifest.json), [`data/DATA_CARD.md`](../data/DATA_CARD.md).
- Actual CPU/GPU experiments and predictions: [`results/`](../results/), [`docs/EVALUATION.md`](EVALUATION.md).
- Demonstration and viva preparation: [`docs/DEMO.md`](DEMO.md), [`docs/VIVA_GUIDE.md`](VIVA_GUIDE.md).
- Private repository: https://github.com/INSANE0777/indian-citation-integrity-verifier

## Rubric mapping

| Requirement | Delivered evidence |
|---|---|
| Clear measurable objectives | Report I.A; identity/metadata/quote/pinpoint checks, retrieval comparison and uncertainty reporting |
| Justified methodology | Report III; deterministic rules for exact mechanical claims, BM25 versus optional dense retrieval |
| All committed modules implemented | Core, corpus collector, evaluation, CLI and local browser; examples cover successful, inconsistent, review and unresolved cases |
| Dataset source, size, preprocessing and ethics | Data card, source hashes, failure manifest, Report III.B and IV.A |
| Quantitative metrics and fair baselines | Identical 2,421 held-out controlled requests; confusion counts, accuracy/precision/recall/F1 and per-category results |
| Parameter tuning | Six BM25 settings on development only; inference batch comparison on development paragraphs |
| Hardware/software and training settings | `results/run_manifest.json`, `results/hardware.json`; no training, optimizer/epochs/learning rate not applicable |
| Limitations and conclusions | Report V and evaluation notes; no legal entailment, completeness or natural-error accuracy claim |
| Demonstration and individual understanding | CLI/browser examples and viva guide; each person must understand the full implementation |
| Report format and references | Seven pages, two-column IEEE layout, 150–250-word abstract, 19 scholarly references plus dataset source |

## Checks performed

- Full `python -m pytest tests -q`: 66 tests and 16 subtests passed.
- `python scripts/build_report.py`: built and checked a seven-page PDF, with no overfull boxes or undefined references. Non-fatal fontconfig and bibliography spacing warnings remain in the local build log.
- Every PDF page rendered and inspected; no clipped/out-of-page text or replacement glyphs.
- All eight CLI examples executed; expected states saved in `results/demo.json`.
- Browser: actual form submission, altered quote, recovery, desktop and 390px mobile widths; no JavaScript errors or horizontal overflow.
- GPU: actual CUDA MiniLM inference, pinned model revision, measured indexing/ranking and batch timings.
- Corpus/experiment source hashes checked by the report builder.

## Human-only items before submission

1. Add the faculty-assigned Team ID to the author block if one has now been assigned. The supplied Phase 1 PDF explicitly said it was not yet assigned; no ID was invented.
2. Record truthful individual contributions if the faculty requests them. No contribution history or signatures were fabricated.
3. Review the report/code, verify academic disclosure requirements for AI assistance, and be prepared to explain the entire system. No similarity/AI-detector outcome or grade is promised.
4. Give the evaluator access to the private GitHub repository. A private URL alone does not grant access; no reviewer was invited without your instruction.
5. Upload the final report and repository link to the required institutional portal. This session does not have portal access and has not submitted or backdated anything. The stated deadline was 10 October 2026; the actual implementation/results were produced on 13 October 2026.

## Known scope limits

Only 385 of 1,873 selected public records met the conservative extraction rules. That is documented rather than presented as the original 2,000 target. The resulting 62/323 year split is biased by extraction success. All completeness indicators remain false. Synthetic benchmark success does not establish natural legal-error performance, legal meaning, ratio/obiter, speaker attribution or continuing precedent. The local Python server is a demonstration, not a public production deployment.

## GitHub delivery verification

The repository was created private and its default branch is `phase-2`. The initial delivery commit `8e311b98889dddab911330aa4c42b790a1579efe` was read back through `git ls-remote` and matched the local commit. The uploaded PDF blob was separately read back and matched `git hash-object report/Final_Report.pdf`. A clean export of the exact committed package, without download/model caches, passed all 66 tests and 16 subtests, generated the report tables with matching corpus/code hashes, and ran the real consistent CLI example. No institutional portal submission was performed.
