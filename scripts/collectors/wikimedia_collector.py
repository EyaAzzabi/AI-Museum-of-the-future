"""
Wikimedia Commons Collector — AI Museum of the Future
======================================================
Source      : Wikimedia Commons API (https://commons.wikimedia.org/w/api.php)
Coverage    : Tunisia-related images, contemporary context 2020–2026
Languages   : Metadata in English/French
Output      : data/raw/wikimedia/
              ├── wikimedia_images_metadata.json   (metadata for all images)
              └── images/                          (downloaded image files)
Volume      : ~100 images (light mode)

No API key required. Free & public. Images are under open licenses (CC).
Official docs: https://www.mediawiki.org/wiki/API:Main_page
"""

import json
import time
from datetime import datetime
from pathlib import Path

import requests

# ── HTTP headers — Wikimedia requires a descriptive User-Agent ────────────────
HEADERS = {
    "User-Agent": "AI-Museum-of-the-Future/1.0 (academic project) python-requests/2.32"
}

# ── Output directories ────────────────────────────────────────────────────────
OUTPUT_DIR  = Path(__file__).resolve().parents[2] / "data" / "raw" / "wikimedia"
IMAGES_DIR  = OUTPUT_DIR / "images"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# ── Wikimedia Commons API ─────────────────────────────────────────────────────
COMMONS_API = "https://commons.wikimedia.org/w/api.php"

# ── Search categories & queries (by theme) ───────────────────────────────────
# Each entry defines a category or search term with its theme
SEARCHES = [
    # Politics & Society
    {"query": "Tunisia politics",               "theme": "politics_society", "max": 10},
    {"query": "Kais Saied",                     "theme": "politics_society", "max": 8},

    # Economy
    {"query": "Tunisia economy port",           "theme": "economy",          "max": 8},
    {"query": "Tunisia market souq",            "theme": "economy",          "max": 8},

    # Culture & Arts
    {"query": "Tunisia festival culture",       "theme": "culture_arts",     "max": 10},
    {"query": "Tunisia music art",              "theme": "culture_arts",     "max": 8},
    {"query": "Medina Tunis",                   "theme": "culture_arts",     "max": 8},

    # Science & Technology
    {"query": "Tunisia university technology",  "theme": "science_tech",     "max": 8},
    {"query": "Tunisia solar energy",           "theme": "environment",      "max": 8},

    # Environment
    {"query": "Tunisia landscape desert",       "theme": "environment",      "max": 10},
    {"query": "Tunisia water lake drought",     "theme": "environment",      "max": 8},
    {"query": "Chott el Jerid",                 "theme": "environment",      "max": 8},

    # Historical context
    {"query": "Carthage ruins Tunisia",         "theme": "historical_context", "max": 8},
    {"query": "Tunisia people street life",     "theme": "politics_society", "max": 8},
]

# Accepted image MIME types
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif"}

# Max file size to download (5 MB)
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024


def search_commons_images(query: str, theme: str, max_results: int = 10) -> list[dict]:
    """
    Searches Wikimedia Commons for images matching a query.
    Returns a list of image metadata dicts.
    """
    params = {
        "action":       "query",
        "generator":    "search",
        "gsrsearch":    f"filetype:bitmap {query}",
        "gsrnamespace": 6,              # File namespace
        "gsrlimit":     max_results,
        "prop":         "imageinfo",
        "iiprop":       "url|size|mime|extmetadata",
        "iiurlwidth":   800,            # request a thumbnail at 800px width
        "format":       "json",
    }

    try:
        response = requests.get(COMMONS_API, params=params, timeout=30, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"  [ERROR] Request failed for '{query}': {e}")
        return []
    except json.JSONDecodeError:
        print(f"  [ERROR] JSON decode failed for '{query}'")
        return []

    pages = data.get("query", {}).get("pages", {})
    if not pages:
        return []

    results = []
    for page in pages.values():
        imageinfo_list = page.get("imageinfo", [])
        if not imageinfo_list:
            continue

        info = imageinfo_list[0]
        mime = info.get("mime", "")

        # Skip non-image or unsupported types
        if mime not in ALLOWED_MIME:
            continue

        # Skip very large files
        size = info.get("size", 0)
        if size > MAX_FILE_SIZE_BYTES:
            continue

        # Extract license from extmetadata
        extmeta = info.get("extmetadata", {})
        license_name  = extmeta.get("LicenseShortName", {}).get("value", "Unknown")
        description   = extmeta.get("ImageDescription",  {}).get("value", "")
        date_taken    = extmeta.get("DateTimeOriginal",   {}).get("value", "")
        artist        = extmeta.get("Artist",             {}).get("value", "")

        # Only use open/free licenses
        is_free = any(lic in license_name for lic in ["CC", "Public domain", "CC0", "GFDL"])
        if not is_free:
            continue

        results.append({
            "source":        "wikimedia_commons",
            "theme":         theme,
            "query_used":    query,
            "collected_at":  datetime.utcnow().isoformat(),
            "page_id":       page.get("pageid"),
            "title":         page.get("title", "").replace("File:", ""),
            "url":           info.get("url", ""),
            "thumb_url":     info.get("thumburl", info.get("url", "")),
            "mime":          mime,
            "width":         info.get("width", 0),
            "height":        info.get("height", 0),
            "size_bytes":    size,
            "license":       license_name,
            "artist":        artist,
            "description":   description,
            "date_taken":    date_taken,
            "commons_page":  f"https://commons.wikimedia.org/wiki/{page.get('title', '').replace(' ', '_')}",
        })

    return results


