# Supreme Court of India Judgments Corpus

## Description
A reproducible extraction of English Supreme Court of India judgment PDFs and registry metadata for a deterministic selection of 2022–2023 records. Paragraphs are retained only when the PDF contains explicit numbered judgment paragraphs after a `JUDGMENT` or `ORDER` heading; the parser attempts to exclude frontmatter and headnotes. This is not an expert-verified guarantee for every unusual layout. `paragraph_numbering_complete` is always false: extraction does not verify the true final judgment paragraph against the PDF.

## Source and attribution
Source: [Indian Supreme Court Judgments](https://registry.opendata.aws/indian-supreme-court-judgments/), downloaded from the public S3 bucket [`indian-supreme-court-judgments`](https://indian-supreme-court-judgments.s3.ap-south-1.amazonaws.com/). Cite as: Vanga (2025), *Indian Supreme Court Judgments* [Data set], AWS Open Data Registry. The source is licensed under Creative Commons Attribution 4.0 International (CC BY 4.0); attribution is retained in `manifest.json`.

## Schema
`data/corpus.jsonl` contains one JSON object per case: stable `id`, `case_name`, `court`, ISO `date`, `bench_size` (or null), source-present `citations`, `paragraphs` (`number`, `text`, one-based PDF `page`), source PDF URL, metadata JSON URL, SHA-256 of the source PDF, and `paragraph_numbering_complete`. SCC/AIR citations are not generated unless supplied by the source metadata.

## Collection
Run `python scripts/ingest_corpus.py --limit 2000 --years 2023 2022 --workers 8`. Downloads are cached under `.cache/raw` and can be resumed. `data/manifest.json` records retrieval time, request totals, failures, attribution, license, and selection policy. Failed or ambiguous documents are listed in the manifest rather than silently represented as successful records.

## Intended use and limitations
Research and reproducibility only, not legal advice. This is a sample, not a complete case-law collection. The extraction preserves explicitly numbered paragraphs but may omit judgments whose PDF layout obscures paragraph structure; consult the source PDF for authoritative text. Some PDFs contain editorial summaries and parallel opinions, and automated extraction may not identify every unusual layout. Citation aliases are limited to aliases explicitly exposed in the registry metadata.

## Transformations and license
PDF text and metadata were converted to JSONL, whitespace was normalized, numbered fragments retained, and ambiguous material omitted. No paragraphs were renumbered. The extracted corpus retains the source CC-BY-4.0 license: https://creativecommons.org/licenses/by/4.0/. Source licensing does not license project code. Data may contain personal information in public judicial records; use only for the stated research purpose.
