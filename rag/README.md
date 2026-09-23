# RAG / Knowledge base

Turns collected documents into a searchable knowledge base and retrieves relevant context for the agents.

- `chunking/` — chunking strategy implementation(s) (fixed size / semantic / recursive / by document structure). The assignment requires justifying chunk size, overlap, and strongly values comparing at least two strategies.
- `vector_store/` — embeddings + vector DB artifacts (not committed; see `.gitignore`). Candidate stores: Pinecone / Weaviate / Supabase.
- Retrieval: top-k, filters (e.g. category/date), optional reranking. Requires a short evaluation of retrieval quality on a small set of test queries (Week 2 milestone).
