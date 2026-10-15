# RAG / Knowledge base

Turns collected documents into a searchable knowledge base and retrieves evidence for the agents.
Every choice below is measured: the scripts and results are in [`evaluation/`](../evaluation/).

| Layer | Choice | Where |
|---|---|---|
| Corpus | public APIs (GDELT, Wikipedia, World Bank, arXiv, Wikimedia, Openverse, Met, Internet Archive, DBpedia) + Tunisian Wikipedia full text (EN/FR/AR) + full-text news | `data/`, `scripts/` |
| Chunking | **sentence packing up to 128 embedding tokens, 1-sentence overlap, document title prefix** | `chunking/chunker.py` (`PRODUCTION_CHUNK_CONFIG`) |
| Embeddings | `paraphrase-multilingual-MiniLM-L12-v2`, 384 dimensions, local (fastembed) | `vector_store/local_embeddings.py` |
| Vector store | Supabase Postgres + pgvector, ivfflat cosine index, `match_chunks` RPC | `schema.sql` |
| Retrieval | hybrid: vector + Postgres full-text, reciprocal-rank fusion, year/country/category filters, statistics down-weighted, one chunk per document, near-duplicates removed, optional LLM rerank | `vector_store/hybrid_retriever.py` |
| Agent retrieval | each specialist searches with its own queries; the sociologist adds HyDE | `agents/base_agent.py`, `hyde_retriever.py` |

## 1. Corpus

**Why these sources.** The museum shows our era (focus: Tunisia 2020-2026) to a visitor in
2126, through history/society, technology, culture and images. The collectors use official
public APIs only: news events (GDELT, 2,542 documents), statistics (World Bank, 1,466),
encyclopedic knowledge (Wikipedia, Wikidata, DBpedia), science (arXiv), images and art
(Wikimedia Commons, Openverse, Met Museum) and archives (Internet Archive). Language coverage is
deliberate (English, Arabic, French and five more), see `data/regions.py`.

**Problem found (2026-10-14).** The knowledge base was mostly titles: the median document was
**68 characters**, 90% were under 452 characters, and only 100 of 6,711 were longer than 2,000.
GDELT returns headlines only, and the 412 Wikipedia records were "most viewed pages" with no text.
Tunisia was thin: 75 chunks mentioned it in Latin script, 6 in Arabic, and 40 of those were
statistics rows. Full text had been extracted for 360 news articles and 38 archive items, but
into sub-folders that ingestion never read.

**Fix.**
- `data/fetch_tunisia_wikipedia.py`: 31 articles about Tunisia 2020-2026 (2021 self-coup,
  2022 referendum, elections, Kais Saied, economy, women, COVID-19, cinema, climate, water...)
  in English, French and Arabic through the official MediaWiki API: **92 articles, 1.9 million
  characters**.
- `data/process_fulltext.py`: the extracted full text of **286 news articles and 15 archive
  items (1.1 million characters)** as records with the same ids as their headline documents,
  so they update them in place.
- `data/ingest.py` keeps, for each document, the record with the longest text, ingests only the
  given files (`python -m data.ingest <files>`), and deletes chunks left over by a re-chunking.

## 2. Chunking

**Constraint found.** The embedding model reads only its first **128 tokens** and silently
ignores the rest: appending 400 unrelated words to a 100-word text leaves its vector identical
(cosine 1.0000). The former chunks were 512 tiktoken tokens, so most of each long chunk was
invisible to vector search.

**Comparison** (`python -m evaluation.compare_chunking`): five configurations on the 557 long
documents (3.3 million characters), 23 passage-level questions in English, French and Arabic
(`evaluation/chunking_cases.json`); a hit is a retrieved chunk that contains the answer
(a date, a name, a figure). Same embedding model, cosine search over all chunks.

| strategy | chunks | mean tokens | text unseen by the embedder | hit@1 | hit@5 | MRR@10 | context sent for top 5 |
|---|---|---|---|---|---|---|---|
| fixed-512 (former) | 3,586 | 295 | **57%** | 0.30 | 0.52 | 0.40 | 1,472 tokens |
| fixed-100 | 17,734 | 63 | 0% | 0.22 | 0.48 | 0.34 | 316 |
| recursive-600 (paragraphs) | 16,836 | 63 | 6% | 0.30 | **0.70** | 0.43 | 316 |
| sentence-128 | 9,845 | 104 | 0% | 0.26 | 0.56 | 0.39 | 520 |
| **sentence-128 + title** (chosen) | 11,144 | 107 | 0% | 0.30 | 0.65 | **0.47** | 532 |

