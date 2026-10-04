"""
Fetch news & events from the GDELT 2.0 DOC API.

Queries are run per language (sourcelang) and per country (sourcecountry)
using the lists defined in regions.py — no unfiltered "global" default.

Output: data/raw/gdelt_<lang_or_country>_<date>.json (one file per query)
"""

import json
import time
from datetime import date, timedelta
from pathlib import Path

import requests

# ── project imports ────────────────────────────────────────────────────────
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from data.regions import LANGUAGES, ALL_COUNTRIES

# ── constants ──────────────────────────────────────────────────────────────
RAW_DIR = Path(__file__).parent / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
MAX_RECORDS = 25          # per query (stay well within rate limits)
LOOKBACK_DAYS = 7         # how far back to look
DELAY_SECONDS = 1.5       # polite pause between requests


def build_params(mode: str, query: str, extra: dict | None = None) -> dict:
    params = {
        "query": query,
        "mode": mode,
        "maxrecords": MAX_RECORDS,
        "format": "json",
        "startdatetime": (date.today() - timedelta(days=LOOKBACK_DAYS)).strftime("%Y%m%d") + "000000",
        "enddatetime": date.today().strftime("%Y%m%d") + "235959",
    }
    if extra:
        params.update(extra)
    return params


def fetch_articles(params: dict) -> list[dict]:
    """Call GDELT DOC API and return the article list (or empty list on error)."""
    try:
        resp = requests.get(BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("articles", [])
    except requests.RequestException as exc:
        print(f"  [GDELT] request error: {exc}")
        return []
    except ValueError:
        print("  [GDELT] JSON decode error")
        return []


def save(records: list[dict], label: str) -> None:
    if not records:
        return
    out_file = RAW_DIR / f"gdelt_{label}_{date.today().isoformat()}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"  → saved {len(records)} articles to {out_file.name}")


def fetch_by_languages() -> None:
    """One query per language edition (sourcelang filter)."""
    print("\n[GDELT] Fetching by language …")
    for lang_code, lang_name in LANGUAGES.items():
        print(f"  lang={lang_code} ({lang_name})")
        params = build_params(
            mode="ArtList",
            query=f'sourcelang:{lang_code} (AI OR "artificial intelligence" OR society OR culture OR technology)',
        )
        articles = fetch_articles(params)
        save(articles, f"lang_{lang_code}")
        time.sleep(DELAY_SECONDS)


def fetch_by_countries() -> None:
    """One query per country code (sourcecountry filter)."""
    print("\n[GDELT] Fetching by country …")
    for country_code, country_name in ALL_COUNTRIES.items():
        print(f"  country={country_code} ({country_name})")
        params = build_params(
            mode="ArtList",
            query=f'sourcecountry:{country_code}',
        )
        articles = fetch_articles(params)
        save(articles, f"country_{country_code}")
        time.sleep(DELAY_SECONDS)


if __name__ == "__main__":
    print("=== GDELT fetch started ===")
    fetch_by_languages()
    fetch_by_countries()
    print("\n=== GDELT fetch complete ===")
