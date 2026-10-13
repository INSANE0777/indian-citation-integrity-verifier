# Phase 1 source audit

Audited with Firecrawl search/scrape on 2026-10-13. This note records source status and prevents unverified Phase 1 claims from entering the final report.

## Retained sources

- Dahl et al., *Large Legal Fictions* — verified through Oxford Academic, arXiv:2401.01301, and Stanford Law. Retained as `ref1`; the final report states its jurisdiction and task limits.
- Magesh et al., *Hallucination-Free?* — verified through Stanford Law and Wiley, DOI 10.1111/jels.12413. Retained as `ref2`; the final report does not generalize product-audit rates to this prototype.
- Liu, Stammbach, and Henderson, *Who Checks the Citations?* — arXiv:2606.21155 is real and contains a taxonomy, an injected-error benchmark, and a United States filing study. It is not included in the numbered minimum bibliography because it is a 2026 preprint discovered after the initial literature set and the final report is scoped to the more established/verified sources. If cited later, cite it as an arXiv preprint and preserve its US-only scope.
- Li et al., *Source or It Didn't Happen* — arXiv:2605.08583 is real and describes CiteTracer, a field-level citation detector and synthetic benchmark. It is not included in the numbered final bibliography because the report does not depend on its 2026 claims and the final experiment is not a comparison to CiteTracer.
- AWS Open Data Registry — verified source page lists the Indian Supreme Court Judgments collection, S3 bucket, metadata and PDF resources, and CC-BY-4.0. Retained as `dataset`.

## Claims deliberately removed or narrowed

- The Phase 1 sentence describing a February 2026 Supreme Court ruling as the first ruling of its kind and stating that every decision containing any hallucinated material is void was found through a secondary observer article, not a primary judgment or official court record in the search evidence. The final report does not rely on or repeat that claim.
- The Phase 1 claim that verification always requires a paid database was removed. The project uses a public AWS Open Data source; commercial coverage, licensing, and search features are separate questions.
- Product capability claims about SCC Online, Manupatra, CaseMine, Indian Kanoon, and other vendors were not used as established comparative facts. An unpublished implementation cannot be called absent merely because it was not found.
- GPTZero's ICLR 2026 news article and other blog/industry sources are not counted as scholarly references. They may be useful leads but do not support the report's primary technical claims.
- `inLegalBERT` is treated as the verified arXiv paper “Pre-trained Language Models for the Legal Domain: A Case Study on Indian Law,” arXiv:2209.06049, rather than the Phase 1 social-media wording. It was not required for the core experiment and is not counted in the final minimum bibliography.

## Report boundary

The 19 numbered scholarly references cover legal hallucination audits, retrieval-grounded generation, citation evaluation, fact verification, legal-language benchmarks, Indian legal NLP, contextual encoders, BM25, dense retrieval, and factual-consistency evaluation. The dataset source is listed separately. The report's measured values come only from `results/` and are explicitly labelled as controlled, semi-synthetic triage or within-judgment retrieval results. They are not estimates of real-world hallucination prevalence or legal-advice accuracy.
