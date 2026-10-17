-- 2026-10-15: vector index ivfflat -> HNSW, full-text index, match_chunks with iterative scan.
--
-- Why. With 17,156 chunks the ivfflat index (lists = 8, probes = 1) returned only 67% of the
-- exact top 10 (recall@10 measured against an exact scan on 39 test queries); ivfflat also has
-- to be rebuilt as the table grows because its lists are trained on the data present at build
-- time. HNSW (pgvector >= 0.5) keeps high recall as rows are added. Keyword search (hybrid
-- retriever) scanned the whole table: about 800 ms per query.
--
-- Run once:  psql "$SUPABASE_DB_DIRECT_URL" -f rag/migrations/2026-10-15_hnsw_and_fulltext.sql
-- (rag/schema.sql already contains the same definitions for a fresh project.)

-- Supabase free tier: a parallel build at 256MB ran out of shared memory ("No space left on device").
set maintenance_work_mem = '64MB';
set max_parallel_maintenance_workers = 0;
set statement_timeout = 0;

create index if not exists chunks_embedding_hnsw_idx
    on chunks using hnsw (embedding vector_cosine_ops) with (m = 16, ef_construction = 64);

drop index if exists chunks_embedding_idx;  -- the former ivfflat index

create index if not exists chunks_content_fts_idx
    on chunks using gin (to_tsvector('simple', content));

-- ef_search 100 (default 40) for recall; iterative scan (pgvector >= 0.8) so that the metadata
-- filter is applied while scanning and match_count rows are still returned.
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

analyze chunks;
