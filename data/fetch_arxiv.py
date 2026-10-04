"""
Fetch science & research papers from the arXiv API.

Queries cover contemporary topics across AI, climate, social science, biology,
and more — the breadth a future historian would care about when representing
"what humans were working on" in the 2020s.

Output: data/raw/arxiv_<topic_slug>_<date>.json
"""

import json
import time
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

import requests

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

# ── constants ──────────────────────────────────────────────────────────────
RAW_DIR = Path(__file__).parent / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

ARXIV_API = "http://export.arxiv.org/api/query"
MAX_RESULTS = 20       # per query
DELAY_SECONDS = 3.0    # arXiv asks for 3 s between requests

# Namespace for Atom feed parsing
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}

# Topics that represent important research threads of the 2020s
TOPICS = [
    ("artificial_intelligence", "artificial intelligence deep learning"),
    ("climate_change", "climate change global warming mitigation"),
    ("pandemic_virology", "COVID pandemic virology epidemiology"),
    ("renewable_energy", "renewable energy solar wind battery"),
    ("large_language_models", "large language models GPT transformers"),
    ("social_media_society", "social media misinformation polarization society"),
    ("space_exploration", "space exploration Mars moon astronomy"),
    ("biotech_genomics", "CRISPR genomics synthetic biology"),
    ("inequality_economics", "economic inequality poverty development"),
    ("quantum_computing", "quantum computing qubit error correction"),
]


def fetch_papers(query: str, max_results: int = MAX_RESULTS) -> list[dict]:
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    url = f"{ARXIV_API}?{urlencode(params)}"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"  [arXiv] request error for '{query}': {exc}")
        return []

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as exc:
        print(f"  [arXiv] XML parse error: {exc}")
        return []

    papers = []
    for entry in root.findall("atom:entry", NS):
        def text(tag: str) -> str:
            el = entry.find(tag, NS)
            return el.text.strip() if el is not None and el.text else ""

        paper_id_url = text("atom:id")
        paper_id = paper_id_url.split("/abs/")[-1] if "/abs/" in paper_id_url else paper_id_url

        authors = [
            a.findtext("atom:name", namespaces=NS) or ""
            for a in entry.findall("atom:author", NS)
        ]

        categories = [
            c.get("term", "")
            for c in entry.findall("atom:category", NS)
        ]

        papers.append({
            "id": paper_id,
            "title": text("atom:title").replace("\n", " "),
            "summary": text("atom:summary").replace("\n", " "),
            "authors": authors,
            "published": text("atom:published"),
            "updated": text("atom:updated"),
            "categories": categories,
            "url": paper_id_url,
            "pdf_url": paper_id_url.replace("/abs/", "/pdf/"),
            "query": query,
            "fetched_on": date.today().isoformat(),
        })
    return papers


def save(records: list[dict], slug: str) -> None:
    if not records:
        return
    out_file = RAW_DIR / f"arxiv_{slug}_{date.today().isoformat()}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"  → saved {len(records)} papers to {out_file.name}")


if __name__ == "__main__":
    print("=== arXiv fetch started ===")
    for slug, query in TOPICS:
        print(f"  topic='{slug}'")
        papers = fetch_papers(query)
        save(papers, slug)
        time.sleep(DELAY_SECONDS)
    print("\n=== arXiv fetch complete ===")
