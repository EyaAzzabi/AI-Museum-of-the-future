-- Supabase / Postgres schema for the RAG knowledge base.
-- Run this once in your Supabase project's SQL editor (Dashboard > SQL Editor > New query),
-- or via `psql "$SUPABASE_DB_URL" -f rag/schema.sql`.

create extension if not exists vector;

-- One row per source document (a news article, an arXiv paper, a Wikipedia page, ...)
create table if not exists documents (
    id uuid primary key default gen_random_uuid(),
    source text not null,              -- e.g. 'gdelt', 'arxiv', 'wikipedia', 'wikimedia_commons'
    source_id text,                    -- the record's ID in its own source (e.g. an arXiv ID) — the
                                        -- natural key for upsert dedup, since `id` is a fresh UUID every call
    category text,                     -- e.g. 'news', 'science', 'culture', 'technology'
    title text,
    url text,
    published_at timestamptz,
    raw_text text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

-- Lets upsert_document() (rag/vector_store/store.py) dedupe via
-- on_conflict="source,source_id" instead of inserting a fresh row every run.
create unique index if not exists documents_source_source_id_idx on documents (source, source_id);

-- One row per chunk of a document, with its embedding.
-- `embedding` dimension must match your embedding model's output
-- (384 = sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2, the local model in
-- rag/vector_store/local_embeddings.py. If you previously created this table with 1536 dims
-- (OpenAI), drop `chunks` + its index + match_chunks and re-run this file, then re-ingest.)
create table if not exists chunks (
    id uuid primary key default gen_random_uuid(),
    document_id uuid not null references documents(id) on delete cascade,
    chunk_index int not null,
    content text not null,
    embedding vector(384),
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists chunks_document_id_idx on chunks (document_id);

-- Approximate nearest-neighbour index for cosine similarity search: HNSW.
-- History: an ivfflat index (lists = 4, later 8) silently returned zero rows when lists
-- outnumbered the data, had to be rebuilt as the table grew, and at 17,156 rows returned only
-- 67% of the exact top 10 (probes = 1). HNSW needs no training on existing rows and measured
-- recall@10 = 1.00 on the same 39 queries (rag/migrations/2026-10-15_hnsw_and_fulltext.sql).
-- On the Supabase free tier, build without parallel workers and with modest memory:
--   set maintenance_work_mem = '64MB'; set max_parallel_maintenance_workers = 0;
create index if not exists chunks_embedding_hnsw_idx
    on chunks using hnsw (embedding vector_cosine_ops) with (m = 16, ef_construction = 64);

-- Keyword (full-text) search used by rag/vector_store/hybrid_retriever.py, which queries
-- chunks.content with PostgREST's fts(simple) filter. It works without this index
-- (~0.5-1.5 s per query on ~7k chunks); the index makes it fast as the corpus grows.
create index if not exists chunks_content_fts_idx
    on chunks using gin (to_tsvector('simple', content));

-- Top-k similarity search, callable from Python (supabase-py .rpc()) or n8n (Supabase node / HTTP request).
create or replace function match_chunks (
    query_embedding vector(384),
    match_count int default 5,
    filter jsonb default '{}'::jsonb
)
returns table (
    id uuid,
    document_id uuid,
    content text,
    metadata jsonb,
    similarity float
)
language plpgsql
as $$
begin
    -- ef_search 100 (default 40) for recall; iterative scan (pgvector >= 0.8) applies the
    -- metadata filter while scanning, so match_count rows are still returned.
    perform set_config('hnsw.ef_search', greatest(100, match_count)::text, true);
    perform set_config('hnsw.iterative_scan', 'relaxed_order', true);
    return query
    select
        chunks.id,
        chunks.document_id,
        chunks.content,
        chunks.metadata,
        1 - (chunks.embedding <=> query_embedding) as similarity
    from chunks
    where chunks.metadata @> filter
    order by chunks.embedding <=> query_embedding
    limit match_count;
end;
$$;
