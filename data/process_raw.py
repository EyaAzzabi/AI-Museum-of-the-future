"""
Clean, deduplicate and normalize raw JSON files from data/raw/ into data/processed/.

Each source type has its own normalizer that maps heterogeneous API responses
to a common schema:

    {
        "id":          str,          # unique identifier (URL, arXiv ID, Wikidata QID…)
        "source":      str,          # "gdelt" | "wikimedia" | "arxiv" | "wikipedia" | "wikidata"
        "category":    str,          # top-level category (news, image, science, culture, history)
        "title":       str,
        "text":        str,          # main text body (abstract, extract, description…)
        "url":         str,
        "image_url":   str | None,
        "date":        str | None,   # ISO-8601 date string or empty
        "lang":        str | None,
        "tags":        list[str],    # keywords, categories, topics…
        "raw_source":  str,          # original filename for traceability
        "processed_on": str,         # ISO date when this record was processed
    }

Duplicates are detected by `id` within each processed file.
Output: data/processed/<source>_<date>.json
"""

import hashlib
import json
import re
from datetime import date
from pathlib import Path

# ── paths ──────────────────────────────────────────────────────────────────
RAW_DIR = Path(__file__).parent / "raw"
PROCESSED_DIR = Path(__file__).parent / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

TODAY = date.today().isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

