-- Supabase / Postgres schema for the RAG knowledge base.
-- Run this once in your Supabase project's SQL editor (Dashboard > SQL Editor > New query),
-- or via `psql "$SUPABASE_DB_URL" -f rag/schema.sql`.

create extension if not exists vector;

-- One row per source document (a news article, an arXiv paper, a Wikipedia page, ...)
create table if not exists documents (
    id uuid primary key default gen_random_uuid(),
    source text not null,              -- e.g. 'gdelt', 'arxiv', 'wikipedia', 'wikimedia_commons'
    category text,                     -- e.g. 'news', 'science', 'culture', 'technology'
    title text,
    url text,
    published_at timestamptz,
    raw_text text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

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
-- ivfflat needs some rows in the table to build good clusters; if this errors on an
-- empty table, load a first batch of chunks and rerun this statement.
create index if not exists chunks_embedding_idx
    on chunks using ivfflat (embedding vector_cosine_ops) with (lists = 100);

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
