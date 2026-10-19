# n8n workflow

Exported n8n workflow(s) (JSON) that automate the end-to-end pipeline: trigger → fetch data → preprocess → store → orchestrate agents → generate output.

Trigger options: manual, webhook, or scheduled execution.

Export the workflow here before each deliverable checkpoint, along with instructions to import and run it (required credentials/env vars, node-by-node notes for anything non-obvious).

## Embeddings

`workflows/My workflow.json` does not call an external embedding API. The
`embed (local MiniLM)` node sends each chunk to the project's Flask app
(`POST /api/embed`), which embeds it with the same local model the retriever
uses (`paraphrase-multilingual-MiniLM-L12-v2`, 384 dimensions, see
`rag/vector_store/local_embeddings.py`). This keeps every vector in the
`chunks.embedding vector(384)` column of `rag/schema.sql` comparable with the
query vectors, whichever path ingested it.

To run the workflow:

1. Start the app first: `python app.py` (listens on port 5000).
2. Run the workflow in n8n. No Gemini credential is needed any more.

If n8n runs in Docker, `localhost` is the container itself: change the node's
URL to `http://host.docker.internal:5000/api/embed`.

## Chunking (aligned with the Python ingestion)

The `chunk` node used to cut 2,000-character chunks. The embedding model reads only its first
128 tokens (about 400-500 characters), so most of each chunk was invisible to vector search.
It now packs whole sentences up to 400 characters, repeats the last sentence in the next chunk
and prefixes the document title, like `PRODUCTION_CHUNK_CONFIG` in `rag/chunking/chunker.py`
(chosen by `evaluation/compare_chunking.py`, see `rag/README.md`).

## Testing the embedding path without n8n

```bash
python n8n/replay_embedding_path.py
```

Runs the workflow's own `chunk` and `format embedding` JavaScript with Node.js, sends the
`embed (local MiniLM)` request to `/api/embed`, and executes the two SQL nodes' exact queries on
Supabase inside a transaction that is rolled back. Last run: 8 chunks of 71-127 tokens (English,
French and Arabic text), 384-dimension vectors stored and read back, database unchanged.

## Exhibition pipeline (end to end)

[`workflows/Exhibition_pipeline_end_to_end.json`](workflows/Exhibition_pipeline_end_to_end.json)
calls the Flask exhibition API on the same machine:

1. Webhook `POST /webhook/exhibition` (or Monday 09:00 schedule).
2. Optional ingest sub-workflow (disabled by default).
3. `POST /api/exhibition` → returns `run_id` (202).
4. Poll `GET /api/exhibition/<run_id>` every 60 s until the exhibition is written.
5. **Exhibition summary** builds museum halls from corpus images (no generation) and emits one item per artwork.
6. **Only hall images** → **Download museum images** (HTTP file) so the final execution shows real **Binary image previews** in n8n.
7. Failure branch if the run has no exhibition.

Body example: `{ "country": "Tunisia", "year_from": 2020, "year_to": 2026, "review": true, "fact_check": true }`.
Replay curator only: `{ "from_run": "20261015-113815-09c5e1" }`.

**End of the workflow — see the museum (images)**

In the execution of **Download museum images**, open the **Binary** tab: each artwork from the halls is a downloadable/visible image.

The summary item also contains:

- `museum_url` → `http://127.0.0.1:5000/virtual?run=<run_id>` (visite 3D, images sur les murs)
- `halls_url` → `http://127.0.0.1:5000/?run=<run_id>&museum=1#exhibition` (plan des salles 2D)
- `halls[]` → `{ hall, title, image_count, images[{ title, image_url }] }`

**Run it**

1. `python app.py` on port 5000 (needs LLM + Supabase keys for a full run).
2. Import the JSON into n8n; keep one active workflow (delete duplicate imports).
3. Use `127.0.0.1`, not `localhost` (n8n on Windows often resolves `localhost` to IPv6 `::1` while Flask listens on IPv4).
4. Optional env: `EXHIBITION_API_URL`, `EXHIBITION_WEB_URL`, `EXHIBITION_API_TOKEN`. Set `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` if `$env` is blocked.

## Known issue: document identity differs from the Python pipeline

n8n identifies documents by `metadata.external_id` (e.g. `arxiv:2610.02207`) and leaves
`source_id` empty; the Python ingestion uses `(source, source_id)` (e.g. `2610.02207v1`). The same
paper ingested by both became two documents: 32 such arXiv duplicates were removed on 2026-10-15
(`python -m rag.dedupe_documents`). To avoid new ones, either set `source_id` in the documents SQL
node with the same convention as `scripts/fetch_arxiv.py`, or run the dedupe after both pipelines.
