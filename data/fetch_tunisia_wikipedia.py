"""Full-text Wikipedia articles about Tunisia 2020-2026, in English, French and Arabic.

Why: the corpus had almost no long text about Tunisia (about 75 chunks mention it,
most of them one-line headlines or World Bank statistics rows), while the museum's
scope is Tunisia 2020-2026. Encyclopedic articles are long, factual, sourced and
multilingual: exactly what passage retrieval needs, and they make the chunking
strategy matter.

How: a curated list of English article titles (politics, economy, society,
culture, environment of the period). For each, the full plain-text extract is
fetched through the official MediaWiki API (action=query&prop=extracts), and the
French and Arabic versions are found through the article's language links.
Section headings are kept on their own lines so paragraph-aware chunking can
use them. Missing titles are reported and skipped.

    python data/fetch_tunisia_wikipedia.py            # fetch + write data/processed/tunisia_wikipedia_<date>.json
    python data/fetch_tunisia_wikipedia.py --langs en # English only
    python data/fetch_tunisia_wikipedia.py --only "Four Daughters (2023 film)"   # some titles, separate file

Output records follow the shared processed schema (see data/README.md).
"""
from __future__ import annotations

import argparse
import json
import re
import time
from datetime import date
from pathlib import Path

import requests

HEADERS = {"User-Agent": "AIMuseumOfFuture/1.0 (academic project, Esprit 5DS; contact: ai-museum@example.com)"}
RAW_DIR = Path(__file__).resolve().parent / "raw" / "wikipedia_tunisia"
PROCESSED_DIR = Path(__file__).resolve().parent / "processed"
PAUSE_S = 0.5  # be polite to the API

# English title -> museum category. Chosen for the 2020-2026 period and the
# specialists' perspectives (history/society, economy, culture, technology/environment).
ARTICLES: dict[str, str] = {
    # politics and institutions
    "Tunisia": "history",
    "2021 Tunisian political crisis": "history",
    "2022 Tunisian constitutional referendum": "history",
    "2022–23 Tunisian parliamentary election": "history",
    "2024 Tunisian presidential election": "history",
    "Kais Saied": "history",
    "Constitution of Tunisia": "history",
    "Tunisian revolution": "history",
    "Ennahda Movement": "history",
    "Tunisian General Labour Union": "history",
    "Assembly of the Representatives of the People": "history",
    "Human rights in Tunisia": "history",
    # economy and society
    "Economy of Tunisia": "economy",
    "COVID-19 pandemic in Tunisia": "society",
    "Women in Tunisia": "society",
    "Education in Tunisia": "society",
    "Tunisians": "society",
    "Tunisian diaspora": "society",
    "Demographics of Tunisia": "society",
    # culture
    "Culture of Tunisia": "culture",
    "Cinema of Tunisia": "culture",
    "Carthage Film Festival": "culture",
    "Kaouther Ben Hania": "culture",
    "Four Daughters (2023 film)": "culture",
    "The Man Who Sold His Skin": "culture",
    "Music of Tunisia": "culture",
    "Tunisian literature": "culture",
    "Tunisian Arabic": "culture",
    # environment, energy, technology
    "Climate change in Tunisia": "science",
    "Energy in Tunisia": "science",
    "Water supply and sanitation in Tunisia": "science",
    "Telecommunications in Tunisia": "technology",
}


def _api(lang: str, **params) -> dict:
    url = f"https://{lang}.wikipedia.org/w/api.php"
    params = {"action": "query", "format": "json", "formatversion": 2, "redirects": 1, **params}
    response = requests.get(url, params=params, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_article(title: str, lang: str) -> dict | None:
    """Plain-text extract, URL, last-edit time and language links of one article."""
    data = _api(lang, titles=title, prop="extracts|info|langlinks", explaintext=1,
                exsectionformat="wiki", inprop="url", lllimit=500)
    pages = data.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing") or not pages[0].get("extract"):
        return None
    page = pages[0]
    return {
        "title": page["title"],
        "lang": lang,
        "url": page.get("fullurl"),
        "touched": page.get("touched"),
        "extract": page["extract"],
        "langlinks": {link["lang"]: link["title"] for link in page.get("langlinks", [])},
    }


def clean_extract(text: str) -> str:
    """Drop reference-only sections and empty headings, keep headings as their own paragraphs."""
    cut = re.split(r"\n==\s*(References|Notes|See also|External links|Further reading|Bibliography|"
                   r"Références|Notes et références|Voir aussi|Liens externes|Bibliographie|"
                   r"المراجع|مراجع|انظر أيضا|وصلات خارجية|مصادر)\s*==", text)[0]
    cut = re.sub(r"\n(={2,})\s*(.*?)\s*\1\n", lambda m: f"\n\n{m.group(2)}\n\n", cut)
    return re.sub(r"\n{3,}", "\n\n", cut).strip()


def to_record(article: dict, category: str, english_title: str) -> dict:
    slug = re.sub(r"\W+", "_", english_title.lower()).strip("_")
    return {
        "id": f"wikipedia:{article['lang']}:{article['title']}",
        "source": "wikipedia",
        "category": category,
        "title": article["title"],
        "text": clean_extract(article["extract"]),
        "url": article["url"],
        "image_url": None,
        "date": (article.get("touched") or "")[:10] or None,  # last edit: the article covers the period up to then
        "lang": article["lang"],
        "tags": ["tunisia", "2020-2026", f"topic:{slug}", "full_text"],
        "raw_source": f"wikipedia_tunisia_{article['lang']}",
        "processed_on": date.today().isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--langs", nargs="+", default=["en", "fr", "ar"])
    parser.add_argument("--only", nargs="+", metavar="TITLE", help="fetch only these English titles (from ARTICLES)")
    args = parser.parse_args()
    articles = {t: c for t, c in ARTICLES.items() if not args.only or t in args.only}

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    records, missing = [], []
    for english_title, category in articles.items():
        english = fetch_article(english_title, "en")
        time.sleep(PAUSE_S)
        if english is None:
            missing.append(english_title)
            continue
        found = {"en": english}
        for lang in args.langs:
            if lang == "en" or lang not in english["langlinks"]:
                continue
            article = fetch_article(english["langlinks"][lang], lang)
            time.sleep(PAUSE_S)
            if article:
                found[lang] = article
        for lang, article in found.items():
            if lang in args.langs:
                records.append(to_record(article, category, english_title))
        sizes = ", ".join(f"{lang} {len(article['extract']):,} chars" for lang, article in found.items())
        print(f"  {english_title}: {sizes}")

    stamp = date.today().isoformat()
    (RAW_DIR / f"articles_{stamp}{'_extra' if args.only else ''}.json").write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
    suffix = "_extra" if args.only else ""
    out = PROCESSED_DIR / f"tunisia_wikipedia_{stamp}{suffix}.json"
    out.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
    chars = sum(len(r["text"]) for r in records)
    print(f"\n{len(records)} articles, {chars:,} characters -> {out}")
    if missing:
        print(f"Not found ({len(missing)}): {', '.join(missing)}")


if __name__ == "__main__":
    main()
