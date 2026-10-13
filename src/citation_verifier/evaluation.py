"""Deterministic, judgment-disjoint evaluation helpers for the local verifier."""
from __future__ import annotations

import math
import random
import re
import time
from collections import Counter, defaultdict
from typing import Any, Iterable, Sequence

from .core import Corpus, normalized_text, verify

STATUSES = ("consistent", "review", "inconsistent", "unresolved")
STATUS_GROUPS = {
    "clean_quote": "verified_clean",
    "whitespace_quote": "verified_clean",
    "wrong_court": "definite_discrepancy",
    "wrong_bench": "definite_discrepancy",
    "quote_corruption": "definite_discrepancy",
    "wrong_pinpoint": "definite_discrepancy",
    "selective_quote": "human_review",
    "missing_pinpoint": "extraction_uncertainty",
    "absent_local_citation": "triage",
}


def split_judgment_ids(corpus: Corpus, *, seed: int = 42, dev_fraction: float = 0.30) -> tuple[list[str], list[str]]:
    """Shuffle immutable judgment IDs with a fixed seed; return dev and test IDs."""
    if not 0 < dev_fraction < 1:
        raise ValueError("dev_fraction must be strictly between zero and one")
    ids = sorted({str(row["id"]) for row in corpus.rows})
    if len(ids) < 2:
        raise ValueError("at least two unique judgment IDs are required for disjoint splits")
    random.Random(seed).shuffle(ids)
    dev_count = max(1, min(len(ids) - 1, int(len(ids) * dev_fraction)))
    return ids[:dev_count], ids[dev_count:]


def generate_mutations(corpus: Corpus, *, judgment_ids: Iterable[str]) -> list[dict[str, Any]]:
    """Generate reproducible, clearly synthetic checks from real corpus paragraphs."""
    requested = set(judgment_ids)
    rows = [row for row in corpus.rows if str(row["id"]) in requested]
    found_ids = {str(row["id"]) for row in rows}
    if requested - found_ids:
        raise ValueError(f"unknown judgment IDs: {sorted(requested - found_ids)}")
    cases: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda value: str(value["id"])):
        paragraphs = row["paragraphs"]
        citation = next(iter(row["citations"]), None)
        if not citation:
            continue
        paragraph = next((p for p in paragraphs if len(normalized_text(p["text"]).split()) >= 5), paragraphs[0])
        quote = _sentence_fragment(paragraph["text"])
        pno = paragraph["number"]
        base = {"citation": citation, "quote": quote}
        wrong = next((p for p in paragraphs if p["number"] != pno), None)

        def add(category: str, request: dict[str, Any], expected: str, *, gold: int | None = None, group: str | None = None) -> None:
            cases.append({
                "case_id": f"{row['id']}::{category}", "judgment_id": str(row["id"]),
                "category": category, "synthetic": True, "request": request,
                "expected_status": expected, "evaluation_group": group or STATUS_GROUPS[category],
                "gold_paragraph": gold,
            })

        add("clean_quote", dict(base), "consistent", gold=pno)
        add("whitespace_quote", {**base, "quote": re.sub(r"\s+", "  \n", quote)}, "consistent", gold=pno)
        add("wrong_court", {**base, "court": "Delhi High Court"}, "inconsistent", gold=pno)
        if isinstance(row.get("bench_size"), int) and not isinstance(row.get("bench_size"), bool):
            add("wrong_bench", {**base, "bench_size": row["bench_size"] + 1}, "inconsistent", gold=pno)
        add("quote_corruption", {**base, "quote": _corrupt_quote(quote)}, "inconsistent", gold=pno)
        if wrong is not None:
            add("wrong_pinpoint", {**base, "pinpoint": wrong["number"]}, "inconsistent", gold=pno)
        selective_paragraph = next((p for p in paragraphs if re.search(r"\b(?:however|but|unless|provided that|subject to|except|only|save that)\b", p["text"], re.I)), None)
        if selective_paragraph:
            selective_quote = _prefix_before_qualifier(selective_paragraph["text"])
            if selective_quote:
                add("selective_quote", {"citation": citation, "quote": selective_quote}, "review", gold=selective_paragraph["number"])
        # Missing pinpoint is an extraction uncertainty, not evidence of case fabrication.
        missing_pinpoint = max(p["number"] for p in paragraphs) + 1
        add("missing_pinpoint", {
            "citation": citation,
            "quote": quote,
            "pinpoint": missing_pinpoint,
        }, "review", gold=pno, group="extraction_uncertainty")
        add("absent_local_citation", {"citation": "2099 INSC 999999", "quote": quote}, "unresolved", group="triage")
    return cases


