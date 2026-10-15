"""Turn the full-text extractions into processed records that replace their headline versions.

scripts/enrich_gdelt_text.py and scripts/enrich_archive_text.py extracted the
full text of 360 GDELT articles and 38 Internet Archive items into
data/processed/gdelt_enriched/ and data/processed/archive_enriched/. Those
subfolders were never ingested (data/ingest.py reads data/processed/*.json),
so the knowledge base kept only the headline of each article: the median
document was 68 characters long.

This script writes data/processed/fulltext_<date>.json: one record per
successful extraction, with the SAME id as the headline record (the article
URL for GDELT, the identifier for the Internet Archive), so ingestion updates
those documents instead of duplicating them (data/ingest.py keeps the longest
text when an id appears twice). Other fields come from the headline record.

    python -m data.process_fulltext
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

PROCESSED_DIR = Path(__file__).resolve().parent / "processed"
MIN_CHARS = 300  # shorter extractions are cookie banners, paywalls or error pages


def _load(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = next((v for v in data.values() if isinstance(v, list)), [])
    return [r for r in data if isinstance(r, dict)]


def headline_records() -> dict[str, dict]:
    records: dict[str, dict] = {}
    for path in sorted(PROCESSED_DIR.glob("*.json")):
        if path.name.startswith(("fulltext_", "quality_report")):
            continue
        for record in _load(path):
            records.setdefault(str(record.get("id")), record)
    return records


def fulltext_records(headlines: dict[str, dict]) -> tuple[list[dict], dict]:
    from rag.dedupe_documents import text_key

    out: list[dict] = []
    seen_texts: set[str] = set()
    stats = {"gdelt_extracted": 0, "archive_extracted": 0, "too_short": 0, "no_headline_record": 0,
             "same_text_other_url": 0}

    def emit(record_id: str, text: str, base_fields: dict, kind: str) -> None:
        if len(text or "") < MIN_CHARS:
            stats["too_short"] += 1
            return
        if text_key(text) in seen_texts:  # same article under another URL or channel
            stats["same_text_other_url"] += 1
            return
        seen_texts.add(text_key(text))
        base = headlines.get(record_id)
        if base is None:
            stats["no_headline_record"] += 1
            base = base_fields
        out.append({
            **base,
            "id": record_id,
            "text": text.strip(),
            "tags": sorted(set((base.get("tags") or []) + ["full_text"])),
            "raw_source": f"{kind}_fulltext",
            "processed_on": date.today().isoformat(),
        })
        stats[f"{kind}_extracted"] += 1

    for path in sorted((PROCESSED_DIR / "gdelt_enriched").glob("*.json")):
        if path.name.startswith("_"):
            continue
        for article in _load(path):
            emit(article["url"], article.get("full_text") or "", {
                "source": "gdelt", "category": "news", "title": article.get("title"),
                "url": article["url"], "image_url": article.get("socialimage"),
                "date": article.get("seendate"), "lang": article.get("language"), "tags": [],
            }, "gdelt")

    for path in sorted((PROCESSED_DIR / "archive_enriched").glob("*.json")):
        for item in _load(path):
            emit(item["identifier"], item.get("full_text") or "", {
                "source": "internet_archive", "category": "history", "title": item.get("title"),
                "url": item.get("url"), "image_url": None, "date": item.get("date"), "lang": None, "tags": [],
            }, "archive")
    return out, stats


def main() -> None:
    records, stats = fulltext_records(headline_records())
    out = PROCESSED_DIR / f"fulltext_{date.today().isoformat()}.json"
    out.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
    chars = sum(len(r["text"]) for r in records)
    print(f"{len(records)} full-text records, {chars:,} characters -> {out}")
    print(stats)


if __name__ == "__main__":
    main()
