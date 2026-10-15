# Evaluation

Two measurements: how good the evidence search is, and how good a whole exhibition run is.

## Retrieval

```bash
python -m evaluation.evaluate_retrieval            # vector vs hybrid, no LLM calls
python -m evaluation.evaluate_retrieval --rerank   # + hybrid with LLM rerank (1 call per query)
```

[`retrieval_cases.json`](retrieval_cases.json) holds 16 queries: Tunisia (democracy, economy, society) and global topics the corpus covers (LLMs, COVID, climate, museums, cinema, protests...). Instead of hand-labelled chunk IDs, each case has **term rules**: a result is relevant when its text or title contains at least one term of every group (whole words, accent-insensitive). This is a reproducible proxy, not a human judgement: a chunk can mention the terms without being useful, and a useful chunk can use other words.

Metrics per method, averaged over the cases (k = 5 by default):

| metric | meaning |
|---|---|
| precision@k | share of the top k results that are relevant |
| hit@k | share of queries with at least one relevant result |
| MRR | 1 / rank of the first relevant result |
| doc diversity | distinct documents / results |
| statistics share | share of World Bank statistics rows in the results |

Results are written to `results/retrieval_<date>.json` with the top results of every case.

First run (2026-10-14, k=5). Five of the 16 reranks fell back to the fused order because the Groq daily token limit was reached, so the rerank row is a lower bound:

| method | precision@5 | hit@5 | MRR | statistics share | s/query |
|---|---|---|---|---|---|
| vector | 0.41 | 0.75 | 0.52 | 0.11 | 0.5 |
| hybrid | 0.68 | 0.94 | 0.83 | 0.00 | 2.1 |
| hybrid + rerank | 0.72 | 1.00 | 0.92 | 0.00 | 16.2 |

**Update 2026-10-15** (new corpus, HNSW index, all 16 reranks completed): vector 0.50 / 0.88 / 0.61,
hybrid 0.70 / 1.00 / 0.94, hybrid + rerank 0.56 / 1.00 / 0.75 (precision@5 / hit@5 / MRR). With every
rerank actually run, reranking lowers quality; it is off by default. Details in `rag/README.md`.

The Tunisia cases stay low (precision 0.2-0.4) for every method: the corpus has only about 75 chunks that mention Tunisia, 40 of them statistics rows. Better retrieval cannot replace missing data; collecting Tunisian sources is the next step.

## Chunking

```bash
python -m evaluation.compare_chunking      # local: no database writes, no LLM (~30 min on CPU)
```

Five chunking configurations on the 557 long documents, 23 passage-level questions in English, French
and Arabic ([`chunking_cases.json`](chunking_cases.json)): a hit is a retrieved chunk that contains the
answer itself (date, name, figure). Results and the choice (sentence packing to the embedder's 128-token
window, with the document title) are in [`rag/README.md`](../rag/README.md#2-chunking) and
`results/chunking_<date>.json`.

## Saved runs

```bash
python run_exhibition.py                             # saves runs/<run_id>/run.json
python -m evaluation.evaluate_run --latest           # metrics from the log
python -m evaluation.evaluate_run --latest --judge   # + LLM faithfulness judge (1 call per specialist)
```

| metric | meaning |
|---|---|
| coverage | specialists that produced cited findings / 5 |
| abstained, errors | specialists with nothing cited / with a provider error or timeout |
| findings, findings_dropped_uncited | findings kept / dropped for missing or invalid citations |
| citation_survival | kept / (kept + dropped) |
| own_search_results_per_agent | evidence each agent found itself |
| review_agreements, review_tensions, review_weak_findings | peer review output |
| fact_check_supported | sections the fact-checker found fully supported |
| faithfulness (`--judge`) | findings an LLM judge finds supported by the text they cite |
| llm_calls, llm_calls_cached, llm_errors, timings_s | cost and speed |

The report is written next to the run as `evaluation.json`.
