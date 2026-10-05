"""Fetch OCR/full text for Internet Archive "texts"-type items into data/processed/archive_enriched/.

The advancedsearch results only carry a short description, not the actual
document content. For mediatype=="texts" items, archive.org's item
metadata lists a DjVuTXT (OCR) file that can be downloaded directly —
this fetches that and truncates to a reasonable chunk-able length (some
OCR'd books run to megabytes of text).

Uses `requests` rather than raw `urllib` — this machine's OS certificate
store is stale, which makes `urllib`'s TLS verification fail intermittently
on archive.org (and other hosts); `requests` bundles its own current CA
list via `certifi` and isn't affected. Confirmed by direct A/B test: urllib
got 8/38 on this exact task, every failure a "certificate has expired" error.
"""

import json
import time
from pathlib import Path

import requests

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "archive"
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "processed" / "archive_enriched"

MAX_CHARS = 10000
HEADERS = {"User-Agent": "ai-museum-of-the-future/0.1"}


def get_text_file_url(identifier: str, retries: int = 3) -> str | None:
    url = f"https://archive.org/metadata/{identifier}"
    last_err = None
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.raise_for_status()
            data = r.json()
            break
        except Exception as e:
            last_err = e
            time.sleep(5)
    else:
        raise last_err

    for f in data.get("files", []):
        name = f.get("name", "")
        if name.endswith("_djvu.txt") or f.get("format") == "DjVuTXT":
            return f"https://archive.org/download/{identifier}/{name}"
    return None


def fetch_text(identifier: str, retries: int = 3) -> str | None:
    text_url = get_text_file_url(identifier)
    if not text_url:
        return None
    last_err = None
    for attempt in range(retries):
        try:
            r = requests.get(text_url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            return r.text[:MAX_CHARS]
        except Exception as e:
            last_err = e
            time.sleep(5)
    raise last_err


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    records = []
    for f in sorted(RAW_DIR.glob("*.json")):
        if f.name.startswith("_"):
            continue
        for r in json.loads(f.read_text(encoding="utf-8")):
            if r.get("mediatype") == "texts":
                records.append(r)

    print(f"[enrich-archive] {len(records)} texts-type items to process")

    enriched = []
    for r in records:
        identifier = r["identifier"]
        try:
            text = fetch_text(identifier)
        except Exception as e:
            print(f"[enrich-archive] {identifier} FAILED: {e}")
            text = None
        enriched.append({
            **r,
            "full_text": text,
            "full_text_chars": len(text) if text else 0,
            "extraction_success": bool(text),
        })
        print(f"[enrich-archive] {identifier}: {'ok, ' + str(len(text)) + ' chars' if text else 'no text file'}")
        time.sleep(1)

    (OUT_DIR / "texts_enriched.json").write_text(
        json.dumps(enriched, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    successes = sum(1 for e in enriched if e["extraction_success"])
    print(f"[enrich-archive] done: {successes}/{len(enriched)} succeeded")


if __name__ == "__main__":
    main()
