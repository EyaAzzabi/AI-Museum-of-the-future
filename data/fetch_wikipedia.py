"""
Fetch historical context and trending topics from:
  - Wikipedia REST API  (article summaries per language edition)
  - Wikipedia Pageviews API  (top-viewed articles = cultural zeitgeist signal)
  - Wikidata SPARQL  (structured facts about contemporary entities)

All queries run per language from regions.py for global coverage.

Output:
  data/raw/wikipedia_pageviews_<lang>_<date>.json
  data/raw/wikipedia_summaries_<lang>_<date>.json
  data/raw/wikidata_<topic>_<date>.json
"""

import json
import time
from datetime import date, timedelta
from pathlib import Path

import requests

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from data.regions import LANGUAGES

# ── constants ──────────────────────────────────────────────────────────────
RAW_DIR = Path(__file__).parent / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

DELAY_SECONDS = 1.0
PAGEVIEWS_TOP_N = 50    # top-N articles per language per day
SUMMARY_TOP_N = 20      # how many article summaries to pull per language

HEADERS = {"User-Agent": "AIMuseumOfFuture/1.0 (academic project; contact: ai-museum@example.com)"}


# ─────────────────────────────────────────────────────────────────────────────
# 1. Wikipedia Pageviews — top articles per language (cultural signal)
# ─────────────────────────────────────────────────────────────────────────────

def fetch_pageviews_top(lang: str, target_date: date | None = None) -> list[dict]:
    """Fetch the top-viewed Wikipedia articles for *lang* on *target_date*."""
    if target_date is None:
        target_date = date.today() - timedelta(days=1)   # yesterday (today not always ready)

    year, month, day = target_date.year, f"{target_date.month:02d}", f"{target_date.day:02d}"
    url = (
        f"https://wikimedia.org/api/rest_v1/metrics/pageviews/top"
        f"/{lang}.wikipedia/all-access/{year}/{month}/{day}"
    )
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        items = resp.json().get("items", [{}])[0].get("articles", [])
        return [
            {
                "rank": item.get("rank"),
                "article": item.get("article"),
                "views": item.get("views"),
                "lang": lang,
                "date": target_date.isoformat(),
                "fetched_on": date.today().isoformat(),
            }
            for item in items[:PAGEVIEWS_TOP_N]
            # Filter out meta-pages (Main_Page, Special:, etc.)
            if not item.get("article", "").startswith(("Main_Page", "Special:", "Wikipedia:", "Wikip"))
        ]
    except requests.RequestException as exc:
        print(f"  [Pageviews] error for lang={lang}: {exc}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# 2. Wikipedia REST API — article summaries for the top pages
# ─────────────────────────────────────────────────────────────────────────────

def fetch_article_summary(title: str, lang: str) -> dict | None:
    """Fetch the summary of a single Wikipedia article."""
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(title)}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        return {
            "title": data.get("title"),
            "display_title": data.get("displaytitle"),
            "description": data.get("description"),
            "extract": data.get("extract"),
            "thumbnail_url": (data.get("thumbnail") or {}).get("source"),
            "content_urls": data.get("content_urls", {}).get("desktop", {}).get("page"),
            "lang": lang,
            "page_id": data.get("pageid"),
            "fetched_on": date.today().isoformat(),
        }
    except requests.RequestException:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# 3. Wikidata SPARQL — structured facts about contemporary topics
# ─────────────────────────────────────────────────────────────────────────────

WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"
WIKIDATA_HEADERS = {
    **HEADERS,
    "Accept": "application/sparql-results+json",
}

