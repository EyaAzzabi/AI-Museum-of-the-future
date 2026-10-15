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

## Known issue: document identity differs from the Python pipeline

n8n identifies documents by `metadata.external_id` (e.g. `arxiv:2610.02207`) and leaves
`source_id` empty; the Python ingestion uses `(source, source_id)` (e.g. `2610.02207v1`). The same
paper ingested by both became two documents: 32 such arXiv duplicates were removed on 2026-10-15
(`python -m rag.dedupe_documents`). To avoid new ones, either set `source_id` in the documents SQL
node with the same convention as `scripts/fetch_arxiv.py`, or run the dedupe after both pipelines.
