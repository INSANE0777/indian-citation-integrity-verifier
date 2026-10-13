#!/usr/bin/env python3
"""Acquire and parse real Supreme Court of India judgments from the AWS registry."""
from __future__ import annotations
import argparse, hashlib, json, re, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Iterable
from urllib.parse import urlencode
import xml.etree.ElementTree as ET
import requests

BASE_URL = "https://indian-supreme-court-judgments.s3.ap-south-1.amazonaws.com/"
USER_AGENT = "indian-corpus-acquisition/1.0 (research; CC-BY-4.0 registry data)"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _clean_html(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", unescape(value)).strip()


def parse_metadata(metadata: dict) -> dict:
    html = metadata.get("raw_html", "")
    title_match = re.search(r"<strong[^>]*>(.*?)</strong>\s*-\s*<span[^>]*class=['\"]escrText", html, re.I | re.S)
    if not title_match:
        title_match = re.search(r"aria-label=['\"](.*?)\s+pdf['\"]", html, re.I | re.S)
    case_name = _clean_html(title_match.group(1) if title_match else metadata.get("path", ""))
    case_name = re.sub(r"\s+versus\s+", " v. ", case_name, flags=re.I)
    case_name = re.sub(r"\s+v\.?\s+", " v. ", case_name, flags=re.I).strip(" -")
    date_match = re.search(r"Decision\s+Date\s*:.*?([0-9]{2}-[0-9]{2}-[0-9]{4})", html, re.I | re.S)
    iso_date = None
    if date_match:
        try:
            iso_date = datetime.strptime(date_match.group(1).strip(), "%d-%m-%Y").date().isoformat()
        except ValueError:
            pass
    bench_match = re.search(r"Bench\s*:.*?(\d+)\s+Judges", html, re.I | re.S)
    citations = []
    raws = re.findall(r"<span[^>]*class=['\"]escrText['\"][^>]*>\s*(.*?)\s*</span>", html, re.I | re.S)
    raws += re.findall(r"<span[^>]*class=['\"]ncDisplay['\"][^>]*>\s*(.*?)\s*</span>", html, re.I | re.S)
    for raw in raws:
        citation = _clean_html(raw)
        if citation and citation not in citations:
            citations.append(citation)
    nc = str(metadata.get("nc_display", "")).strip()
    if nc:
        nc = re.sub(r"(\d{4})INSC(\d+)", r"\1 INSC \2", nc)
        if nc not in citations:
            citations.append(nc)
    return {"case_name": case_name, "date": iso_date, "bench_size": int(bench_match.group(1)) if bench_match else None, "citations": citations}


_PARAGRAPH_START = re.compile(r"^\s*(\d{1,4})\s*[.)]\s+(\S.*)$")


def extract_numbered_paragraphs(pages: Iterable[str], *, return_complete: bool = False):
    paragraphs, current, started, seen_numbers, complete = [], None, False, set(), False
    judgment_started = False
    halted = False
    for page_no, page in enumerate(pages, 1):
        if halted:
            break
        for raw_line in page.replace("\r", "").splitlines():
            line = re.sub(r"\s+", " ", raw_line).strip()
            if not line:
                continue
            if line.upper() in {"JUDGMENT", "JUDGMENTS", "ORDER"}:
                judgment_started = True
                continue
            marker = _PARAGRAPH_START.match(line)
            if marker:
                if not judgment_started:
                    continue
                number, text = int(marker.group(1)), marker.group(2).strip()
                if number in seen_numbers:
                    complete = False
                    if current is not None:
                        paragraphs.append(current)
                    current, started, halted = None, False, True
                    break
                if current is not None:
                    if number != current["number"] + 1:
                        complete = False
                    paragraphs.append(current)
                seen_numbers.add(number)
                current = {"number": number, "text": text, "page": page_no}
                started = True
            elif started and current is not None:
                if re.fullmatch(r"\d{1,4}", line) or line.upper() in {"JUDGMENT", "ORDER", "DISSENT", "SIGNED"}:
                    continue
                current["text"] += " " + line
    if current is not None:
        paragraphs.append(current)
    if not paragraphs:
        complete = False
    return (paragraphs, complete) if return_complete else paragraphs


def _fetch(session: requests.Session, url: str, target: Path, retries: int = 3) -> None:
    if target.exists() and target.stat().st_size > 0:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    last = None
    for attempt in range(retries):
        try:
            with session.get(url, timeout=(15, 90), stream=True) as response:
                response.raise_for_status()
                temp = target.with_suffix(target.suffix + ".part")
                with temp.open("wb") as out:
                    for block in response.iter_content(1024 * 1024):
                        if block:
                            out.write(block)
                temp.replace(target)
                return
        except Exception as exc:
            last = exc
            if attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"download failed: {url}: {last}")


