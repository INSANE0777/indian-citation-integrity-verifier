import hashlib
import json
from pathlib import Path

import pytest

from scripts.ingest_corpus import (
    extract_numbered_paragraphs,
    parse_metadata,
    sha256_file,
)


def test_parse_metadata_keeps_only_real_registry_aliases():
    html = '''
    <button aria-label="A v. B pdf"><strong>A <span> versus </span> B </strong>
    - <span class="escrText">[2023] 10 S.C.R. 1001</span>
    <span class="ncDisplay">2023 INSC 600</span></button>
    <strong>Coram : JUSTICE ONE, JUSTICE TWO</strong>
    <strong class="caseDetailsTD">Decision Date :<font> 05-07-2023</font> | Bench :<font> 2 Judges</font></strong>
    '''
    got = parse_metadata({"raw_html": html, "nc_display": "2023INSC600"})
    assert got["case_name"] == "A v. B"
    assert got["date"] == "2023-07-05"
    assert got["bench_size"] == 2
    assert got["citations"] == ["[2023] 10 S.C.R. 1001", "2023 INSC 600"]
    assert got["citations"].count("SCC") == 0


def test_extracts_only_numbered_judgment_body_with_source_pages():
    pages = [
        "HEADNOTE\n1. This is a headnote and must not appear.\nJUDGMENT\n1. The court considers the appeal.\nContinuation on same page.",
        "2. The appeal is allowed.\n\nSigned",
    ]
    got = extract_numbered_paragraphs(pages)
    assert got == [
        {"number": 1, "text": "The court considers the appeal. Continuation on same page.", "page": 1},
        {"number": 2, "text": "The appeal is allowed.", "page": 2},
    ]


def test_does_not_turn_unmarked_lines_or_page_numbers_into_paragraphs():
    pages = ["JUDGMENT\nThe court states a reason.\n42\nAppendix\nNo paragraph marker."]
    assert extract_numbered_paragraphs(pages) == []


def test_repeated_numbering_is_marked_incomplete_and_keeps_first_opinion():
    pages = ["JUDGMENT\n1. Majority reason.\n2. Majority result.\nDISSENT\n1. Dissent reason."]
    paragraphs, complete = extract_numbered_paragraphs(pages, return_complete=True)
    assert [p["number"] for p in paragraphs] == [1, 2]
    assert complete is False


def test_repeated_numbering_across_pages_stops_extraction():
    paragraphs, complete = extract_numbered_paragraphs(["JUDGMENT\n1. Majority.", "2. Result.", "1. Dissent.", "3. Should not merge."], return_complete=True)
    assert [p["number"] for p in paragraphs] == [1, 2]
    assert complete is False


def test_numbering_gap_is_never_claimed_complete():
    paragraphs, complete = extract_numbered_paragraphs(["JUDGMENT\n1. First.\n3. Third."], return_complete=True)
    assert [p["number"] for p in paragraphs] == [1, 3]
    assert complete is False


def test_quoted_numbered_list_stops_at_ambiguous_duplicate():
    paragraphs, complete = extract_numbered_paragraphs(["JUDGMENT\n1. Holding.\n2. The quoted list says:\n1. quoted item."], return_complete=True)
    assert [p["number"] for p in paragraphs] == [1, 2]
    assert complete is False


def test_numbering_completeness_is_false_without_verified_final_paragraph():
    paragraphs, complete = extract_numbered_paragraphs(["JUDGMENT\n1. First.\n2. Second."], return_complete=True)
    assert len(paragraphs) == 2
    assert complete is False


def test_sha256_file_is_real_digest(tmp_path: Path):
    p = tmp_path / "x.pdf"
    p.write_bytes(b"judgment")
    assert sha256_file(p) == hashlib.sha256(b"judgment").hexdigest()