**Choice: sentence-128 + title.** Whole sentences packed up to 128 tokens of the embedding
model's own tokenizer (so nothing is invisible to it), one sentence of overlap, and the document
title prefixed to every chunk. The title matters: a chunk deep in "2021 Tunisian self-coup"
often never names its subject; with the prefix, the Article 80 and Najla Bouden questions are
found, and no other configuration finds them. It has the best MRR and ties for the best hit@1.
recursive-600 finds one more question in its top 5 (16 vs 15 of 23, not significant on 23
questions) but produces 50% more chunks, many of them a lone heading, and cuts long paragraphs
mid-word. fixed-512, the former setting, is the weakest: 57% of its text is never embedded and
it sends three times more context to the agents. The 128-token budget fits the model; overlap
of one sentence (about 20%) keeps facts that straddle a boundary in at least one chunk.

**Limits.** 23 questions, one run, answers checked by term matching; questions were written
from the corpus. Short documents (headlines, statistics) are one chunk under every strategy.

## 3. Embeddings and vector store

- **Model:** `paraphrase-multilingual-MiniLM-L12-v2` (384 dimensions) through fastembed. Free,
  local (no API key, no data sent out), multilingual (the corpus mixes English, Arabic, French,
  Chinese, Hindi...): an English question retrieves the French and Arabic passages too
  (`bouden-date`, `jcc-1966` above). Its 128-token window drove the chunking choice.
- **Store:** Supabase (Postgres + pgvector), `documents` + `chunks` tables, ivfflat cosine index,
  `match_chunks(query_embedding, match_count, filter)` RPC (`schema.sql`). The n8n workflow embeds
  through the same model (`POST /api/embed`), so every stored vector is comparable.
- `schema.sql` also has an optional full-text index (`chunks_content_fts_idx`) for the keyword
  channel of the hybrid search.

## 4. Retrieval

`vector_store/hybrid_retriever.py`, used by every agent:
1. vector candidates (`match_chunks`) and keyword candidates (Postgres full-text) for each query,
   fused by reciprocal rank;
2. each chunk joined to its document (title, year, url, image);
3. filters: year range (default 2020-2026), country mention, categories; when a country filter
   leaves too few results, the best results from elsewhere are added and marked out of scope;
4. statistics rows down-weighted and capped at one; one chunk per document; near-duplicates
   removed;
5. optional LLM rerank (off for agents by default: one large call per agent for +0.04 precision).

Measured (`python -m evaluation.evaluate_retrieval`, 16 queries, k=5, before the new corpus):

| method | precision@5 | hit@5 | MRR | statistics share |
|---|---|---|---|---|
| vector (former) | 0.41 | 0.75 | 0.52 | 0.11 |
| hybrid | 0.68 | 0.94 | 0.83 | 0.00 |
| hybrid + LLM rerank | 0.72 | 1.00 | 0.92 | 0.00 |

After adding the Tunisian articles and the full-text news (2026-10-15, same 16 queries, no rerank):

| method | precision@5 | hit@5 | MRR | precision@5 on the 3 Tunisia queries |
|---|---|---|---|---|
| vector | 0.41 → 0.47 | 0.75 → 0.81 | 0.52 → 0.54 | 0.13 → 0.53 |
| hybrid | 0.68 → 0.68 | 0.94 → **1.00** | 0.83 → **0.94** | 0.13 → 0.40 |

Knowledge base: 7,296 → 17,156 chunks; chunks mentioning Tunisia 75 → 3,747 (Latin script) and
6 → 1,417 (Arabic). The hybrid search keeps one chunk per document, so on a query such as
"Tunisia economy" it returns five different sources rather than five passages of one article,
which caps its Tunisian precision below the vector channel's (0.40 vs 0.53).

**Known limit.** The ivfflat index was built with `lists = 4` on the earlier, smaller table and
searches one list by default; with 17,000 rows, rebuilding it with more lists (about rows/1000)
and raising `ivfflat.probes` is the next step for vector recall (see the comments in `schema.sql`).

## 5. Reproduce

```bash
python data/fetch_tunisia_wikipedia.py          # Tunisian articles (EN/FR/AR)
python data/process_fulltext.py                 # full-text news/archive records
python -m data.ingest data/processed/tunisia_wikipedia_<date>.json data/processed/fulltext_<date>.json
python -m evaluation.compare_chunking           # chunking comparison (local, ~30 min on CPU)
python -m evaluation.evaluate_retrieval         # retrieval quality on the live knowledge base
```
