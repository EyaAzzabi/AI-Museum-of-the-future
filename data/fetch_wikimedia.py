"""
Fetch images & media from the Wikimedia Commons API.

Searches are run per region/topic keyword to avoid the default US/Europe bias.
Each result includes the image URL, title, description, and metadata.

Output: data/raw/wikimedia_<category>_<date>.json
"""

import json
import time
from datetime import date
from pathlib import Path

import requests

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from data.regions import ARAB_WORLD_COUNTRIES, OTHER_GLOBAL_COUNTRIES

# ── constants ──────────────────────────────────────────────────────────────
RAW_DIR = Path(__file__).parent / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
MAX_IMAGES = 20       # per search query
DELAY_SECONDS = 1.0

# Topic keywords that capture contemporary culture across domains
GLOBAL_TOPICS = [
    "artificial intelligence",
    "climate change",
    "urban life 2020s",
    "renewable energy",
    "social media",
    "space exploration",
    "pandemic",
    "contemporary art",
]

# Region-specific search terms derived from the countries lists
REGION_TERMS = (
    [f"{country} culture" for country in list(ARAB_WORLD_COUNTRIES.values())[:10]]
    + [f"{country} contemporary" for country in list(OTHER_GLOBAL_COUNTRIES.values())[:8]]
)


def search_images(query: str, limit: int = MAX_IMAGES) -> list[dict]:
    """Search Wikimedia Commons for images matching *query*."""
    params = {
        "action": "query",
        "generator": "search",
        "gsrnamespace": 6,     # File namespace
        "gsrsearch": f"filetype:bitmap {query}",
        "gsrlimit": limit,
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata",
        "iiurlwidth": 800,
        "format": "json",
        "utf8": 1,
    }
    headers = {
        "User-Agent": "AIMuseumOfFuture/1.0 (academic project; https://github.com/ai-museum)",
    }
    try:
        resp = requests.get(COMMONS_API, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        pages = data.get("query", {}).get("pages", {})
        results = []
        for page in pages.values():
            info = page.get("imageinfo", [{}])[0]
            extmeta = info.get("extmetadata", {})
            results.append({
                "title": page.get("title", ""),
                "pageid": page.get("pageid"),
                "url": info.get("url", ""),
                "thumb_url": info.get("thumburl", ""),
                "width": info.get("width"),
                "height": info.get("height"),
                "mime": info.get("mime", ""),
                "description": extmeta.get("ImageDescription", {}).get("value", ""),
                "license": extmeta.get("LicenseShortName", {}).get("value", ""),
                "author": extmeta.get("Artist", {}).get("value", ""),
                "date_created": extmeta.get("DateTimeOriginal", {}).get("value", ""),
                "query": query,
                "fetched_on": date.today().isoformat(),
            })
        return results
    except requests.RequestException as exc:
        print(f"  [Wikimedia] request error for '{query}': {exc}")
        return []
    except ValueError:
        print(f"  [Wikimedia] JSON decode error for '{query}'")
        return []


def save(records: list[dict], label: str) -> None:
    if not records:
        return
    # Sanitize label for filename
    safe_label = label.replace(" ", "_").replace("/", "-")[:60]
    out_file = RAW_DIR / f"wikimedia_{safe_label}_{date.today().isoformat()}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"  → saved {len(records)} images to {out_file.name}")


if __name__ == "__main__":
    print("=== Wikimedia Commons fetch started ===")

    print("\n[Wikimedia] Fetching global topic images …")
    for topic in GLOBAL_TOPICS:
        print(f"  topic='{topic}'")
        images = search_images(topic)
        save(images, topic)
        time.sleep(DELAY_SECONDS)

    print("\n[Wikimedia] Fetching region-specific images …")
    for term in REGION_TERMS:
        print(f"  term='{term}'")
        images = search_images(term, limit=10)
        save(images, term)
        time.sleep(DELAY_SECONDS)

    print("\n=== Wikimedia Commons fetch complete ===")
