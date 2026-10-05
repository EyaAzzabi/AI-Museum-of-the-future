"""Pull historical document/media metadata from the Internet Archive into data/raw/archive/.

Keyless. Complements DBpedia (structured facts) with primary-source-style
material (texts, images, audio, video) for the historical-context layer.

Searches both region names and topics — see fetch_openverse.py docstring
for why region-only search isn't enough for real subject coverage.
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

RAW_DIR = REPO_ROOT / "data" / "raw" / "archive"

BASE = "https://archive.org/advancedsearch.php"

# All 36 countries from data/regions.py (22 Arab League states + 14 other
# global countries) — genuine worldwide coverage, not just a curated subset.
REGION_TERMS = list(ALL_COUNTRIES.values())

SEARCH_TERMS = REGION_TERMS + ALL_TOPICS + DEDICATED_EVENT_TOPICS

RESULTS_PER_TERM = 15
FIELDS = ["identifier", "title", "description", "date", "mediatype", "creator", "subject"]


def fetch_term(term: str, retries: int = 3) -> list[dict]:
    params = [("q", term), ("rows", str(RESULTS_PER_TERM)), ("output", "json")]
    for f in FIELDS:
        params.append(("fl[]", f))
    url = f"{BASE}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "ai-museum-of-the-future/0.1"})

    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read())
                break
        except Exception as e:
            last_err = e
            time.sleep(6)
    else:
        raise last_err

    docs = data.get("response", {}).get("docs", [])
    results = []
    for d in docs:
        results.append({
            "identifier": d.get("identifier"),
            "title": d.get("title"),
            "description": d.get("description"),
            "date": d.get("date"),
            "mediatype": d.get("mediatype"),
            "creator": d.get("creator"),
            "subject": d.get("subject"),
            "url": f"https://archive.org/details/{d.get('identifier')}",
            "source": "internet_archive",
            "query_term": term,
        })
    return results


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []
    pending = [t for t in SEARCH_TERMS if not (RAW_DIR / f"{t.replace(' ', '_').lower()}.json").exists()]
    print(f"[archive] {len(SEARCH_TERMS) - len(pending)} terms already fetched, {len(pending)} pending")

    for term in pending:
        try:
            results = fetch_term(term)
        except Exception as e:
            print(f"[archive] FAILED term={term!r}: {e}")
            continue
        fname = f"{term.replace(' ', '_').lower()}.json"
        out_path = RAW_DIR / fname
        out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[archive] term={term!r} -> {len(results)} items -> {out_path}")
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
