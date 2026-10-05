"""Fetch and extract full article text for GDELT records into data/processed/gdelt_enriched/.

GDELT's DOC API only returns headline + URL + metadata, not article bodies —
too thin to chunk meaningfully for RAG. This visits each article's own URL
(already legitimately discovered via the GDELT API, not a fresh crawl) and
extracts clean article text with trafilatura, which handles arbitrary site
layouts across languages far better than hand-written HTML parsing.

Capped per topic (ARTICLES_PER_TOPIC) — extracting from all ~2,200 GDELT
records would take hours and hit many dead/paywalled/JS-only pages for
little gain. Records are already sorted by relevance (hybridrel), so taking
the top N per topic keeps the most relevant ones.
"""

import json
import time
from pathlib import Path

import trafilatura

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "gdelt"
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "processed" / "gdelt_enriched"

ARTICLES_PER_TOPIC = 15
FETCH_TIMEOUT = 15


def extract_one(article: dict) -> dict:
    url = article.get("url")
    text = None
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
    except Exception:
        text = None

    return {
        **article,
        "full_text": text,
        "full_text_chars": len(text) if text else 0,
        "extraction_success": bool(text),
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    topic_files = [f for f in sorted(RAW_DIR.glob("*.json")) if not f.name.startswith("_")]

    summary = []
    for topic_file in topic_files:
        out_path = OUT_DIR / topic_file.name
        if out_path.exists():
            continue

        articles = json.loads(topic_file.read_text(encoding="utf-8"))[:ARTICLES_PER_TOPIC]
        enriched = []
        for a in articles:
            enriched.append(extract_one(a))
            time.sleep(0.5)

        out_path.write_text(json.dumps(enriched, indent=2, ensure_ascii=False), encoding="utf-8")
        successes = sum(1 for e in enriched if e["extraction_success"])
        avg_chars = sum(e["full_text_chars"] for e in enriched) / len(enriched) if enriched else 0
        print(f"[enrich] {topic_file.stem}: {successes}/{len(enriched)} extracted, avg {avg_chars:.0f} chars")
        summary.append({"topic": topic_file.stem, "attempted": len(enriched), "succeeded": successes})

    (OUT_DIR / "_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
