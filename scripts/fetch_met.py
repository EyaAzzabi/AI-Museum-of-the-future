"""Pull public-domain artwork/artifacts from the Met Museum Open Access API into data/raw/met/.

Keyless. Chosen as a Wikimedia Commons replacement (blocked on this network) —
and thematically a better fit for a museum project than generic stock images.

The Met's `q=` search matches full-text across ALL metadata (including
provenance/exhibition notes), which produces false positives with no real
connection to the query term (confirmed: searching "Palestine" surfaced an
ancient Egyptian funerary text and a Mexican Posada print, neither of which
mention Palestine in any geographic field). `geoLocation=` is precise but too
sparse — it returns 0 results for Palestine/Tunisia/Morocco/Saudi
Arabia/Jordan/Brazil entirely. The fix here is a post-fetch relevance filter:
keep an object only if the search term actually appears in its own
title/culture/period/region/country/subregion fields, not just somewhere in
the API's full-text index.
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "met"

BASE = "https://collectionapi.metmuseum.org/public/collection/v1"

# Palestine explicitly included, not folded into a generic "Middle East" bucket.
SEARCH_TERMS = [
    "Palestine",
    "Egypt",
    "Tunisia",
    "Morocco",
    "Saudi Arabia",
    "Jordan",
    "India",
    "China",
    "Brazil",
    "France",
]

MAX_OBJECTS_PER_TERM = 3
MAX_CANDIDATES_SCANNED = 40  # how many search hits to check before giving up on a term


def get_json(url: str, retries: int = 3):
    req = urllib.request.Request(url, headers={"User-Agent": "ai-museum-of-the-future/0.1"})
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read())
        except Exception as e:
            last_err = e
            time.sleep(5)
    raise last_err


def is_actually_relevant(term: str, obj: dict) -> bool:
    """True only if the term appears in a real geographic/cultural field, not just anywhere in the API's full-text index."""
    haystack = " ".join(str(obj.get(f) or "") for f in
                         ("title", "culture", "period", "country", "region", "subregion", "locale")).lower()
    return term.lower() in haystack


def fetch_term(term: str) -> tuple[list[dict], int]:
    q = urllib.parse.urlencode({"q": term, "hasImages": "true"})
    search = get_json(f"{BASE}/search?{q}")
    candidate_ids = (search.get("objectIDs") or [])[:MAX_CANDIDATES_SCANNED]

    objects = []
    scanned = 0
    for obj_id in candidate_ids:
        if len(objects) >= MAX_OBJECTS_PER_TERM:
            break
        try:
            obj = get_json(f"{BASE}/objects/{obj_id}")
        except Exception as e:
            print(f"[met] object {obj_id} failed: {e}")
            continue
        scanned += 1
        if not is_actually_relevant(term, obj):
            continue
        objects.append({
            "id": obj.get("objectID"),
            "title": obj.get("title"),
            "culture": obj.get("culture"),
            "period": obj.get("period"),
            "date": obj.get("objectDate"),
            "medium": obj.get("medium"),
            "department": obj.get("department"),
            "image_url": obj.get("primaryImage"),
            "object_url": obj.get("objectURL"),
            "is_public_domain": obj.get("isPublicDomain"),
            "source": "met_museum",
            "query_term": term,
        })
        time.sleep(0.3)
    return objects, scanned


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []
    for term in SEARCH_TERMS:
        try:
            objects, scanned = fetch_term(term)
        except Exception as e:
            print(f"[met] FAILED term={term!r}: {e}")
            continue
        fname = f"{term.replace(' ', '_').lower()}.json"
        out_path = RAW_DIR / fname
        out_path.write_text(json.dumps(objects, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[met] term={term!r} -> {len(objects)}/{scanned} scanned passed relevance filter -> {out_path}")
        manifest.append({"term": term, "count": len(objects), "candidates_scanned": scanned, "file": fname})
        time.sleep(1)

    (RAW_DIR / "_manifest.json").write_text(
        json.dumps({"fetched_at": datetime.now(timezone.utc).isoformat(), "terms": manifest}, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
