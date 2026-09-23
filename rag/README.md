# RAG / Knowledge base

Turns collected documents into a searchable knowledge base and retrieves relevant context for the agents.

- `schema.sql` — Postgres/Supabase schema (`documents`, `chunks` with a `pgvector` embedding column, a cosine-similarity index, and a `match_chunks` RPC for top-k retrieval). Run once against a Supabase project; see top-level README setup steps.
- `chunking/` — chunking strategy implementation(s) (fixed size / semantic / recursive / by document structure). The assignment requires justifying chunk size, overlap, and strongly values comparing at least two strategies.
- `vector_store/` — local embeddings/vector artifacts, if any (not committed; see `.gitignore`). The vector store itself is Supabase/pgvector (`schema.sql`), not a local index.
- Retrieval: top-k, filters (e.g. category/date via the `filter` jsonb param on `match_chunks`), optional reranking. Requires a short evaluation of retrieval quality on a small set of test queries (Week 2 milestone).
