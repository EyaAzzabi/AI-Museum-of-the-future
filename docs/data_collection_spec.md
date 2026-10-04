# Data Collection Specification
## AI Museum of the Future — Tunisia 2020-2026

**Version:** 1.0  
**Week:** 1  
**Status:** ✅ Scripts ready — pending execution & validation

---

## 1. Scope & Decisions

| Parameter | Decision | Rationale |
|---|---|---|
| Country | Tunisia | Project case study |
| Period | 2020–2026 | Contemporary era, rich in events |
| Languages | French + English | Most accessible APIs, avoids Arabic parsing complexity |
| Volume | Light (~500–600 items) | Sufficient for RAG prototype, fast to collect |
| Thematic coverage | All 5 themes | Politics/society, economy, culture/arts, science/tech, environment |

---

## 2. Data Sources

### 2.1 GDELT
| Field | Value |
|---|---|
| Script | `scripts/collectors/gdelt_collector.py` |
| API | GDELT DOC API v2 — `https://api.gdeltproject.org/api/v2/doc/doc` |
| API Key | Not required |
| Output | `data/raw/gdelt/gdelt_articles.json` |
| Volume | ~200 articles |
| Method | 10 keyword queries (FR + EN) × 20 articles each, deduplicated by URL |
| Fields | title, url, domain, language, seendate, socialimage, theme, source |

**Queries used:**

| Theme | Query |
|---|---|
| politics_society | "Tunisia politics society 2020 2021 2022 2023 2024" |
| politics_society | "Tunisie politique société constitution" |
| economy | "Tunisia economy IMF crisis unemployment" |
| economy | "Tunisie économie crise FMI inflation" |
| culture_arts | "Tunisia culture arts cinema music" |
| culture_arts | "Tunisie culture cinéma musique patrimoine" |
| science_tech | "Tunisia technology startups innovation research" |
| science_tech | "Tunisie technologie startups innovation" |
| environment | "Tunisia environment water drought climate" |
| environment | "Tunisie environnement eau sécheresse climat" |

---

### 2.2 Wikipedia
| Field | Value |
|---|---|
| Script | `scripts/collectors/wikipedia_collector.py` |
| API | MediaWiki API — `https://{en/fr}.wikipedia.org/w/api.php` |
| API Key | Not required |
| Output | `data/raw/wikipedia/wikipedia_articles.json` |
| Volume | ~38 articles |
| Method | Manually curated list of article titles, full plain-text extract |
| Fields | title, pageid, url, categories, text, word_count, lang, theme |

**Articles by theme:**

| Theme | Count | Examples |
|---|---|---|
| politics_society | 8 | "Kais Saied", "2021 Tunisian political crisis" |
| economy | 5 | "Economy of Tunisia", "Tourism in Tunisia" |
| culture_arts | 7 | "Cinema of Tunisia", "Carthage Film Festival" |
| science_tech | 6 | "Telecommunications in Tunisia", "Startup ecosystem in Tunisia" |
| environment | 5 | "Water scarcity in Tunisia", "Désertification en Tunisie" |
| historical_context | 6 | "Tunisia", "Tunisian Revolution" |

---

### 2.3 Google Trends
| Field | Value |
|---|---|
| Script | `scripts/collectors/google_trends_collector.py` |
| API | pytrends (unofficial Google Trends wrapper) |
| API Key | Not required (may hit 429 rate limits) |
| Output | `data/raw/google_trends/google_trends.json` |
| Volume | ~10 topic groups × weekly data points 2020–2026 |
| Method | 10 keyword groups (max 5 keywords/request), geo=TN |
| Fields | keywords, geo, timeframe, average_interest, weekly_data |

> ⚠ **Note:** Google Trends can return HTTP 429 (Too Many Requests). The script includes automatic retries with exponential backoff. If blocked, wait ~1 hour and re-run with `--only google_trends`.

---

### 2.4 arXiv
| Field | Value |
|---|---|
| Script | `scripts/collectors/arxiv_collector.py` |
| API | arXiv Atom API — `http://export.arxiv.org/api/query` |
| API Key | Not required |
| Output | `data/raw/arxiv/arxiv_papers.json` |
| Volume | ~50 papers |
| Method | 5 search queries filtering by Tunisian affiliation and/or topic keywords, sorted by date desc |
| Fields | id, title, abstract, authors, affiliations, published, categories, pdf_url |

**Queries used:**

| Theme | Search Strategy |
|---|---|
| science_tech | `affil:"Tunisia"` — broad |
| science_tech | `affil:"Tunisia"` + machine learning |
| environment | Tunisia in title + climate/water/drought |
| economy | Tunisia in title/abstract + economic/unemployment/migration |
| culture_arts | Tunisia in title/abstract + social/culture/gender |

