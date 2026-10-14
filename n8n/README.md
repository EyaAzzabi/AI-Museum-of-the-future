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