def classification_metrics(expected: Sequence[str], predicted: Sequence[str], *, labels: Sequence[str] = STATUSES) -> dict[str, Any]:
    if len(expected) != len(predicted):
        raise ValueError("expected and predicted must have equal lengths")
    if not expected:
        raise ValueError("metrics require at least one case")
    labels = tuple(labels)
    confusion = {label: {guess: 0 for guess in labels} for label in labels}
    for actual, guess in zip(expected, predicted):
        if actual not in confusion or guess not in confusion:
            raise ValueError(f"unknown status: {actual!r} or {guess!r}")
        confusion[actual][guess] += 1
    per_class: dict[str, dict[str, float | int]] = {}
    for label in labels:
        tp = confusion[label][label]
        fp = sum(confusion[actual][label] for actual in labels if actual != label)
        fn = sum(confusion[label][guess] for guess in labels if guess != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        per_class[label] = {"precision": precision, "recall": recall, "f1": _f1(precision, recall), "support": sum(confusion[label].values())}
    count = len(expected)
    accuracy = sum(a == b for a, b in zip(expected, predicted)) / count
    macro_f1 = sum(float(per_class[label]["f1"]) for label in labels) / len(labels)
    weights = [int(per_class[label]["support"]) for label in labels]
    weighted_f1 = sum(float(per_class[label]["f1"]) * weight for label, weight in zip(labels, weights)) / count
    return {
        "count": count, "accuracy": accuracy,
        "precision_macro": sum(float(per_class[x]["precision"]) for x in labels) / len(labels),
        "recall_macro": sum(float(per_class[x]["recall"]) for x in labels) / len(labels),
        "f1_macro": macro_f1, "f1_weighted": weighted_f1,
        "confusion": confusion, "per_class": per_class,
        "grouped": _group_metrics(expected, predicted),
    }


def _group_metrics(expected: Sequence[str], predicted: Sequence[str]) -> dict[str, Any]:
    output = {}
    for name, gold_statuses in (
        ("human_review", {"review"}),
        ("definite_discrepancy", {"inconsistent"}),
        ("review_or_discrepancy", {"review", "inconsistent"}),
        ("attention", {"review", "inconsistent", "unresolved"}),
    ):
        tp = fp = fn = tn = 0
        for actual, guess in zip(expected, predicted):
            actual_positive = actual in gold_statuses
            guess_positive = guess in gold_statuses
            tp += int(actual_positive and guess_positive)
            fp += int(not actual_positive and guess_positive)
            fn += int(actual_positive and not guess_positive)
            tn += int(not actual_positive and not guess_positive)
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        output[name] = {"precision": p, "recall": r, "f1": _f1(p, r), "accuracy": (tp + tn) / len(expected), "tp": tp, "fp": fp, "fn": fn, "tn": tn}
    return output


def rank_bm25(documents: Sequence[str], query: str, *, k1: float = 1.5, b: float = 0.75) -> list[dict[str, Any]]:
    """Rank a judgment's paragraphs using a small BM25 implementation."""
    if k1 <= 0 or not 0 <= b <= 1:
        raise ValueError("BM25 requires k1 > 0 and 0 <= b <= 1")
    docs = [normalized_text(text).split() for text in documents]
    terms = normalized_text(query).split()
    if not docs:
        return []
    df = Counter(term for doc in docs for term in set(doc))
    avgdl = sum(map(len, docs)) / len(docs) or 1.0
    scores = []
    for index, doc in enumerate(docs):
        frequencies = Counter(doc)
        score = 0.0
        for term in terms:
            freq = frequencies[term]
            if not freq:
                continue
            idf = math.log(1 + (len(docs) - df[term] + 0.5) / (df[term] + 0.5))
            score += idf * (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * len(doc) / avgdl))
        scores.append({"index": index, "score": score})
    return sorted(scores, key=lambda result: (-result["score"], result["index"]))