---

### 2.5 World Bank
| Field | Value |
|---|---|
| Script | `scripts/collectors/worldbank_collector.py` |
| API | World Bank Open Data API v2 — `https://api.worldbank.org/v2/` |
| API Key | Not required |
| Output | `data/raw/worldbank/worldbank_indicators.json` |
| Volume | 33 indicator series |
| Method | One API call per indicator, country=TN, date=2020:2026 |
| Fields | indicator_code, indicator_name, yearly_values, latest_year, latest_value |

**Indicators by theme:**

| Theme | Count | Examples |
|---|---|---|
| economy | 11 | GDP, inflation, unemployment, tourism arrivals |
| politics_society | 10 | Population, poverty, migration, health expenditure |
| science_tech | 6 | Internet usage, R&D expenditure, patent applications |
| environment | 6 | CO2 emissions, freshwater withdrawals, renewable energy |

---

### 2.6 Wikimedia Commons
| Field | Value |
|---|---|
| Script | `scripts/collectors/wikimedia_collector.py` |
| API | Wikimedia Commons API — `https://commons.wikimedia.org/w/api.php` |
| API Key | Not required |
| Output | `data/raw/wikimedia/wikimedia_images_metadata.json` + `data/raw/wikimedia/images/` |
| Volume | ~100 images |
| Method | 14 keyword searches in File namespace, filtered by open license (CC/Public Domain) |
| Fields | title, url, thumb_url, mime, width, height, license, artist, description, local_filename |

> **License policy:** Only images with CC (any), CC0, GFDL or Public Domain licenses are downloaded.

---

## 3. Running the Collection

### Install dependencies
```bash
pip install -r requirements.txt
```

### Run all collectors
```bash
python scripts/run_collection.py
```

### Run specific collectors only
```bash
python scripts/run_collection.py --only gdelt wikipedia worldbank
```

### Skip a collector (e.g. Google Trends if rate-limited)
```bash
python scripts/run_collection.py --skip google_trends
```

### Dry run (show plan without executing)
```bash
python scripts/run_collection.py --dry-run
```

---

## 4. Output Structure

```
data/raw/
├── gdelt/
│   └── gdelt_articles.json
├── wikipedia/
│   └── wikipedia_articles.json
├── google_trends/
│   └── google_trends.json
├── arxiv/
│   └── arxiv_papers.json
├── worldbank/
│   └── worldbank_indicators.json
└── wikimedia/
    ├── wikimedia_images_metadata.json
    └── images/
        └── *.jpg / *.png / ...
```

---

## 5. Volume Summary

| Source | Type | Expected volume | Theme coverage |
|---|---|---|---|
| GDELT | News articles | ~200 | All 5 themes |
| Wikipedia | Encyclopedia articles | ~38 | All 5 + historical |
| Google Trends | Search interest timeseries | ~10 groups | All 5 themes |
| arXiv | Scientific papers | ~50 | Science, env, economy, culture |
| World Bank | Economic/social indicators | 33 | Economy, society, science, env |
| Wikimedia | Images + metadata | ~100 | All 5 + historical |
| **TOTAL** | | **~430–450 items** | **All 5 themes** |

---

## 6. Data Quality Notes

- **Deduplication:** GDELT and Wikimedia collectors deduplicate by URL/page_id at collection time.
- **Null values:** World Bank may return null for some years — nulls are filtered out, only non-null values stored.
- **Language:** All text data is in EN or FR. Arabic sources are out of scope for this phase.
- **License compliance:** Wikimedia images are filtered to open licenses only — safe for academic use.
- **Rate limits:** Google Trends is the only source with aggressive rate limiting. All others are stable.

---

## 7. Validation Checklist (for professor review)

- [ ] All 6 scripts execute without errors
- [ ] `data/raw/` contains 6 subdirectories with output files
- [ ] GDELT: ≥100 articles in `gdelt_articles.json`
- [ ] Wikipedia: ≥30 articles in `wikipedia_articles.json`
- [ ] arXiv: ≥20 papers in `arxiv_papers.json`
- [ ] World Bank: ≥25 indicators in `worldbank_indicators.json`
- [ ] Wikimedia: ≥50 images downloaded in `wikimedia/images/`
- [ ] All themes (politics, economy, culture, science, environment) represented in each source
- [ ] No API keys hardcoded in any script
- [ ] All outputs are valid JSON

---

*Document maintained by: Data & APIs role*  
*Last updated: Week 1*