def list_keys(year: int, session: requests.Session) -> list[str]:
    keys, token = [], None
    while True:
        params = [("list-type", "2"), ("prefix", f"metadata/json/year={year}/"), ("max-keys", "1000")]
        if token:
            params.append(("continuation-token", token))
        root = ET.fromstring(session.get(BASE_URL + "?" + urlencode(params), timeout=60).content)
        ns = "{http://s3.amazonaws.com/doc/2006-03-01/}"
        keys.extend(x.text for x in root.findall(ns + "Contents/" + ns + "Key") if x.text and x.text.endswith(".json"))
        if root.findtext(ns + "IsTruncated") != "true":
            return keys
        token = root.findtext(ns + "NextContinuationToken")


def acquire(limit: int, years: list[int], workers: int, root: Path) -> dict:
    cache = root / ".cache" / "raw"
    data_dir = root / "data"
    cache.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    keys = []
    for year in years:
        keys.extend(list_keys(year, session))
    available_count = len(keys)
    keys = sorted(keys)[:limit]
    selected_count = len(keys)
    rows, failures = [], []

    def one(key: str):
        year = int(re.search(r"year=(\d+)", key).group(1))
        stem = Path(key).stem
        meta_url = BASE_URL + key
        pdf_key = f"data/pdf/year={year}/english/{stem}_EN.pdf"
        pdf_url = BASE_URL + pdf_key
        meta_path, pdf_path = cache / key, cache / pdf_key
        _fetch(session, meta_url, meta_path)
        _fetch(session, pdf_url, pdf_path)
        return key, meta_path, pdf_path, meta_url, pdf_url

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        jobs = {pool.submit(one, key): key for key in keys}
        for future in as_completed(jobs):
            key = jobs[future]
            try:
                _, meta_path, pdf_path, meta_url, pdf_url = future.result()
                metadata = json.loads(meta_path.read_text(encoding="utf-8"))
                import fitz
                with fitz.open(pdf_path) as doc:
                    pages = [p.get_text("text") for p in doc]
                paragraphs, complete = extract_numbered_paragraphs(pages, return_complete=True)
                parsed = parse_metadata(metadata)
                if not parsed["date"] or not parsed["case_name"] or not paragraphs:
                    raise ValueError(f"ambiguous or empty judgment: {key}")
                rows.append({"id": metadata.get("nc_display") or Path(key).stem, **parsed, "court": "Supreme Court of India", "paragraphs": paragraphs, "source_url": pdf_url, "metadata_url": meta_url, "sha256": sha256_file(pdf_path), "paragraph_numbering_complete": complete})
            except Exception as exc:
                failures.append({"key": key, "error": str(exc)})
    rows.sort(key=lambda x: (x["date"], x["id"]))
    corpus = data_dir / "corpus.jsonl"
    with corpus.open("w", encoding="utf-8", newline="\n") as out:
        for row in rows:
            out.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    manifest = {"retrieved_at": datetime.now(timezone.utc).isoformat(), "years": years, "requested": limit, "available_count": available_count, "selected_count": selected_count, "downloaded": len(rows), "failures": failures, "failure_count": len(failures), "license": "CC-BY-4.0", "attribution": "Vanga (2025), Indian Supreme Court Judgments, AWS Open Data Registry", "source": BASE_URL, "selection": "deterministic sorted registry metadata keys", "paragraph_numbering_complete_policy": "always false; extraction does not verify the final judgment paragraph"}
    (data_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=2000)
    parser.add_argument("--years", type=int, nargs="+", default=[2023, 2022])
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    print(json.dumps(acquire(args.limit, args.years, args.workers, args.root), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