def evaluate_cases(corpus: Corpus, cases: Sequence[dict[str, Any]], *, baselines: Sequence[str] = ("citation_existence", "literal_quote", "normalized_quote", "full_verifier")) -> dict[str, Any]:
    allowed = {"citation_existence", "literal_quote", "normalized_quote", "full_verifier"}
    if not cases:
        raise ValueError("evaluation requires at least one case")
    if not baselines or set(baselines) - allowed:
        raise ValueError(f"baselines must be selected from {sorted(allowed)}")
    predictions: dict[str, list[str]] = {name: [] for name in baselines}
    times: dict[str, list[float]] = {name: [] for name in baselines}
    retrieval: dict[str, list[bool]] = {name: [] for name in baselines}
    per_case = []
    categories: dict[str, dict[str, dict[str, int]]] = defaultdict(lambda: {name: {"correct": 0, "count": 0} for name in baselines})
    for case in cases:
        request = case["request"]
        rows = corpus.resolve(request["citation"])
        if "citation_existence" in predictions:
            start = time.perf_counter()
            pred = "unresolved" if not rows else "consistent"
            _record(predictions, times, "citation_existence", pred, start)
            retrieval["citation_existence"].append(False)
        if "literal_quote" in predictions:
            start = time.perf_counter()
            pred, found = _quote_baseline(rows, request.get("quote"), normalized=False)
            _record(predictions, times, "literal_quote", pred, start)
            retrieval["literal_quote"].append(case.get("gold_paragraph") in found if case.get("gold_paragraph") is not None else False)
        if "normalized_quote" in predictions:
            start = time.perf_counter()
            pred, found = _quote_baseline(rows, request.get("quote"), normalized=True)
            _record(predictions, times, "normalized_quote", pred, start)
            retrieval["normalized_quote"].append(case.get("gold_paragraph") in found if case.get("gold_paragraph") is not None else False)
        if "full_verifier" in predictions:
            start = time.perf_counter()
            result = verify(corpus, request)
            _record(predictions, times, "full_verifier", result["status"], start)
            retrieved_numbers = {entry["number"] for entry in result.get("evidence", []) if entry.get("match_type", "verified") == "verified"}
            retrieval["full_verifier"].append(case.get("gold_paragraph") in retrieved_numbers if case.get("gold_paragraph") is not None else False)
        for name, values in predictions.items():
            categories[case["category"]][name]["count"] += 1
            categories[case["category"]][name]["correct"] += int(values[-1] == case["expected_status"])
        per_case.append({"case_id": case["case_id"], "judgment_id": case["judgment_id"], "category": case["category"], "evaluation_group": case["evaluation_group"], "expected_status": case["expected_status"], "gold_paragraph": case.get("gold_paragraph"), "predictions": {name: predictions[name][-1] for name in baselines}, "evidence_retrieval": {name: retrieval[name][-1] for name in baselines if name in retrieval}})
    expected = [case["expected_status"] for case in cases]
    summary = {}
    gold_count = sum(case.get("gold_paragraph") is not None for case in cases)
    for name, values in predictions.items():
        summary[name] = {
            "metrics": classification_metrics(expected, values),
            "per_category": {cat: {"accuracy": entries[name]["correct"] / entries[name]["count"], "count": entries[name]["count"], "correct": entries[name]["correct"]} for cat, entries in categories.items()},
            "evidence_retrieval_recall": (sum(retrieval[name][index] for index, case in enumerate(cases) if case.get("gold_paragraph") is not None) / gold_count) if gold_count else None,
            "evidence_retrieval_count": gold_count,
            "timings_ms": {"mean": sum(times[name]) / len(times[name]), "median": _median(times[name]), "total": sum(times[name]), "count": len(times[name])},
        }
    return {"case_count": len(cases), "baselines": summary, "cases": per_case}


