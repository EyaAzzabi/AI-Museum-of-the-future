# Data

Public, accessible sources only (no full-internet crawling). Candidate sources per category:

- **News & events** — GDELT 2.0 DOC API (keyless)
- **Images & media** — Wikimedia Commons API (keyless)
- **Science & research** — arXiv API (keyless), NASA Open APIs (optional, free key)
- **Social & cultural trends** — Wikipedia Pageviews API (keyless) — used instead of Google Trends, which has no official API and relies on scraping an internal endpoint (`pytrends`), too fragile/unreliable for a graded corpus
- **Historical context** — Wikipedia REST API + Wikidata SPARQL (keyless)
- **Public statistics** — World Bank Open Data API (keyless; includes Tunisia and the project's covered countries)

All of the above are official JSON APIs, not HTML scraping, and require no signup except the optional NASA key.

## Global coverage, not just US/Europe

Left to their defaults, most of these APIs skew English/US/UK-heavy. `regions.py` defines the languages and countries every fetch script must explicitly query against instead of relying on a source's default results — with deliberate coverage of the Arab world (all 22 Arab League states) alongside other world regions (East/South Asia, Sub-Saharan Africa, Latin America, ...). Concretely:

- GDELT queries are run per `sourcelang`/`sourcecountry`, not just unfiltered
- Wikipedia/Wikidata pulls are run per language edition (`ar.wikipedia.org`, `fr.wikipedia.org`, ... not just `en.wikipedia.org`)
- Wikimedia Commons searches include region-specific categories (e.g. "Tunisia", "Egypt", "Middle East")
- World Bank/UNESCO queries include Arab League country codes explicitly

`raw/` holds unprocessed API/source pulls; `processed/` holds cleaned, deduplicated, structured output ready for chunking. Both are gitignored (only `.gitkeep` is tracked) — raw pulls and processed corpora should not be committed to the repo.

## Fetch scripts

| Script | Source | Key needed |
|---|---|---|
| `fetch_gdelt.py` | GDELT 2.0 DOC API — news & events per language/country | None |
| `fetch_wikimedia.py` | Wikimedia Commons — images per topic & region | None |
| `fetch_arxiv.py` | arXiv — recent papers across 10 research topics | None |
| `fetch_wikipedia.py` | Wikipedia Pageviews + REST summaries + Wikidata SPARQL | None |
| `fetch_worldbank.py` | World Bank population, GDP per capita, internet use, and CO2 indicators (2015-current year) | None |
| `process_raw.py` | Normalize & deduplicate all raw JSON → common schema | None |
| `fetch_all.py` | **Master script** — runs all fetches then processes | None |

### Run all sources

```bash
python data/fetch_all.py
```

### Run a specific source only

```bash
python data/fetch_all.py --sources gdelt
python data/fetch_all.py --sources arxiv wikipedia
python data/fetch_all.py --sources worldbank
python data/fetch_all.py --sources wikimedia --skip-process
```

### Run normalization only (on already-fetched raw data)

```bash
python data/process_raw.py
```

## Processed schema

Every source is normalized to this common structure before being handed off to the RAG chunking pipeline:

```json
{
  "id":           "unique identifier (URL, arXiv ID, Wikidata QID…)",
  "source":       "gdelt | wikimedia | arxiv | wikipedia | wikidata",
  "category":     "news | image | science | culture | history",
  "title":        "...",
  "text":         "main body (abstract / extract / description)",
  "url":          "...",
  "image_url":    "... or null",
  "date":         "ISO-8601 or null",
  "lang":         "ISO 639-1 code or null",
  "tags":         ["keyword", "category", "..."],
  "raw_source":   "original filename for traceability",
  "processed_on": "YYYY-MM-DD"
}
```