def download_image(url: str, filename: str) -> bool:
    """
    Downloads an image from a URL and saves it to the images directory.
    Returns True on success, False on failure.
    """
    output_path = IMAGES_DIR / filename

    # Skip if already downloaded
    if output_path.exists():
        return True

    try:
        response = requests.get(url, timeout=30, stream=True, headers=HEADERS)
        response.raise_for_status()

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True

    except requests.exceptions.RequestException as e:
        print(f"    [ERROR] Download failed for {filename}: {e}")
        return False


def sanitize_filename(title: str, page_id: int, mime: str) -> str:
    """Creates a safe filename from image title and page ID."""
    ext_map = {
        "image/jpeg": ".jpg",
        "image/png":  ".png",
        "image/webp": ".webp",
        "image/gif":  ".gif",
    }
    ext = ext_map.get(mime, ".jpg")

    # Sanitize: keep alphanumeric, spaces→underscores, limit length
    safe = "".join(c if c.isalnum() or c in "._- " else "_" for c in title)
    safe = safe.replace(" ", "_")[:60]
    return f"{page_id}_{safe}{ext}"


def run():
    """Main collection loop — searches, collects metadata, downloads images."""
    print("=" * 60)
    print("Wikimedia Commons Collector — Tunisia 2020-2026")
    print("=" * 60)

    all_metadata: list[dict] = []
    seen_ids: set[int] = set()
    downloaded = 0
    failed_downloads = 0

    for i, search in enumerate(SEARCHES, start=1):
        query = search["query"]
        theme = search["theme"]
        max_r = search["max"]

        print(f"\n[{i}/{len(SEARCHES)}] Theme: {theme}")
        print(f"  Query: '{query}' (max {max_r})")

        images = search_commons_images(query, theme, max_r)

        # Deduplicate by page_id
        new_images = [img for img in images if img["page_id"] not in seen_ids]
        for img in new_images:
            seen_ids.add(img["page_id"])

        print(f"  Found: {len(images)} | New (deduped): {len(new_images)}")

        # Download each image
        for img in new_images:
            filename = sanitize_filename(img["title"], img["page_id"], img["mime"])
            img["local_filename"] = filename

            success = download_image(img["thumb_url"], filename)
            if success:
                downloaded += 1
                print(f"    ✓ {filename}")
            else:
                failed_downloads += 1
                img["local_filename"] = None

        all_metadata.extend(new_images)

        # Polite delay between search requests
        if i < len(SEARCHES):
            time.sleep(1.5)

    # ── Save metadata ─────────────────────────────────────────────────────────
    metadata_file = OUTPUT_DIR / "wikimedia_images_metadata.json"
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(all_metadata, f, ensure_ascii=False, indent=2)

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"✓ Done.")
    print(f"  Total images in metadata : {len(all_metadata)}")
    print(f"  Successfully downloaded  : {downloaded}")
    print(f"  Failed downloads         : {failed_downloads}")
    print(f"✓ Metadata : {metadata_file}")
    print(f"✓ Images   : {IMAGES_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    run()