def make_retrieval_queries(corpus: Corpus, judgment_ids: Iterable[str]) -> list[dict[str, Any]]:
    """Create automatically labelled quote-gap fragments within each judgment."""
    requested = set(judgment_ids)
    output = []
    for row in sorted((r for r in corpus.rows if str(r["id"]) in requested), key=lambda r: str(r["id"])):
        for paragraph in row["paragraphs"]:
            tokens = normalized_text(paragraph["text"]).split()
            if len(tokens) < 8:
                continue
            start = len(tokens) // 3
            stop = min(len(tokens) - 2, start + max(2, len(tokens) // 4))
            query = " ".join(tokens[:start] + tokens[stop:])
            overlap = _overlap(query, paragraph["text"])
            output.append({"judgment_id": str(row["id"]), "query": query, "gold_paragraph": paragraph["number"], "query_type": "overlap_heavy" if overlap >= 0.65 else "quote_gap", "relevance": "automatic_same_paragraph_source"})
    return output


def tune_retrieval_thresholds(dev_rows: Sequence[dict[str, Any]], score_key: str = "score", threshold_grid: Sequence[float] | None = None) -> dict[str, Any]:
    """Select a retrieval-score threshold using development rows only."""
    if not dev_rows:
        raise ValueError("development retrieval rows are required")
    grid = list(threshold_grid or (0.0, 0.05, 0.1, 0.2, 0.35, 0.5, 0.75, 1.0))
    if not grid:
        raise ValueError("threshold grid cannot be empty")
    candidates = []
    for threshold in grid:
        tp = fp = fn = tn = 0
        for row in dev_rows:
            retrieved = row[score_key] >= threshold
            relevant = bool(row["relevant"])
            tp += int(retrieved and relevant)
            fp += int(retrieved and not relevant)
            fn += int(not retrieved and relevant)
            tn += int(not retrieved and not relevant)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        candidates.append({"threshold": threshold, "precision": precision, "recall": recall, "f1": _f1(precision, recall), "tp": tp, "fp": fp, "fn": fn, "tn": tn})
    selected = max(candidates, key=lambda item: (item["f1"], item["precision"], item["threshold"]))
    return {"selected_threshold": selected["threshold"], "selection_split": "dev", "grid": candidates}


def _quote_baseline(rows: list[dict[str, Any]], quote: str | None, *, normalized: bool) -> tuple[str, set[int]]:
    if not rows:
        return "unresolved", set()
    if not quote:
        return "review", set()
    needle = normalized_text(quote) if normalized else quote.strip()
    found = set()
    for row in rows:
        for paragraph in row["paragraphs"]:
            text = normalized_text(paragraph["text"]) if normalized else paragraph["text"]
            if needle and f" {needle} " in f" {text} ":
                found.add(paragraph["number"])
    return ("consistent" if found else "inconsistent"), found


def _sentence_fragment(text: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    candidate = next((s.strip() for s in sentences if len(normalized_text(s).split()) >= 5), text.strip())
    words = candidate.split()
    return " ".join(words[:32]) if len(words) > 32 else candidate


def _corrupt_quote(quote: str) -> str:
    words = quote.split()
    if len(words) > 2:
        words.insert(2, "unquestionably")
        return " ".join(words)
    return f"{quote} never stated"


def _prefix_before_qualifier(text: str) -> str:
    match = re.search(r"\b(?:however|but|unless|provided that|subject to|except|only|save that)\b", text, re.I)
    if not match:
        return ""
    prefix = text[:match.start()].strip(" ,;:-")
    return prefix if len(normalized_text(prefix).split()) >= 4 else ""


def _overlap(query: str, document: str) -> float:
    terms = set(normalized_text(query).split())
    return len(terms & set(normalized_text(document).split())) / max(1, len(terms))


def _record(predictions: dict[str, list[str]], times: dict[str, list[float]], name: str, prediction: str, start: float) -> None:
    predictions[name].append(prediction)
    times[name].append((time.perf_counter() - start) * 1000)


def _f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2
