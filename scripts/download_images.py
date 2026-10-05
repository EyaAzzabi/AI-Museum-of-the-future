"""Download the actual image files (not just URLs/metadata) referenced by
Openverse and Met Museum records into data/raw/images/.

Collection so far only stored links + metadata — fine for cataloging, but
the mandatory multimodal component needs real image bytes to run object
detection/scene analysis on. This downloads a working local copy now, so
there's something concrete to inspect/validate; more images (or re-fetches
of failures) can be added on demand once the multimodal pipeline's actual
needs are clearer.

Uses `requests` rather than raw `urllib` — this machine's OS certificate
store is stale, which makes `urllib`'s TLS verification fail intermittently
on some image CDN hosts; `requests` bundles its own current CA list via
`certifi` and isn't affected.
"""

import json
import mimetypes
import time
import urllib.parse
from pathlib import Path

import requests

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
OUT_DIR = RAW_DIR / "images"

TIMEOUT = 20
HEADERS = {"User-Agent": "ai-museum-of-the-future/0.1"}


def guess_extension(url: str, content_type: str | None) -> str:
    path_ext = Path(urllib.parse.urlparse(url).path).suffix.lower()
    if path_ext and len(path_ext) <= 5:
        return path_ext
    if content_type:
        ext = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if ext:
            return ext
    return ".jpg"


def download_one(url: str, dest_stem: Path, retries: int = 2) -> Path | None:
    last_err = None
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            r.raise_for_status()
            ext = guess_extension(url, r.headers.get("Content-Type"))
            dest = dest_stem.with_suffix(ext)
            dest.write_bytes(r.content)
            return dest
        except Exception as e:
            last_err = e
            time.sleep(2)
    print(f"    FAILED: {last_err}")
    return None


def download_openverse():
    src_dir = RAW_DIR / "openverse"
    out_dir = OUT_DIR / "openverse"
    out_dir.mkdir(parents=True, exist_ok=True)

    total, done, skipped = 0, 0, 0
    for f in sorted(src_dir.glob("*.json")):
        if f.name.startswith("_"):
            continue
        records = json.loads(f.read_text(encoding="utf-8"))
        for r in records:
            total += 1
            image_id = r.get("id")
            if not image_id:
                continue
            existing = list(out_dir.glob(f"{image_id}.*"))
            if existing:
                skipped += 1
                continue
            url = r.get("url") or r.get("thumbnail")
            if not url:
                continue
            dest = download_one(url, out_dir / image_id)
            if dest:
                done += 1
                print(f"  [openverse] {image_id} -> {dest.name}")
            time.sleep(0.3)

    print(f"[openverse] {done} downloaded, {skipped} already present, {total} total records")


def download_met():
    src_dir = RAW_DIR / "met"
    out_dir = OUT_DIR / "met"
    out_dir.mkdir(parents=True, exist_ok=True)

    total, done, skipped = 0, 0, 0
    for f in sorted(src_dir.glob("*.json")):
        if f.name.startswith("_"):
            continue
        records = json.loads(f.read_text(encoding="utf-8"))
        for r in records:
            total += 1
            obj_id = r.get("id")
            if not obj_id:
                continue
            existing = list(out_dir.glob(f"{obj_id}.*"))
            if existing:
                skipped += 1
                continue
            url = r.get("image_url")
            if not url:
                continue
            dest = download_one(url, out_dir / str(obj_id))
            if dest:
                done += 1
                print(f"  [met] {obj_id} -> {dest.name}")
            time.sleep(0.3)

    print(f"[met] {done} downloaded, {skipped} already present, {total} total records")


def main():
    download_openverse()
    download_met()


if __name__ == "__main__":
    main()