SPARQL_QUERIES: dict[str, str] = {
    "contemporary_scientists": """
        SELECT ?person ?personLabel ?fieldLabel ?awardLabel WHERE {
          ?person wdt:P31 wd:Q5 ;
                  wdt:P106 wd:Q901 ;
                  wdt:P569 ?born .
          OPTIONAL { ?person wdt:P101 ?field . }
          OPTIONAL { ?person wdt:P166 ?award . }
          FILTER(YEAR(?born) >= 1970)
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fr,ar,es,zh" . }
        }
        LIMIT 50
    """,
    "recent_tech_companies": """
        SELECT ?company ?companyLabel ?countryLabel ?foundedYear WHERE {
          ?company wdt:P31 wd:Q4830453 ;
                   wdt:P571 ?founded ;
                   wdt:P17 ?country .
          BIND(YEAR(?founded) AS ?foundedYear)
          FILTER(?foundedYear >= 2010)
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fr,ar,es" . }
        }
        LIMIT 50
    """,
    "cultural_events_2020s": """
        SELECT ?event ?eventLabel ?dateLabel ?countryLabel WHERE {
          ?event wdt:P31 wd:Q1656682 ;
                 wdt:P585 ?date ;
                 wdt:P17 ?country .
          FILTER(YEAR(?date) >= 2020)
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ar,fr,es,zh" . }
        }
        ORDER BY DESC(?date)
        LIMIT 50
    """,
    "global_crises": """
        SELECT ?event ?eventLabel ?startLabel ?countryLabel WHERE {
          ?event wdt:P31/wdt:P279* wd:Q3839081 ;
                 wdt:P580 ?start .
          OPTIONAL { ?event wdt:P17 ?country . }
          FILTER(YEAR(?start) >= 2015)
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ar,fr,es,zh" . }
        }
        ORDER BY DESC(?start)
        LIMIT 50
    """,
}


def fetch_wikidata(query_name: str, sparql: str) -> list[dict]:
    try:
        resp = requests.get(
            WIKIDATA_ENDPOINT,
            params={"query": sparql, "format": "json"},
            headers=WIKIDATA_HEADERS,
            timeout=60,
        )
        resp.raise_for_status()
        bindings = resp.json().get("results", {}).get("bindings", [])
        # Flatten bindings: { "var": {"type": ..., "value": ...} } → { "var": "value" }
        return [
            {k: v.get("value", "") for k, v in row.items()}
            for row in bindings
        ]
    except requests.RequestException as exc:
        print(f"  [Wikidata] error for '{query_name}': {exc}")
        return []
    except ValueError:
        print(f"  [Wikidata] JSON decode error for '{query_name}'")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def save(records: list[dict], name: str) -> None:
    if not records:
        return
    out_file = RAW_DIR / f"{name}_{date.today().isoformat()}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"  → saved {len(records)} records to {out_file.name}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Wikipedia / Wikidata fetch started ===")

    # 1. Pageviews per language
    print("\n[Pageviews] Top articles by language …")
    for lang_code, lang_name in LANGUAGES.items():
        print(f"  lang={lang_code} ({lang_name})")
        pv_records = fetch_pageviews_top(lang_code)
        save(pv_records, f"wikipedia_pageviews_{lang_code}")
        time.sleep(DELAY_SECONDS)

    # 2. Article summaries for top pages (English only to keep volume manageable,
    #    but reusing the pageview results so we know what's actually popular)
    print("\n[Wikipedia REST] Article summaries for top English pages …")
    top_en = fetch_pageviews_top("en")
    summaries: list[dict] = []
    for item in top_en[:SUMMARY_TOP_N]:
        title = item["article"]
        print(f"  '{title}'")
        summary = fetch_article_summary(title, "en")
        if summary:
            summaries.append(summary)
        time.sleep(DELAY_SECONDS)
    save(summaries, "wikipedia_summaries_en")

    # 3. Wikidata SPARQL queries
    print("\n[Wikidata SPARQL] Structured facts …")
    for query_name, sparql in SPARQL_QUERIES.items():
        print(f"  query='{query_name}'")
        results = fetch_wikidata(query_name, sparql)
        save(results, f"wikidata_{query_name}")
        time.sleep(DELAY_SECONDS * 2)   # Wikidata is slower, be polite

    print("\n=== Wikipedia / Wikidata fetch complete ===")
