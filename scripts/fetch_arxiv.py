"""Pull recent papers from the arXiv API into data/raw/arxiv/.

arXiv is keyless. Research categories are inherently international, so no
per-country/language filtering is applied here (unlike the news/trends
fetchers) — see data/regions.py for where that filtering matters more.

Uses a single combined query (cat:A OR cat:B OR ...) rather than one request
per category: export.arxiv.org's rate limit allows one request through and
then 406s on anything for a while, even minutes apart, so back-to-back calls
are unreliable. One request avoids the problem entirely.
"""

import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "arxiv"

ATOM_NS = "{http://www.w3.org/2005/Atom}"

# A spread across categories relevant to a "state of our era" corpus.
CATEGORIES = [
    "cs.AI",            # artificial intelligence
    "cs.CY",            # computers and society
    "physics.soc-ph",   # social/cultural dynamics
    "q-bio.PE",         # population/ecology - climate-adjacent
]

MAX_RESULTS = 80


def fetch_combined(categories: list[str], max_results: int = MAX_RESULTS, retries: int = 5) -> bytes:
    search_query = " OR ".join(f"cat:{c}" for c in categories)
    query = urllib.parse.urlencode({
        "search_query": search_query,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": max_results,
    })
    url = f"https://export.arxiv.org/api/query?{query}"
    req = urllib.request.Request(url, headers={"User-Agent": "ai-museum-of-the-future/0.1"})

    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except Exception as e:
            last_err = e
            print(f"[arxiv] attempt {attempt + 1}/{retries} failed: {e}, backing off 30s")
            time.sleep(30)
    raise last_err


def parse_entries(body: bytes) -> list[dict]:
    root = ET.fromstring(body)
    entries = []
    for entry in root.findall(f"{ATOM_NS}entry"):
        entries.append({
            "id": entry.findtext(f"{ATOM_NS}id"),
            "title": (entry.findtext(f"{ATOM_NS}title") or "").strip(),
            "summary": (entry.findtext(f"{ATOM_NS}summary") or "").strip(),
            "published": entry.findtext(f"{ATOM_NS}published"),
            "updated": entry.findtext(f"{ATOM_NS}updated"),
            "authors": [
                a.findtext(f"{ATOM_NS}name")
                for a in entry.findall(f"{ATOM_NS}author")
            ],
            "categories": [
                c.attrib.get("term") for c in entry.findall(f"{ATOM_NS}category")
            ],
            "pdf_url": next(
                (
                    link.attrib.get("href")
                    for link in entry.findall(f"{ATOM_NS}link")
                    if link.attrib.get("title") == "pdf"
                ),
                None,
            ),
            "source": "arxiv",
        })
    return entries


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    body = fetch_combined(CATEGORIES)
    entries = parse_entries(body)

    out_path = RAW_DIR / "papers.json"
    out_path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[arxiv] combined query -> {len(entries)} papers -> {out_path}")

    (RAW_DIR / "_manifest.json").write_text(
        json.dumps({
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "categories": CATEGORIES,
            "count": len(entries),
            "file": "papers.json",
        }, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