def clean_text(text: str | None) -> str:
    """Strip HTML tags, collapse whitespace."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)          # remove HTML tags
    text = re.sub(r"\s+", " ", text).strip()       # collapse whitespace
    return text


def stable_id(*parts: str) -> str:
    """Generate a stable short hash when a natural ID is not available."""
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def dedup(records: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for rec in records:
        key = rec.get("id", "")
        if key and key not in seen:
            seen.add(key)
            out.append(rec)
        elif not key:
            out.append(rec)   # keep records without an id (shouldn't happen)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Source-specific normalizers
# ─────────────────────────────────────────────────────────────────────────────

def normalize_gdelt(raw: dict, source_file: str) -> dict:
    url = raw.get("url", "")
    return {
        "id": url or stable_id(raw.get("title", ""), raw.get("seendate", "")),
        "source": "gdelt",
        "category": "news",
        "title": clean_text(raw.get("title", "")),
        "text": clean_text(raw.get("title", "")),   # GDELT DOC API returns title only
        "url": url,
        "image_url": raw.get("socialimage"),
        "date": raw.get("seendate", "")[:8] or None,  # YYYYMMDDHHMMSS → YYYYMMDD
        "lang": raw.get("language"),
        "tags": [raw.get("domain", ""), raw.get("sourcecountry", "")],
        "raw_source": source_file,
        "processed_on": TODAY,
    }


def normalize_wikimedia(raw: dict, source_file: str) -> dict:
    url = raw.get("url", "")
    return {
        "id": url or stable_id(raw.get("title", "")),
        "source": "wikimedia",
        "category": "image",
        "title": clean_text(raw.get("title", "")),
        "text": clean_text(raw.get("description", "")),
        "url": raw.get("url", ""),
        "image_url": raw.get("thumb_url") or raw.get("url"),
        "date": raw.get("date_created", "") or None,
        "lang": None,
        "tags": [raw.get("license", ""), raw.get("query", "")],
        "raw_source": source_file,
        "processed_on": TODAY,
    }


def normalize_arxiv(raw: dict, source_file: str) -> dict:
    return {
        "id": raw.get("id", stable_id(raw.get("title", ""))),
        "source": "arxiv",
        "category": "science",
        "title": clean_text(raw.get("title", "")),
        "text": clean_text(raw.get("summary", "")),
        "url": raw.get("url", ""),
        "image_url": None,
        "date": raw.get("published", "")[:10] or None,
        "lang": "en",
        "tags": raw.get("categories", []),
        "raw_source": source_file,
        "processed_on": TODAY,
    }


def normalize_wikipedia_pageviews(raw: dict, source_file: str) -> dict:
    article = raw.get("article", "")
    lang = raw.get("lang", "en")
    return {
        "id": stable_id(lang, article, raw.get("date", "")),
        "source": "wikipedia",
        "category": "culture",
        "title": article.replace("_", " "),
        "text": "",    # pageviews only — summaries are fetched separately
        "url": f"https://{lang}.wikipedia.org/wiki/{article}",
        "image_url": None,
        "date": raw.get("date"),
        "lang": lang,
        "tags": [f"rank:{raw.get('rank')}", f"views:{raw.get('views')}"],
        "raw_source": source_file,
        "processed_on": TODAY,
    }


def normalize_wikipedia_summary(raw: dict, source_file: str) -> dict:
    return {
        "id": str(raw.get("page_id", stable_id(raw.get("title", "")))),
        "source": "wikipedia",
        "category": "history",
        "title": clean_text(raw.get("title", "")),
        "text": clean_text(raw.get("extract", "")),
        "url": raw.get("content_urls", ""),
        "image_url": raw.get("thumbnail_url"),
        "date": None,
        "lang": raw.get("lang", "en"),
        "tags": [raw.get("description", "")],
        "raw_source": source_file,
        "processed_on": TODAY,
    }


def normalize_wikidata(raw: dict, source_file: str) -> dict:
    # Wikidata bindings: keys vary per query; use label fields when available
    label = raw.get("personLabel") or raw.get("companyLabel") or raw.get("eventLabel") or ""
    entity_url = raw.get("person") or raw.get("company") or raw.get("event") or ""
    return {
        "id": entity_url or stable_id(label, source_file),
        "source": "wikidata",
        "category": "history",
        "title": clean_text(label),
        "text": clean_text(
            raw.get("fieldLabel", "")
            or raw.get("countryLabel", "")
            or raw.get("dateLabel", "")
        ),
        "url": entity_url,
        "image_url": None,
        "date": raw.get("startLabel") or raw.get("dateLabel") or raw.get("foundedYear") or None,
        "lang": None,
        "tags": [v for v in raw.values() if isinstance(v, str) and not v.startswith("http")],
        "raw_source": source_file,
        "processed_on": TODAY,
    }


def normalize_worldbank(raw: dict, source_file: str) -> dict:
    country = raw.get("country") or {}
    indicator = raw.get("indicator") or {}
    country_code = country.get("iso2Code") or country.get("id") or raw.get("countryiso3code", "")
    indicator_id = indicator.get("id", "")
    country_name = clean_text(country.get("value", "Unknown country"))
    indicator_name = clean_text(indicator.get("value") or indicator_id)
    year = str(raw.get("date", ""))
    value = raw.get("value")
    record_id = f"{country_code}:{indicator_id}:{year}"

    return {
        "id": record_id if country_code and indicator_id and year else stable_id(source_file, str(raw)),
        "source": "worldbank",
        "category": "statistics",
        "title": f"{country_name} - {indicator_name} ({year})",
        "text": f"{indicator_name} for {country_name} in {year}: {value}.",
        "url": (
            f"https://api.worldbank.org/v2/country/"
            f"{raw.get('countryiso3code') or country_code}/indicator/{indicator_id}?date={year}"
        ),
        "image_url": None,
        "date": year or None,
        "lang": None,
        "tags": [f"indicator:{indicator_id}", f"country:{country_code}"],
        "raw_source": source_file,
        "processed_on": TODAY,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Dispatcher: detect source from filename and apply the right normalizer
# ─────────────────────────────────────────────────────────────────────────────

def get_normalizer(filename: str):
    name = filename.lower()
    if name.startswith("gdelt_"):
        return normalize_gdelt
    if name.startswith("wikimedia_"):
        return normalize_wikimedia
    if name.startswith("arxiv_"):
        return normalize_arxiv
    if name.startswith("wikipedia_pageviews_"):
        return normalize_wikipedia_pageviews
    if name.startswith("wikipedia_summaries_"):
        return normalize_wikipedia_summary
    if name.startswith("wikidata_"):
        return normalize_wikidata
    if name.startswith("worldbank_"):
        return normalize_worldbank
    return None


def process_file(raw_file: Path) -> list[dict]:
    normalizer = get_normalizer(raw_file.name)
    if normalizer is None:
        print(f"  [skip] no normalizer for {raw_file.name}")
        return []

    try:
        with open(raw_file, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"  [error] could not read {raw_file.name}: {exc}")
        return []

    if not isinstance(data, list):
        data = [data]

    records = [normalizer(item, raw_file.name) for item in data if isinstance(item, dict)]
    records = [r for r in records if r["title"] or r["text"]]   # drop empty records
    return dedup(records)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Processing raw data ===")

    raw_files = sorted(RAW_DIR.glob("*.json"))
    if not raw_files:
        print("No raw JSON files found. Run the fetch scripts first.")
        raise SystemExit(0)

    # Group processed records by source
    by_source: dict[str, list[dict]] = {}

    for raw_file in raw_files:
        print(f"\nProcessing {raw_file.name} …")
        records = process_file(raw_file)
        if records:
            source = records[0]["source"]
            by_source.setdefault(source, []).extend(records)
            print(f"  → {len(records)} valid records")

    # Write one processed file per source
    total = 0
    for source, records in by_source.items():
        records = dedup(records)   # global dedup within source
        out_file = PROCESSED_DIR / f"{source}_{TODAY}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        print(f"\n[{source}] {len(records)} records → {out_file.name}")
        total += len(records)

    print(f"\n=== Done: {total} total processed records across {len(by_source)} sources ===")
