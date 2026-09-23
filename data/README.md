# Data

Public, accessible sources only (no full-internet crawling). Candidate sources per category:

- **News & events** — GDELT 2.0 DOC API (keyless)
- **Images & media** — Wikimedia Commons API (keyless)
- **Science & research** — arXiv API (keyless), NASA Open APIs (optional, free key)
- **Social & cultural trends** — Wikipedia Pageviews API (keyless) — used instead of Google Trends, which has no official API and relies on scraping an internal endpoint (`pytrends`), too fragile/unreliable for a graded corpus
- **Historical context** — Wikipedia REST API + Wikidata SPARQL (keyless)

All of the above are official JSON APIs, not HTML scraping, and require no signup except the optional NASA key.

## Global coverage, not just US/Europe

Left to their defaults, most of these APIs skew English/US/UK-heavy. `regions.py` defines the languages and countries every fetch script must explicitly query against instead of relying on a source's default results — with deliberate coverage of the Arab world (all 22 Arab League states) alongside other world regions (East/South Asia, Sub-Saharan Africa, Latin America, ...). Concretely:

- GDELT queries are run per `sourcelang`/`sourcecountry`, not just unfiltered
- Wikipedia/Wikidata pulls are run per language edition (`ar.wikipedia.org`, `fr.wikipedia.org`, ... not just `en.wikipedia.org`)
- Wikimedia Commons searches include region-specific categories (e.g. "Tunisia", "Egypt", "Middle East")
- World Bank/UNESCO queries include Arab League country codes explicitly

`raw/` holds unprocessed API/source pulls; `processed/` holds cleaned, deduplicated, structured output ready for chunking. Both are gitignored (only `.gitkeep` is tracked) — raw pulls and processed corpora should not be committed to the repo.
