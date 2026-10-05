"""Pull CC-licensed images from the Openverse API into data/raw/openverse/.

Keyless. Broader complement to the Met Museum fetch (aggregates Flickr,
museums, etc.) — another Wikimedia Commons replacement.

Searches both region names (for geographic representation) and topics
(for subject diversity) — a region-only search skews toward whatever's
incidentally tagged with a country name (e.g. Palestine came back almost
entirely as Western protest photography, not everyday life/culture), so
explicit topic terms are needed to get real coverage of culture, sports,
economy, etc.
"""

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "data"))
from topics import ALL_TOPICS, DEDICATED_EVENT_TOPICS  # noqa: E402
from regions import ALL_COUNTRIES  # noqa: E402

RAW_DIR = REPO_ROOT / "data" / "raw" / "openverse"

BASE = "https://api.openverse.org/v1/images/"

# All 36 countries from data/regions.py (22 Arab League states + 14 other
# global countries) — genuine worldwide coverage, not just a curated subset.
REGION_TERMS = list(ALL_COUNTRIES.values())

SEARCH_TERMS = REGION_TERMS + ALL_TOPICS + DEDICATED_EVENT_TOPICS

RESULTS_PER_TERM = 10


def fetch_term(term: str, retries: int = 3) -> list[dict]:
    q = urllib.parse.urlencode({"q": term, "page_size": RESULTS_PER_TERM, "license_type": "commercial,modification"})
    url = f"{BASE}?{q}"
    req = urllib.request.Request(url, headers={"User-Agent": "ai-museum-of-the-future/0.1"})

    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read())
                break
        except Exception as e:
            last_err = e
            time.sleep(8)
    else:
        raise last_err

    results = []
    for item in data.get("results", []):
        results.append({
            "id": item.get("id"),
            "title": item.get("title"),
            "creator": item.get("creator"),
            "url": item.get("url"),
            "thumbnail": item.get("thumbnail"),
            "license": item.get("license"),
            "license_url": item.get("license_url"),
            "source": "openverse",
            "provider": item.get("provider"),
            "tags": [t.get("name") for t in (item.get("tags") or [])],
            "query_term": term,
        })
    return results


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []
    pending = [t for t in SEARCH_TERMS if not (RAW_DIR / f"{t.replace(' ', '_').lower()}.json").exists()]
    print(f"[openverse] {len(SEARCH_TERMS) - len(pending)} terms already fetched, {len(pending)} pending")

    for term in pending:
        try:
            results = fetch_term(term)
        except Exception as e:
            print(f"[openverse] FAILED term={term!r}: {e}")
            continue
        fname = f"{term.replace(' ', '_').lower()}.json"
        out_path = RAW_DIR / fname
        out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[openverse] term={term!r} -> {len(results)} images -> {out_path}")
        manifest.append({"term": term, "count": len(results), "file": fname})
        time.sleep(2)

    manifest_path = RAW_DIR / "_manifest.json"
    existing_terms = []
    if manifest_path.exists():
        existing_terms = json.loads(manifest_path.read_text(encoding="utf-8")).get("terms", [])
    seen = {t["term"] for t in manifest}
    merged = manifest + [t for t in existing_terms if t["term"] not in seen]

    manifest_path.write_text(
        json.dumps({"fetched_at": datetime.now(timezone.utc).isoformat(), "terms": merged}, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
