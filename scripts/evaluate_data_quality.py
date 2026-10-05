"""Quality pass over everything collected in data/raw/.

Not a formal retrieval evaluation (that comes after chunking/embedding,
per the Week 2 milestone) — this checks the raw pulls themselves are
usable: no duplicates, no missing fields, and real regional/language
spread rather than an accidental English/US skew.
"""

import json
from collections import Counter
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def load_json_files(source_dir: Path) -> list[dict]:
    records = []
    for f in sorted(source_dir.glob("*.json")):
        if f.name.startswith("_"):
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"  ! {f.name}: invalid JSON ({e})")
            continue
        if isinstance(data, list):
            records.extend(data)
        else:
            records.append(data)
    return records


def eval_arxiv(records: list[dict]) -> dict:
    seen_ids = Counter(r.get("id") for r in records)
    duplicates = sum(c - 1 for c in seen_ids.values() if c > 1)
    missing_summary = sum(1 for r in records if not (r.get("summary") or "").strip())
    missing_title = sum(1 for r in records if not (r.get("title") or "").strip())
    cat_counts = Counter(c for r in records for c in r.get("categories", []))
    lengths = [len(r.get("summary") or "") for r in records]
    dates = sorted(r.get("published") for r in records if r.get("published"))

    return {
        "count": len(records),
        "duplicates": duplicates,
        "missing_summary": missing_summary,
        "missing_title": missing_title,
        "avg_summary_length_chars": round(sum(lengths) / len(lengths), 1) if lengths else 0,
        "category_distribution": dict(cat_counts.most_common(10)),
        "date_range": [dates[0], dates[-1]] if dates else None,
    }


def eval_gdelt(records: list[dict]) -> dict:
    seen_urls = Counter(r.get("url") for r in records)
    duplicates = sum(c - 1 for c in seen_urls.values() if c > 1)
    missing_title = sum(1 for r in records if not (r.get("title") or "").strip())
    missing_url = sum(1 for r in records if not (r.get("url") or "").strip())
    lang_counts = Counter(r.get("language") for r in records)
    country_counts = Counter(r.get("sourcecountry") for r in records)
    dates = sorted(r.get("seendate") for r in records if r.get("seendate"))

    return {
        "count": len(records),
        "duplicates": duplicates,
        "missing_title": missing_title,
        "missing_url": missing_url,
        "language_distribution": dict(lang_counts.most_common(15)),
        "sourcecountry_distribution": dict(country_counts.most_common(15)),
        "date_range": [dates[0], dates[-1]] if dates else None,
    }


def eval_met(records: list[dict]) -> dict:
    seen_ids = Counter(r.get("id") for r in records)
    duplicates = sum(c - 1 for c in seen_ids.values() if c > 1)
    missing_image = sum(1 for r in records if not r.get("image_url"))
    term_counts = Counter(r.get("query_term") for r in records)
    culture_counts = Counter(r.get("culture") for r in records if r.get("culture"))

    return {
        "count": len(records),
        "duplicates": duplicates,
        "missing_image_url": missing_image,
        "query_term_distribution": dict(term_counts),
        "culture_distribution": dict(culture_counts.most_common(10)),
    }


def eval_openverse(records: list[dict]) -> dict:
    seen_ids = Counter(r.get("id") for r in records)
    duplicates = sum(c - 1 for c in seen_ids.values() if c > 1)
    missing_url = sum(1 for r in records if not r.get("url"))
    term_counts = Counter(r.get("query_term") for r in records)
    license_counts = Counter(r.get("license") for r in records)

    return {
        "count": len(records),
        "duplicates": duplicates,
        "missing_url": missing_url,
        "query_term_distribution": dict(term_counts),
        "license_distribution": dict(license_counts),
    }


def eval_dbpedia(records: list[dict]) -> dict:
    missing_label = sum(1 for r in records if not r.get("label"))
    missing_abstract = sum(1 for r in records if not r.get("abstract"))
    empty_categories = sum(1 for r in records if not r.get("categories"))
    cat_counts = [len(r.get("categories") or []) for r in records]

    return {
        "count": len(records),
        "entities": [r.get("entity") for r in records],
        "missing_label": missing_label,
        "missing_abstract": missing_abstract,
        "note": "abstract is expected to be missing for all — DBpedia's live endpoint has no dbo:abstract/rdfs:comment triples for these entities, confirmed via direct SPARQL, not a parsing gap",
        "empty_categories": empty_categories,
        "avg_categories_per_entity": round(sum(cat_counts) / len(cat_counts), 1) if cat_counts else 0,
    }


def eval_archive(records: list[dict]) -> dict:
    seen_ids = Counter(r.get("identifier") for r in records)
    duplicates = sum(c - 1 for c in seen_ids.values() if c > 1)
    missing_title = sum(1 for r in records if not r.get("title"))
    term_counts = Counter(r.get("query_term") for r in records)
    mediatype_counts = Counter(r.get("mediatype") for r in records)

    return {
        "count": len(records),
        "duplicates": duplicates,
        "missing_title": missing_title,
        "query_term_distribution": dict(term_counts),
        "mediatype_distribution": dict(mediatype_counts),
    }


def eval_trends(records: list[dict]) -> dict:
    # each "record" here is actually one topic's timeline (a list of series);
    # load_json_files appends it as a single list item since the file's top
    # level is a list already, so records is a flat list of series dicts.
    total_points = sum(len(series.get("data", [])) for series in records)
    empty_series = sum(1 for series in records if not series.get("data"))

    return {
        "series_count": len(records),
        "total_data_points": total_points,
        "empty_series": empty_series,
    }


EVALUATORS = {
    "arxiv": eval_arxiv,
    "gdelt": eval_gdelt,
    "met": eval_met,
    "openverse": eval_openverse,
    "dbpedia": eval_dbpedia,
    "archive": eval_archive,
    "trends": eval_trends,
}


def main():
    report = {}
    for source_dir in sorted(RAW_DIR.iterdir()):
        if not source_dir.is_dir():
            continue
        source = source_dir.name
        records = load_json_files(source_dir)
        evaluator = EVALUATORS.get(source)
        if evaluator is None:
            report[source] = {"count": len(records), "note": "no evaluator defined for this source"}
            continue
        report[source] = evaluator(records)

    out_path = RAW_DIR.parent / "processed" / "quality_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nWritten to {out_path}")


if __name__ == "__main__":
    main()
