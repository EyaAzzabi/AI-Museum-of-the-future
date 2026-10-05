# Data

Public, accessible sources only (no full-internet crawling, no HTML scraping — everything below is an official JSON API). Two parallel collection pipelines currently exist in this repo, covering different scope:

- **`scripts/fetch_*.py`** — broad, global/topical corpus (36 countries, 22+ topics, multiple sources). See "Global pipeline" below.
- **`data/fetch_*.py` + `data/process_raw.py` + `data/ingest.py`** — Tunisia 2020-2026 focused pipeline, already normalizing output into the schema the RAG chunking step consumes. See "Tunisia pipeline" below.

Both write to `data/raw/` (different filenames/subdirectories, no overwrite conflicts) and should be reconciled into one corpus before/during chunking rather than kept permanently separate — worth a team conversation on which becomes canonical.

## Tunisia pipeline (`data/`)

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

### Processed schema

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

**Note on Wikimedia access:** `fetch_wikipedia.py`/`fetch_wikimedia.py` use `requests`, which works around a stale-OS-certificate-store issue that makes raw `urllib` fail with "certificate has expired" errors against `wikimedia.org`-family domains on at least one team member's machine. If Wikimedia pulls fail for you with that exact error, see the global pipeline's note on this below — the fix is to use `requests`, not to treat the domain as blocked.

## Global pipeline (`scripts/`)

| Script | Source | Category | Key needed? |
|---|---|---|---|
| `fetch_gdelt.py` | GDELT 2.0 DOC API | News & events | No |
| `fetch_trends.py` | GDELT DOC API (`mode=timelinevol`) | Social & cultural trends | No |
| `fetch_arxiv.py` | arXiv API | Science & research | No |
| `fetch_met.py` | Met Museum Open Access API | Images & media (art/artifacts) | No |
| `fetch_openverse.py` | Openverse API | Images & media (general) | No |
| `fetch_archive.py` | Internet Archive `advancedsearch` API | Historical context (primary sources) | No |
| `fetch_dbpedia.py` | DBpedia (structured categories only, see below) | Historical context (structured facts) | No |

### Topics, not just regions

Early pulls only searched by **country name** (`data/regions.py`), which produces geographically-tagged but topically uncontrolled results — e.g. searching Openverse for "Palestine" returned almost entirely Western protest photography, not everyday life or culture, because that's what happens to be tagged with that name on Flickr. `data/topics.py` defines explicit subject topics so coverage isn't left to chance:

- **Science & Technology**: artificial intelligence, space exploration, climate change, innovation and startups, biotechnology and health, renewable energy
- **Culture & Media**: cultural heritage, arts and music, fashion, cinema and film, traditional crafts, architecture, literature, dance and performance, food and cuisine
- **Socio-Historical / social & economic trends**: social movements, economy, sports, migration and demographics, digital life and social media, gender and equality, conflict and peace

`fetch_gdelt.py`, `fetch_openverse.py`, `fetch_archive.py`, and `fetch_trends.py` all query this shared topic list. `fetch_met.py` and `fetch_dbpedia.py` stay region/entity-based (art-by-culture and country-facts respectively don't map cleanly onto these topics).

### Global coverage, not just US/Europe

Left to their defaults, most of these APIs skew English/US/UK-heavy. `data/regions.py` defines the languages and countries every region-based fetch script queries against explicitly — with deliberate coverage of the Arab world (all 22 Arab League states, Palestine included by name, not folded into a generic "Middle East" bucket) alongside 14 other global countries spanning every populated continent. Concretely:

- GDELT topic queries are run as `topic (sourcelang:X OR sourcelang:Y OR ...)` across 8 languages in a single request, not left unfiltered (English is deliberately *not* included as a `sourcelang` filter — GDELT tags translated non-English content with `sourcelang`, but native-English articles usually aren't tagged at all, so filtering by it would exclude English rather than include it)
- Openverse and Internet Archive search all 36 countries in `regions.py` (`ALL_COUNTRIES`), not a hand-picked subset
- Met Museum and DBpedia stay on a smaller curated subset (Palestine, Egypt, Tunisia, Morocco, Saudi Arabia, Jordan, India, China, Brazil, France) — Met because its low precision on modern country names (see below) makes scaling up low-value, DBpedia because it's a lighter-touch structured source not core to the "all the world" image/media push

### Known source limitations (found during collection, not hidden)

- **DBpedia has no `dbo:abstract`/`rdfs:comment` data on its live endpoint** for any entity tested (confirmed via direct SPARQL query, not a parsing bug) — it only yields structured categories, not descriptive prose. It also 500s reliably on very large entities (India, China, France) — a backend limitation, not fixable client-side.
- **Met Museum's `q=` search matches on full-text across all metadata** (including unrelated provenance/exhibition notes), producing false positives (an ancient Egyptian text and a Mexican print both "matched" a Brazil/Jordan/Morocco/Palestine search). `fetch_met.py` applies a post-fetch relevance filter, which fixes precision but reveals the collection is organized by historical/cultural period (Byzantine, Ottoman...) rather than modern country names — so yield for Tunisia/Morocco/Jordan/Saudi Arabia/Palestine/Brazil is very low (0-1 objects each) even after fixing the filter. Met is a minor supplementary image source, not the primary one.
- **GDELT's free API rate-limits aggressively and unpredictably** (429s, timeouts) from a single request on, independent of request volume. All GDELT fetch scripts use single combined queries (multiple languages/topics OR'd together) plus long retry/backoff, rather than many small sequential requests.
- **Raw `urllib` TLS verification fails intermittently** ("certificate has expired") against `wikimedia.org`, `archive.org`, and some image CDN hosts on at least one team member's machine — caused by a stale OS certificate store, not a real network block. `requests` (via `certifi`'s bundled, current CA list) is unaffected. All scripts that download files directly (`enrich_archive_text.py`, `download_images.py`, `download_gdelt_images.py`) use `requests` for this reason — confirmed via A/B test, and confirmed again by the Tunisia pipeline's Wikipedia/Wikimedia collectors (also `requests`-based) succeeding on the same machine where raw `urllib` calls to the same domains failed.

`raw/` holds unprocessed API/source pulls; `processed/` holds cleaned, deduplicated, structured output ready for chunking, plus `quality_report.json` from `scripts/evaluate_data_quality.py`. Both are gitignored (only `.gitkeep` is tracked) — raw pulls and processed corpora should not be committed to the repo.
