# Data

Public, accessible sources only (no full-internet crawling). Candidate sources per category:

- **News & events** — GDELT API, NewsAPI, BBC/Reuters open data
- **Images & media** — Wikimedia Commons, Unsplash (open license), GDELT news images
- **Science & research** — NASA Open APIs, arXiv, open datasets (e.g. climate, health)
- **Social & cultural trends** — Google Trends, UNESCO cultural heritage, World Bank open data
- **Historical context** — Wikipedia, Wikidata, digital archives

`raw/` holds unprocessed API/source pulls; `processed/` holds cleaned, deduplicated, structured output ready for chunking. Both are gitignored (only `.gitkeep` is tracked) — raw pulls and processed corpora should not be committed to the repo.
