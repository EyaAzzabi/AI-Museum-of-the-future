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
-- (1536 = OpenAI text-embedding-3-small / ada-002 — change if you pick a different model).
create table if not exists chunks (
    id uuid primary key default gen_random_uuid(),
    document_id uuid not null references documents(id) on delete cascade,
    chunk_index int not null,
    content text not null,
    embedding vector(1536),
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists chunks_document_id_idx on chunks (document_id);

-- Approximate nearest-neighbour index for cosine similarity search.
-- `lists` must scale with row count — a rule of thumb is rows/1000 (min ~4),
-- not a fixed value. lists=100 against a table with only a few hundred rows
-- leaves ~1-2 rows per list, which silently breaks ivfflat's default
-- single-probe search: `ORDER BY embedding <=> query LIMIT n` then returns
-- ZERO rows with no error (confirmed live — ~150 rows against lists=100
-- returned nothing; dropping and rebuilding with lists=4 fixed it
-- immediately). If chunks already has data, check row count first:
--   select count(*) from chunks;
-- then pick lists accordingly (4 is reasonable up to a few thousand rows).
-- Rebuild as the table grows: `drop index chunks_embedding_idx;` then rerun
-- with an updated `lists` value (may need `set maintenance_work_mem = '128MB';`
-- first — the default 32MB can be too small even for a modest rebuild).
create index if not exists chunks_embedding_idx
    on chunks using ivfflat (embedding vector_cosine_ops) with (lists = 4);

-- Top-k similarity search, callable from Python (supabase-py .rpc()) or n8n (Supabase node / HTTP request).
create or replace function match_chunks (
    query_embedding vector(1536),
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
