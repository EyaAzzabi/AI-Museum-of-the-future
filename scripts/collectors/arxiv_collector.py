"""
arXiv Collector — AI Museum of the Future
==========================================
Source      : arXiv API (http://export.arxiv.org/api/query)
Coverage    : Scientific papers related to Tunisia or by Tunisian researchers, 2020–2026
Languages   : English (arXiv is predominantly English)
Output      : data/raw/arxiv/arxiv_papers.json
Volume      : ~50 papers (light mode)

No API key required. Free & public.
Official docs: https://info.arxiv.org/help/api/index.html
"""

import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import requests

# ── Output directory ──────────────────────────────────────────────────────────
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "arxiv"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── arXiv API endpoint ────────────────────────────────────────────────────────
ARXIV_API = "http://export.arxiv.org/api/query"

# ── Namespaces used in arXiv Atom feed ───────────────────────────────────────
NS = {
    "atom":   "http://www.w3.org/2005/Atom",
    "arxiv":  "http://arxiv.org/schemas/atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
}

# ── Search queries ────────────────────────────────────────────────────────────
# Strategy: search by affiliation (Tunisia) + by topic relevant to the museum themes
# arXiv date filter uses submittedDate:[20200101 TO 20261231]
QUERIES = [
    # Tunisian affiliation — broad
    {
        "theme":   "science_tech",
        "search":  'affil:"Tunisia" AND submittedDate:[20200101 TO 20261231]',
        "max":     15,
    },
    # Tunisian affiliation — AI & technology
    {
        "theme":   "science_tech",
        "search":  'affil:"Tunisia" AND (ti:machine AND ti:learning) AND submittedDate:[20200101 TO 20261231]',
        "max":     10,
    },
    # North Africa / MENA region — climate & environment
    {
        "theme":   "environment",
        "search":  '(ti:Tunisia OR ti:Tunisian) AND (ti:climate OR ti:water OR ti:drought) AND submittedDate:[20200101 TO 20261231]',
        "max":     10,
    },
    # Socioeconomic studies on Tunisia
    {
        "theme":   "economy",
        "search":  '(ti:Tunisia OR abs:Tunisia) AND (ti:economic OR ti:unemployment OR ti:migration) AND submittedDate:[20200101 TO 20261231]',
        "max":     10,
    },
    # Cultural / social studies
    {
        "theme":   "culture_arts",
        "search":  '(ti:Tunisia OR abs:Tunisia) AND (ti:social OR ti:culture OR ti:gender) AND submittedDate:[20200101 TO 20261231]',
        "max":     10,
    },
]


def parse_arxiv_entry(entry: ET.Element) -> dict:
    """Parses a single arXiv Atom <entry> element into a dict."""

    def text(tag: str, ns_key: str = "atom") -> str:
        el = entry.find(f"{ns_key}:{tag}", NS)
        return el.text.strip() if el is not None and el.text else ""

    # Authors
    authors = [
        a.find("atom:name", NS).text.strip()
        for a in entry.findall("atom:author", NS)
        if a.find("atom:name", NS) is not None
    ]

    # Affiliations (not always present)
    affiliations = [
        a.find("arxiv:affiliation", NS).text.strip()
        for a in entry.findall("atom:author", NS)
        if a.find("arxiv:affiliation", NS) is not None
    ]

    # PDF link
    pdf_url = ""
    for link in entry.findall("atom:link", NS):
        if link.get("title") == "pdf":
            pdf_url = link.get("href", "")
            break

    # Categories
    categories = [
        c.get("term", "")
        for c in entry.findall("atom:category", NS)
    ]

    # Published date — keep only YYYY-MM-DD
    published_raw = text("published")
    published = published_raw[:10] if published_raw else ""

    return {
        "id":           text("id"),
        "title":        text("title").replace("\n", " "),
        "abstract":     text("summary").replace("\n", " "),
        "authors":      authors,
        "affiliations": affiliations,
        "published":    published,
        "categories":   categories,
        "pdf_url":      pdf_url,
    }


def fetch_arxiv_papers(query: str, theme: str, max_results: int = 10) -> list[dict]:
    """
    Calls the arXiv API for a given search query and returns parsed paper dicts.
    """
    params = {
        "search_query": query,
        "start":        0,
        "max_results":  max_results,
        "sortBy":       "submittedDate",
        "sortOrder":    "descending",
    }

    try:
        response = requests.get(ARXIV_API, params=params, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"  [ERROR] Request failed: {e}")
        return []

    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as e:
        print(f"  [ERROR] XML parse failed: {e}")
        return []

    entries = root.findall("atom:entry", NS)
    if not entries:
        print(f"  [WARN] No entries returned.")
        return []

    papers = []
    for entry in entries:
        parsed = parse_arxiv_entry(entry)
        if parsed["title"]:  # skip empty entries
            papers.append({
                "source":       "arxiv",
                "theme":        theme,
                "collected_at": datetime.utcnow().isoformat(),
                **parsed,
            })

    return papers


def run():
    """Main collection loop — fetches all queries and saves to JSON."""
    print("=" * 60)
    print("arXiv Collector — Tunisia 2020-2026")
    print("=" * 60)

    all_papers: list[dict] = []
    seen_ids: set[str] = set()

    for i, q in enumerate(QUERIES, start=1):
        print(f"\n[{i}/{len(QUERIES)}] Theme: {q['theme']}")
        print(f"  Query: {q['search'][:80]}...")

        papers = fetch_arxiv_papers(q["search"], q["theme"], q["max"])

        # Deduplicate by arXiv ID
        new_papers = [p for p in papers if p["id"] not in seen_ids]
        for p in new_papers:
            seen_ids.add(p["id"])

        all_papers.extend(new_papers)
        print(f"  Fetched: {len(papers)} | New (deduped): {len(new_papers)} | Total: {len(all_papers)}")

        # arXiv API asks for 3s delay between requests
        if i < len(QUERIES):
            time.sleep(3)

    # ── Save results ──────────────────────────────────────────────────────────
    output_file = OUTPUT_DIR / "arxiv_papers.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_papers, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print(f"✓ Done. {len(all_papers)} papers saved.")
    print(f"✓ Output: {output_file}")
    print("=" * 60)


if __name__ == "__main__":
    run()
