"""
Normalize the global/topical corpus (scripts/fetch_*.py) into the same
processed schema that process_raw.py produces for the Tunisia pipeline, and
write it to the same data/processed/ directory that data/ingest.py reads.

This is the reconciliation of the two Python pipelines into one canonical
ingestion path: two sets of collectors (Tunisia-focused, global/topical),
one shared normalize -> chunk -> embed -> store pipeline. GDELT and arXiv
records from either collector share the same `source` value and therefore
merge naturally in the vector store; Openverse, Met Museum, Internet
Archive and DBpedia add four new sources alongside the Tunisia pipeline's
six.

Usage:
    python data/process_global.py
"""

from __future__ import annotations

import json
from pathlib import Path

from data.process_raw import (  # reuse, don't reinvent
    PROCESSED_DIR,
    TODAY,
    clean_text,
    dedup,
    normalize_gdelt,
    stable_id,
)

RAW_DIR = (Path(__file__).parent / "raw").resolve()


def _as_text(value) -> str:
    """Archive.org/DBpedia fields are inconsistently str, list, or missing."""
    if value is None:
        return ""
    if isinstance(value, list):
        return "; ".join(str(v) for v in value if v)
    return str(value)


def _as_tags(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v]
    return [str(value)]


# ── Normalizers for the global pipeline's sources ───────────────────────────

def normalize_openverse(raw: dict, source_file: str) -> dict:
    title = clean_text(raw.get("title", ""))
    return {
        "id": raw.get("id") or stable_id(title, raw.get("url", "")),
        "source": "openverse",
        "category": "image",
        "title": title,
        "text": title,  # Openverse exposes no separate description field
        "url": raw.get("url", ""),
        "image_url": raw.get("url") or raw.get("thumbnail"),
        "date": None,
        "lang": None,
        "tags": _as_tags(raw.get("tags")) + [raw.get("license", ""), raw.get("query_term", "")],
        "raw_source": source_file,
        "processed_on": TODAY,
    }


def normalize_met(raw: dict, source_file: str) -> dict:
    title = clean_text(raw.get("title", ""))
    descriptors = " ".join(
        filter(None, [raw.get("culture"), raw.get("period"), raw.get("medium"), raw.get("department")])
    )
    return {
        "id": str(raw.get("id") or stable_id(title)),
        "source": "met_museum",
        "category": "culture",
        "title": title,
        "text": clean_text(descriptors),
        "url": raw.get("object_url", ""),
        "image_url": raw.get("image_url"),
        "date": None,  # Met's "date" field is free text (e.g. "19th century"), not ISO
        "lang": None,
        "tags": [t for t in [raw.get("culture"), raw.get("department"), raw.get("query_term")] if t],
        "raw_source": source_file,
        "processed_on": TODAY,
    }


def normalize_archive(raw: dict, source_file: str) -> dict:
    title = clean_text(_as_text(raw.get("title")))
    date = _as_text(raw.get("date"))[:10] or None
    return {
        "id": raw.get("identifier") or stable_id(title),
        "source": "internet_archive",
        "category": "history",
        "title": title,
        "text": clean_text(_as_text(raw.get("description"))),
        "url": raw.get("url", ""),
        "image_url": None,
        "date": date,
        "lang": None,
        "tags": _as_tags(raw.get("subject")) + [raw.get("mediatype", ""), raw.get("query_term", "")],
        "raw_source": source_file,
        "processed_on": TODAY,
    }


def normalize_dbpedia(raw: dict, source_file: str) -> dict:
    title = clean_text(raw.get("label") or raw.get("entity") or "")
    categories = raw.get("categories") or []
    # abstract is unavailable on this DBpedia endpoint for every entity tested
    # (see data/README.md) — fall back to the category list as the text body
    # rather than leaving the record empty.
    text = clean_text(raw.get("abstract") or ("Categories: " + ", ".join(categories[:15])))
    return {
        "id": raw.get("url") or stable_id(raw.get("entity", "")),
        "source": "dbpedia",
        "category": "history",
        "title": title,
        "text": text,
        "url": raw.get("url", ""),
        "image_url": raw.get("thumbnail"),
        "date": None,
        "lang": None,
        "tags": categories[:15],
        "raw_source": source_file,
        "processed_on": TODAY,
    }


def normalize_arxiv_global(raw: dict, source_file: str) -> dict:
    return {
        "id": raw.get("id") or stable_id(raw.get("title", "")),
        "source": "arxiv",
        "category": "science",
        "title": clean_text(raw.get("title", "")),
        "text": clean_text(raw.get("summary", "")),
        "url": raw.get("id") or raw.get("pdf_url", ""),
        "image_url": None,
        "date": (raw.get("published") or "")[:10] or None,
        "lang": "en",
        "tags": raw.get("categories", []),
        "raw_source": source_file,
        "processed_on": TODAY,
    }


# ── Per-directory processing ────────────────────────────────────────────────

SOURCE_DIRS = {
    "gdelt": normalize_gdelt,              # same API shape as the Tunisia pipeline — reused as-is
    "openverse": normalize_openverse,
    "met": normalize_met,
    "archive": normalize_archive,
    "dbpedia": normalize_dbpedia,
}


def process_dir(subdir: str, normalizer) -> list[dict]:
    folder = RAW_DIR / subdir
    if not folder.exists():
        return []
    records: list[dict] = []
    for raw_file in sorted(folder.glob("*.json")):
        if raw_file.name.startswith("_"):
            continue
        try:
            data = json.loads(raw_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"  [error] could not read {subdir}/{raw_file.name}: {exc}")
            continue
        if not isinstance(data, list):
            data = [data]
        for item in data:
            if not isinstance(item, dict):
                continue
            try:
                rec = normalizer(item, f"{subdir}/{raw_file.name}")
            except Exception as exc:  # noqa: BLE001 — one malformed record shouldn't kill the run
                print(f"  [error] normalize failed for {subdir}/{raw_file.name}: {exc}")
                continue
            if rec.get("title") or rec.get("text"):
                records.append(rec)
    return dedup(records)


def process_arxiv_global() -> list[dict]:
    papers_file = RAW_DIR / "arxiv" / "papers.json"
    if not papers_file.exists():
        return []
    data = json.loads(papers_file.read_text(encoding="utf-8"))
    records = [normalize_arxiv_global(item, "arxiv/papers.json") for item in data if isinstance(item, dict)]
    records = [r for r in records if r["title"] or r["text"]]
    return dedup(records)


if __name__ == "__main__":
    print("=== Processing global/topical corpus ===")

    by_source: dict[str, list[dict]] = {}

    for subdir, normalizer in SOURCE_DIRS.items():
        print(f"\nProcessing data/raw/{subdir}/ ...")
        records = process_dir(subdir, normalizer)
        if records:
            source = records[0]["source"]
            by_source.setdefault(source, []).extend(records)
            print(f"  -> {len(records)} valid records")

    print("\nProcessing data/raw/arxiv/papers.json ...")
    arxiv_records = process_arxiv_global()
    if arxiv_records:
        by_source.setdefault("arxiv", []).extend(arxiv_records)
        print(f"  -> {len(arxiv_records)} valid records")

    total = 0
    for source, records in by_source.items():
        records = dedup(records)
        out_file = PROCESSED_DIR / f"global_{source}_{TODAY}.json"
        out_file.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[{source}] {len(records)} records -> {out_file.name}")
        total += len(records)

    print(f"\n=== Done: {total} total processed records across {len(by_source)} sources ===")
