"""
Wikipedia Collector — AI Museum of the Future
=============================================
Source      : Wikipedia REST API (https://en.wikipedia.org/api/rest_v1/)
              + Wikipedia API (https://fr.wikipedia.org/w/api.php)
Coverage    : Tunisia-related articles, contemporary context 2020–2026
Languages   : English (en), French (fr)
Output      : data/raw/wikipedia/wikipedia_articles.json
Volume      : ~100 articles (light mode)

No API key required. Free & public.
"""

import json
import time
import requests
from datetime import datetime
from pathlib import Path

# ── HTTP headers — Wikipedia requires a descriptive User-Agent ────────────────
HEADERS = {
    "User-Agent": "AI-Museum-of-the-Future/1.0 (academic project) python-requests/2.32"
}

# ── Output directory ──────────────────────────────────────────────────────────
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "wikipedia"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Wikipedia API endpoints ───────────────────────────────────────────────────
WIKI_API = {
    "en": "https://en.wikipedia.org/w/api.php",
    "fr": "https://fr.wikipedia.org/w/api.php",
}

# ── Article titles to collect (by theme) ─────────────────────────────────────
# Manually curated list of relevant Wikipedia articles for Tunisia 2020-2026
ARTICLES = [
    # --- Politics & Society ---
    {"title": "Kais Saied",                                     "lang": "en", "theme": "politics_society"},
    {"title": "Constitution of Tunisia",                        "lang": "en", "theme": "politics_society"},
    {"title": "Human rights in Tunisia",                        "lang": "en", "theme": "politics_society"},
    {"title": "Politics of Tunisia",                            "lang": "en", "theme": "politics_society"},
    {"title": "Media of Tunisia",                               "lang": "en", "theme": "politics_society"},
    {"title": "Women in Tunisia",                               "lang": "en", "theme": "politics_society"},

    # --- Economy ---
    {"title": "Economy of Tunisia",                             "lang": "en", "theme": "economy"},
    {"title": "Tourism in Tunisia",                             "lang": "en", "theme": "economy"},
    {"title": "Agriculture in Tunisia",                         "lang": "en", "theme": "economy"},
    {"title": "Transport in Tunisia",                           "lang": "en", "theme": "economy"},
    {"title": "Tunisian dinar",                                 "lang": "en", "theme": "economy"},

    # --- Culture & Arts ---
    {"title": "Cinema of Tunisia",                              "lang": "en", "theme": "culture_arts"},
    {"title": "Music of Tunisia",                               "lang": "en", "theme": "culture_arts"},
    {"title": "Tunisian literature",                            "lang": "en", "theme": "culture_arts"},
    {"title": "Carthage Film Festival",                         "lang": "en", "theme": "culture_arts"},
    {"title": "Tunisian cuisine",                               "lang": "en", "theme": "culture_arts"},
    {"title": "Islam in Tunisia",                               "lang": "en", "theme": "culture_arts"},
    {"title": "Sport in Tunisia",                               "lang": "en", "theme": "culture_arts"},

    # --- Science & Technology ---
    {"title": "Telecommunications in Tunisia",                  "lang": "en", "theme": "science_tech"},
    {"title": "Education in Tunisia",                           "lang": "en", "theme": "science_tech"},
    {"title": "Information technology in Africa",               "lang": "en", "theme": "science_tech"},
    {"title": "Internet in Tunisia",                            "lang": "en", "theme": "science_tech"},

    # --- Environment ---
    {"title": "Climate change in Africa",                       "lang": "en", "theme": "environment"},
    {"title": "Environmental issues in Tunisia",                "lang": "en", "theme": "environment"},
    {"title": "Sahara",                                         "lang": "en", "theme": "environment"},
    {"title": "Chott el Djerid",                                "lang": "en", "theme": "environment"},
    {"title": "Water supply and sanitation in Tunisia",         "lang": "en", "theme": "environment"},

    # --- Historical context ---
    {"title": "Tunisia",                                        "lang": "en", "theme": "historical_context"},
    {"title": "Tunisian Revolution",                            "lang": "en", "theme": "historical_context"},
    {"title": "History of Tunisia",                             "lang": "en", "theme": "historical_context"},
    {"title": "Demographics of Tunisia",                        "lang": "en", "theme": "historical_context"},
    {"title": "Tunisian diaspora",                              "lang": "en", "theme": "historical_context"},
]


def fetch_wikipedia_article(title: str, lang: str, theme: str) -> dict | None:
    """
    Fetches the full extract of a Wikipedia article via the MediaWiki API.
    Returns a structured dict or None if the article is not found.
    """
    params = {
        "action":       "query",
        "prop":         "extracts|info|categories",
        "titles":       title,
        "exintro":      False,      # get full article, not just intro
        "explaintext":  True,       # plain text, no HTML
        "inprop":       "url",
        "cllimit":      10,
        "format":       "json",
        "redirects":    1,
    }

    try:
        response = requests.get(WIKI_API[lang], params=params, timeout=30, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"  [ERROR] Request failed for '{title}' ({lang}): {e}")
        return None
    except json.JSONDecodeError:
        print(f"  [ERROR] JSON decode failed for '{title}' ({lang})")
        return None

    pages = data.get("query", {}).get("pages", {})
    if not pages:
        return None

    page = next(iter(pages.values()))

    # -1 means page not found
    if page.get("pageid", -1) == -1:
        print(f"  [WARN] Article not found: '{title}' ({lang})")
        return None

    extract = page.get("extract", "").strip()
    if not extract:
        print(f"  [WARN] Empty extract for: '{title}' ({lang})")
        return None

    categories = [
        c.get("title", "").replace("Category:", "").replace("Catégorie:", "")
        for c in page.get("categories", [])
    ]

    return {
        "source":       "wikipedia",
        "theme":        theme,
        "lang":         lang,
        "collected_at": datetime.utcnow().isoformat(),
        "title":        page.get("title", title),
        "pageid":       page.get("pageid"),
        "url":          page.get("fullurl", f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}"),
        "categories":   categories,
        "text":         extract,
        "char_count":   len(extract),
        "word_count":   len(extract.split()),
    }


def run():
    """Main collection loop — fetches all articles and saves to JSON."""
    print("=" * 60)
    print("Wikipedia Collector — Tunisia 2020-2026")
    print("=" * 60)

    results: list[dict] = []
    failed: list[str] = []

    for i, article in enumerate(ARTICLES, start=1):
        title = article["title"]
        lang  = article["lang"]
        theme = article["theme"]

        print(f"\n[{i}/{len(ARTICLES)}] [{lang.upper()}] {title}")

        result = fetch_wikipedia_article(title, lang, theme)

        if result:
            results.append(result)
            print(f"  ✓ {result['word_count']} words — theme: {theme}")
        else:
            failed.append(f"{lang}:{title}")

        # Polite delay between requests
        if i < len(ARTICLES):
            time.sleep(1)

    # ── Save results ──────────────────────────────────────────────────────────
    output_file = OUTPUT_DIR / "wikipedia_articles.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"✓ Done. {len(results)} articles saved, {len(failed)} failed.")
    if failed:
        print(f"  Failed articles: {failed}")
    print(f"✓ Output: {output_file}")
    print("=" * 60)


if __name__ == "__main__":
    run()
