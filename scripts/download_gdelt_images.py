"""Download each GDELT article's real news photo (og:image meta tag) into data/raw/images/gdelt_news/.

Met Museum images are historical art by design, and Openverse pulls whatever
Flickr users happened to tag with a search term (old photos, protest
photography, etc.) — neither actually represents *today's* world. The GDELT
articles we already fetched are genuine 2026 news, so their featured images
are real, dated, current-event photography, tied to the same topics/regions
already curated. Reuses the article URLs from data/processed/gdelt_enriched/
(only ones we already confirmed are fetchable).

Uses `requests` rather than raw `urllib` — this machine's OS certificate
store is stale, which makes `urllib`'s TLS verification fail intermittently
across the many arbitrary news/CDN domains this script hits; `requests`
bundles its own current CA list via `certifi` and isn't affected.
"""

import json
import mimetypes
import re
import time
import urllib.parse
from pathlib import Path

import requests

ENRICHED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed" / "gdelt_enriched"
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "images" / "gdelt_news"

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
OG_IMAGE_RE = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)["\']',
    re.I,
)


def find_og_image(url: str) -> str | None:
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    m = OG_IMAGE_RE.search(r.text)
    if not m:
        return None
    return urllib.parse.urljoin(url, m.group(1))


def guess_extension(url: str, content_type: str | None) -> str:
    path_ext = Path(urllib.parse.urlparse(url).path).suffix.lower().split("?")[0]
    if path_ext and len(path_ext) <= 5:
        return path_ext
    if content_type:
        ext = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if ext:
            return ext
    return ".jpg"


def download_image(image_url: str, dest_stem: Path) -> Path | None:
    r = requests.get(image_url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    ext = guess_extension(image_url, r.headers.get("Content-Type"))
    dest = dest_stem.with_suffix(ext)
    dest.write_bytes(r.content)
    return dest


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []

    for topic_file in sorted(ENRICHED_DIR.glob("*.json")):
        if topic_file.name.startswith("_"):
            continue
        topic = topic_file.stem
        topic_dir = OUT_DIR / topic
        topic_dir.mkdir(exist_ok=True)

        articles = json.loads(topic_file.read_text(encoding="utf-8"))
        found, downloaded = 0, 0
        for a in articles:
            if not a.get("extraction_success"):
                continue
            article_url = a.get("url")
            article_id = str(abs(hash(article_url)))[:12]
            existing = list(topic_dir.glob(f"{article_id}.*"))
            if existing:
                found += 1
                downloaded += 1
                continue
            try:
                image_url = find_og_image(article_url)
                if image_url:
                    found += 1
                    dest = download_image(image_url, topic_dir / article_id)
                    if dest:
                        downloaded += 1
                        (topic_dir / f"{article_id}.json").write_text(
                            json.dumps({"article_url": article_url, "image_url": image_url, "title": a.get("title")}, ensure_ascii=False),
                            encoding="utf-8",
                        )
            except Exception as e:
                print(f"  [images] {article_url[:60]} FAILED: {e}")
            time.sleep(1)

        print(f"[images] topic={topic}: {downloaded}/{len(articles)} images downloaded ({found} og:image tags found)")
        manifest.append({"topic": topic, "attempted": len(articles), "found": found, "downloaded": downloaded})

    (OUT_DIR / "_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
