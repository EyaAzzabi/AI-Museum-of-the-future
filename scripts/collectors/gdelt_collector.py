"""
GDELT Collector — AI Museum of the Future
==========================================
Source      : GDELT 2.0 DOC API (https://api.gdeltproject.org/api/v2/doc/doc)
Coverage    : Tunisia-related news articles, 2020–2026
Languages   : English, French
Output      : data/raw/gdelt/gdelt_articles.json
Volume      : ~200 articles (light mode)

No API key required. Free & public.
"""

import json
import time
import requests
from datetime import datetime, timedelta
from pathlib import Path

# ── HTTP headers ──────────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": "AI-Museum-of-the-Future/1.0 (academic project) python-requests/2.32"
}

# ── Output directory ──────────────────────────────────────────────────────────
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "gdelt"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── GDELT DOC API base URL ────────────────────────────────────────────────────
GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"

# ── Search configuration ──────────────────────────────────────────────────────
# Queries cover all 5 thematic areas for Tunisia 2020-2026
QUERIES = [
    # Politics & Society
    {"query": "Tunisia politics society 2020 2021 2022 2023 2024",  "theme": "politics_society"},
    {"query": "Tunisie politique société constitution",              "theme": "politics_society"},
    # Economy
    {"query": "Tunisia economy IMF crisis unemployment",            "theme": "economy"},
    {"query": "Tunisie économie crise FMI inflation",               "theme": "economy"},
    # Culture & Arts
    {"query": "Tunisia culture arts cinema music",                  "theme": "culture_arts"},
    {"query": "Tunisie culture cinéma musique patrimoine",          "theme": "culture_arts"},
    # Science & Technology
    {"query": "Tunisia technology startups innovation research",    "theme": "science_tech"},
    {"query": "Tunisie technologie startups innovation",            "theme": "science_tech"},
    # Environment
    {"query": "Tunisia environment water drought climate",          "theme": "environment"},
    {"query": "Tunisie environnement eau sécheresse climat",        "theme": "environment"},
]

# Max articles per query (total ~200 for light mode)
MAX_PER_QUERY = 20


def fetch_gdelt_articles(query: str, theme: str, max_records: int = MAX_PER_QUERY) -> list[dict]:
    """
    Calls the GDELT DOC API for a given query and returns a list of article dicts.
    """
    params = {
        "query": query,
        "mode": "artlist",          # returns article list with metadata
        "maxrecords": max_records,
        "startdatetime": "20200101000000",
        "enddatetime": "20261231235959",
        "format": "json",
        "sort": "DateDesc",
    }

    try:
        response = requests.get(GDELT_DOC_API, params=params, timeout=30, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"  [ERROR] Request failed for query '{query}': {e}")
        return []
    except json.JSONDecodeError:
        print(f"  [ERROR] JSON decode failed for query '{query}'")
        return []

    articles = data.get("articles", [])
    if not articles:
        print(f"  [WARN] No articles returned for query: '{query}'")
        return []

    # Enrich each article with collection metadata
    enriched = []
    for art in articles:
        enriched.append({
            "source":       "gdelt",
            "theme":        theme,
            "query_used":   query,
            "collected_at": datetime.utcnow().isoformat(),
            "title":        art.get("title", ""),
            "url":          art.get("url", ""),
            "domain":       art.get("domain", ""),
            "language":     art.get("language", ""),
            "seendate":     art.get("seendate", ""),
            "socialimage":  art.get("socialimage", ""),
        })

    return enriched


def run():
    """Main collection loop — iterates over all queries and saves to JSON."""
    print("=" * 60)
    print("GDELT Collector — Tunisia 2020-2026")
    print("=" * 60)

    all_articles: list[dict] = []
    seen_urls: set[str] = set()

    for i, q in enumerate(QUERIES, start=1):
        print(f"\n[{i}/{len(QUERIES)}] Theme: {q['theme']}")
        print(f"  Query: {q['query']}")

        articles = fetch_gdelt_articles(q["query"], q["theme"])

        # Deduplicate by URL
        new_articles = [a for a in articles if a["url"] not in seen_urls]
        for a in new_articles:
            seen_urls.add(a["url"])

        all_articles.extend(new_articles)
        print(f"  Fetched: {len(articles)} | New (deduped): {len(new_articles)} | Total: {len(all_articles)}")

        # Be polite to the API — wait 6s between requests (limit: 1 req/5s)
        if i < len(QUERIES):
            time.sleep(6)

    # ── Save results ──────────────────────────────────────────────────────────
    output_file = OUTPUT_DIR / "gdelt_articles.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_articles, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print(f"✓ Done. {len(all_articles)} articles saved.")
    print(f"✓ Output: {output_file}")
    print("=" * 60)


if __name__ == "__main__":
    run()
