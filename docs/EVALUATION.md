# Evaluation protocol and recorded results

## Reproduce

Core verification has no third-party runtime dependency. Acquisition, testing, PDF checking and GPU retrieval have optional dependency groups:

```sh
python -m pip install -e ".[test,ingest,report,gpu]"
python -m pytest tests -q
python scripts/run_experiments.py --corpus data/corpus.jsonl --out results --model-revision 1110a243fdf4706b3f48f1d95db1a4f5529b4d41
python scripts/build_report.py
```

A CUDA-enabled PyTorch build is required for the GPU run; use PyTorch's installer appropriate to your platform. `--skip-gpu` permits an explicitly labelled CPU-only run. Use a different `--out` directory to preserve the submitted measurements. Model files are cached under the project's `.cache/huggingface/`. The initial model download uses Hugging Face, not a model inference API. `trust_remote_code=False` and safetensors are required by the runner.

`results/run_manifest.json` records source/code hashes, corpus identity, environment, packages, seed and timestamps. `results/hardware.json` records CPU/RAM queried through Windows CIM and GPU memory/driver from `nvidia-smi`. Inference timings are single-run observations and vary by machine. The report builder rejects changed experiment code/corpus; regenerate results before rebuilding a changed method.

## Dataset and partition

- 1,873 selected registry keys from 2022–2023, under a requested cap of 2,000.
- 385 retained judgments, 13,456 extracted numbered fragments; 1,488 logged failures.
- All automatic completeness indicators are false. The actual end of each judgment was not independently verified.
- Sorted unique judgment IDs are shuffled with Python `random.Random(42)`.
- Development: 115 judgments, 1,032 constructed requests. Test: 270 judgments, 2,421 requests.
- Mutations are generated only after splitting. A judgment's variants never cross partitions.
- There is no training/fine-tuning. Epochs, optimizer and learning rate are not applicable.

The fixed test set was reused during engineering integration, including correction of a missing-pinpoint escalation and metric denominator. This is not a blind, preregistered or independent validation. No claim of real-world legal accuracy follows from these results.

## Controlled labels

Every benchmark request is labelled `synthetic: true`; source judgments are real. Clean and whitespace variants expect consistent. Wrong court, known bench, inserted quote word and incorrect existing pinpoint expect inconsistent. Omitted qualification cues and missing extracted pinpoints expect review. An absent local identifier expects unresolved and is not labelled a fabricated case.

These automatic labels are generator-defined. They are not expert legal annotations. Cases use one error at a time and limited variants. Short source passages and overlapping query tokens make this task easier than natural legal reasoning.

## Held-out triage

Positive means **needs attention**: inconsistent, review or unresolved. All methods use identical requests. Zero denominators produce zero. Four-class confusion tables and per-category results are also preserved.

| Method | Accuracy | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| Citation existence | 0.3346 | 1.0000 | 0.1435 | 0.2510 |
| Literal quote | 0.3565 | 0.6871 | 0.3153 | 0.4322 |
| Normalized quote | 0.4461 | 1.0000 | 0.2871 | 0.4461 |
| Full verifier | 0.9789 | 1.0000 | 0.9729 | 0.9863 |

Full-verifier counts: TP 1,830; TN 540; FP 0; FN 51. The 51 misses are selective-quotation constructions (214/265 received review). Full four-state accuracy is also 0.9789, but the other baselines' four-state accuracy need not equal triage accuracy. For example, a literal mismatch can request attention while assigning the wrong detailed state.

The test set has 540 clean cases and 1,881 attention cases (77.7% positive). Zero false positives on these clean cases does not estimate the false-positive rate on natural drafts. Corrupted-quote recall considers original source paragraphs only when a gold paragraph is defined; candidate evidence is not counted as a verified quote.

## Within-judgment retrieval

Use the first three paragraphs with at least 12 normalized tokens per judgment. Take at most 60 tokens, remove a middle span, and cap the query at 47 tokens. The original paragraph is the automatic gold result. There are 344 development and 804 test queries. Candidates are **all extracted paragraphs in that judgment**, not all judgments. Both methods use identical queries/candidates.

BM25 grid: `k1 ∈ {0.8, 1.5, 2.0}`, `b ∈ {0.25, 0.75}`. Maximize development MRR, then recall@1, then prefer smaller k1/b for ties. Selected `k1=0.8, b=0.75`; development R@1/MRR both 1.0. Full grid is in `results/retrieval.json` and the PDF.

| Method | Test R@1 | Test R@5 | MRR |
|---|---:|---:|---:|
| BM25 | 1.0000 | 1.0000 | 1.0000 |
| all-MiniLM-L6-v2 (CUDA) | 0.9478 | 0.9988 | 0.9718 |

The generic pretrained encoder uses 384 dimensions and a 256-token limit. Revision: `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. GPU: NVIDIA GeForce RTX 3050 6GB Laptop, PyTorch 2.6.0+cu124. After warm-up, inference batches 8/16/32 took 0.334/0.273/0.274 seconds on 128 development paragraphs; batch 16 was selected. The timings are noisy single observations, not evidence of a universally optimal batch.

13,456 paragraphs were indexed once in 19.97 seconds; peak PyTorch allocated CUDA memory was about 177 MiB. The lexical method wins on these highly overlapping fragment queries. This says nothing about which method is better for paraphrased, conceptual or cross-judgment search. Dense similarity never changes a quote verification verdict.

## Files

- `evaluation_dev.jsonl`, `evaluation_test.jsonl`: input requests and expected labels.
- `evaluation.json`: predictions, status confusion tables, grouped metrics and timings.
- `retrieval.json`: tuning grid, query ranks, encoder revision and timings.
- `run_manifest.json`: hashes, split counts, environment and GPU status.
- `hardware.json`: measured machine specifications.

## Important ceilings

No natural-error benchmark, independent annotation, multilingual test set, multiple-error adversarial set, confidence interval or human legal entailment evaluation was completed. Source paragraphs can contain headers, quoted numbered material or truncated text; conservative completeness does not itself remove these artifacts. The results establish a working mechanical prototype and a reproducible research baseline, not a production legal assurance system.
