# Demonstrate the real implementation

Run from the repository root after `python -m pip install -e .`.

## CLI

```sh
python -m citation_verifier verify --corpus data/corpus.jsonl --input examples/consistent.json --pretty
python -m citation_verifier verify --corpus data/corpus.jsonl --input examples/wrong-court.json --pretty
python -m citation_verifier verify --corpus data/corpus.jsonl --input examples/altered-quote.json --pretty
python -m citation_verifier verify --corpus data/corpus.jsonl --input examples/missing-pinpoint.json --pretty
python -m citation_verifier verify --corpus data/corpus.jsonl --input examples/unresolved.json --pretty
python -m citation_verifier verify --corpus data/corpus.jsonl --input examples/request.json --pretty
```

Expected states in order: `consistent`, `inconsistent`, `inconsistent`, `review`, `unresolved`, `review`. The final request adds a proposition to a matching quotation and therefore still requires legal review. Saved demonstration outputs are in `results/demo.json`; regenerate by running the commands above. No source judgment was invented for these examples. Inputs with deliberate discrepancies are demonstration mutations.

## Browser

```sh
python -m citation_verifier serve --corpus data/corpus.jsonl --host 127.0.0.1 --port 8765
```

Open <http://127.0.0.1:8765/>. Enter:

- Citation: `[2022] 1 S.C.R. 473`
- Court: `Supreme Court of India`
- Bench size: `2`
- Pinpoint: `1`
- Quote: `Leave granted.`
- Proposition: leave empty for this first check.

Submit and inspect the verified paragraph, original PDF page and source link. Change the quote to `Leave refused.` and resubmit: quotation/pinpoint discrepancies appear. Restore the quote and enter a proposition to see why matching text does not establish its meaning. Change the citation to `2099 INSC 999999` for an unresolved result, not a claim that the case is fabricated. Clear both quote and proposition to exercise client-side validation, then restore the quote to recover.

The source judgment is *Rajendra Bhagat v. State of Jharkhand & Anr.*, 2022 INSC 6. The short paragraph is suitable for a simple demonstration, not evidence about the merits of a legal proposition. For the more substantial benchmark passages see `results/evaluation_test.jsonl`.

## Context and retrieval

Use `examples/selective-quote.json` to demonstrate a cue-based review warning, and inspect `examples/wrong-pinpoint.json` to distinguish a matching quote at one paragraph from a requested different paragraph. These examples are generated from retained source text. Context cues are a heuristic, not a finding of deliberate misrepresentation.

## Evidence to show in the viva

- `data/manifest.json`: 1,873 selected keys, 385 retained, 1,488 logged failures.
- `data/DATA_CARD.md`: source license and extraction limitations.
- `results/evaluation.json`: per-case predictions and confusion metrics.
- `results/retrieval.json`: BM25 grid, actual GPU model revision and ranks.
- `report/Final_Report.pdf`: seven-page IEEE report.
- `docs/VIVA_GUIDE.md`: interpretation and limitations.

The application is local and uses no remote inference service. Do not expose the standard-library demonstration server publicly. The server is not a production hosting deployment.
