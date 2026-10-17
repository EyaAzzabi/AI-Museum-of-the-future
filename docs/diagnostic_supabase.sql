-- READ-ONLY: paste in your existing Supabase SQL editor. No schema changes.
-- 1. Declared vector column dimension.
select a.attname, format_type(a.atttypid, a.atttypmod) as column_type
from pg_attribute a
where a.attrelid = 'public.chunks'::regclass and a.attname = 'embedding';
-- 2. Dimensions really stored, counts and missing vectors.
select vector_dims(embedding) as dimensions, count(*) from public.chunks group by 1;
select count(*) as documents_count from public.documents;
-- 3. RPC signature/body and unique indexes used by both ingestion paths.
select p.oid::regprocedure as signature, pg_get_functiondef(p.oid)
from pg_proc p join pg_namespace n on n.oid = p.pronamespace
where n.nspname = 'public' and p.proname = 'match_chunks';
select tablename, indexname, indexdef from pg_indexes
where schemaname = 'public' and tablename in ('chunks', 'documents');
-- 4. Cultural coverage and readable excerpts (no vectors/credentials displayed).
select metadata->>'category' as category, metadata->>'source' as source, count(*)
from public.chunks group by 1,2 order by count(*) desc;
select id, metadata->>'title' as title, left(content, 300) as excerpt
from public.chunks where metadata->>'category' in ('culture','image','images_media','social_cultural') limit 10;
