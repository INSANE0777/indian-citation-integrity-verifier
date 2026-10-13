# Phase 2 demonstration and viva guide

## What the project does

It checks a citation and quotation against an attributed, bounded local collection of Supreme Court judgments. Its answer contains findings and source paragraphs, not a generated legal opinion. The four statuses are `consistent`, `inconsistent`, `review`, and `unresolved`.

## Demonstration sequence

1. Run the README setup, tests and local server. Show the acquired corpus's manifest and source license.
2. Open an actual request in `examples/request.json`. Show the original judgment URL and compare the paragraph number and text with the PDF. A `consistent` result concerns extracted text only.
3. Change a number or add a negation in the quotation. Show `QUOTE_MISMATCH` and distinguish nearby candidate evidence from a verified match.
4. Keep the quotation but change the requested court or a known bench size. Show the corresponding metadata discrepancy.
5. Change the pinpoint to another existing paragraph. Show the quotation at its actual location and the incorrect pinpoint finding.
6. Use a citation absent from the bounded corpus. Show `unresolved`; explain why it is not proof of fabrication.
7. Supply a proposition alongside a matching quote. Show `PROPOSITION_REVIEW`. The project does not implement legal entailment.
8. Where the chosen actual judgment contains an immediate qualification cue, shorten the quote before it. Show the context warning and original context. Do not invent a case if the chosen example lacks this construction.
9. Display the saved experiment metrics, judgment-disjoint split, per-category outcomes and optional GPU retrieval results. Explain that the errors were deliberately constructed.

## Questions everyone should be able to answer

**Why use rules instead of training a legal language model?**
The committed modules include source identity, exact quotation, metadata and paragraph checks. These have inspectable definitions and do not require a learned classifier. A pretrained encoder is useful for comparing retrieval, but cannot override a failed quotation check or certify a legal proposition.

**What prevents data leakage?**
The experiment splits judgment IDs before generating request variants. Variants of the same judgment stay in one partition. Retrieval candidates are the same across competing methods. Any tuning uses development results, not held-out test outcomes. This does not eliminate the separate bias from constructing errors using rules similar to the detector.

**Why are some real citations unresolved?**
The source contains only certain years and reporter aliases. An authentic SCC or AIR citation might not be mapped even when an SCR or neutral alias for that judgment exists. The system does not invent aliases or use a fuzzy case name as proof of identity.

**What is the difference between retrieval and verification?**
Retrieval ranks likely paragraphs. Verification checks whether the submitted words occur as a contiguous normalized sequence and whether available metadata agree. Retrieval overlap is not logical entailment or binding force.

**Why preserve paragraph numbers?**
A citation's pinpoint refers to the judgment's actual numbered paragraph, not an arbitrary extraction chunk. Renumbering paragraphs or treating PDF page numbers as paragraphs would fabricate evidence locations.

**Why can the system not confidently reject every missing pinpoint?**
PDF extraction can omit text or stop at ambiguous numbering. Unless completeness is independently established, a missing extracted number warrants review rather than a universal claim about the original judgment.

**Why might a context warning be wrong?**
A word such as “however” can introduce an unrelated contrast. Important qualifications can use different wording, occur earlier, or lie several paragraphs away. The cue heuristic provides a review prompt, not an expert annotation of misleading quotation.

**What exactly do accuracy and F1 measure?**
They measure agreement with automatically constructed benchmark labels under the metric's stated positive class. Triage treats review-needed requests differently from a strict four-class status metric. Neither number is the rate of correctness of legal advice.

**What did the GPU do?**
Consult `results/` for the actual executed experiment. If completed, it ran inference with a pinned pretrained sentence encoder to rank paragraphs. It did not train the verifier or establish legal reasoning capability. Do not describe an unavailable or skipped GPU run as completed.

**What remains outside the scope?**
Ratio versus obiter, speaker/voice attribution, overruling and treatment tracking, comprehensive reporter coverage, multilingual documents, and proposition entailment. A quoted argument can match perfectly without being a holding.

## Contribution attestation

The source PDF lists Afjal Hussein, Ayush Kumar and Arush Sharma. It does not establish who performed particular implementation tasks. Each person must independently record their actual contributions and be able to explain the whole implementation. Do not submit invented equal assignments or signatures.

## Academic integrity

The supplied rubric includes similarity and AI-generated-content checks. This project was developed with AI assistance. Review and understand all code, verify source references and results, and follow the institution's disclosure rules. No detector outcome or grade is promised. The report's missing faculty-assigned Team ID must be supplied by the team if required; it must not be guessed.
