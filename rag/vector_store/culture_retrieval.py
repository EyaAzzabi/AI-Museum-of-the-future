"""Read-only retrieval for Sarah's agent; supports the two pipelines in the ZIP."""
from __future__ import annotations

import json
import math
import os
from typing import Any

from agents.culture_scope import ALIASES, CODES, normalize, resolve_country, matches_country
import re
from rag.vector_store.local_embeddings import EMBEDDING_MODEL, build_embedding_client
from rag.vector_store.retriever import Retriever, RetrievalResult


class CultureRetrievalError(ValueError):
    """Actionable error without disclosing connection strings or API keys."""


def build_supabase_client():
    from supabase import create_client
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        raise CultureRetrievalError("Configure SUPABASE_URL and an authorized Supabase key in .env.")
    try:
        return create_client(url, key)
    except Exception:
        raise CultureRetrievalError("Cannot initialize Supabase. Check the URL and key format.") from None


def vector_dimension(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return None
    return len(value) if isinstance(value, list) and value else None


def diagnose_supabase(client) -> dict:
    """Read counts and a small sample; never modify data or return raw vectors."""
    try:
        docs = client.table("documents").select("id", count="exact").limit(1).execute()
        chunks = client.table("chunks").select("id", count="exact").limit(1).execute()
        sample = client.table("chunks").select("id,embedding,metadata").limit(20).execute()
    except Exception:
        raise CultureRetrievalError("Supabase read failed. Check connectivity, table names and read permissions.") from None
    rows = sample.data or []
    dimensions = sorted({dim for row in rows if (dim := vector_dimension(row.get("embedding"))) is not None})
    return {
        "documents_count": docs.count,
        "chunks_count": chunks.count,
        "sample_size": len(rows),
        "sample_dimensions": dimensions,
        "sample_categories": sorted({str((row.get("metadata") or {}).get("category")) for row in rows}),
        "configured_backend": os.getenv("CULTURE_EMBEDDING_BACKEND") or "not configured",
        "warning": "Dimension alone cannot identify the model. Confirm ingestion model with your teammate."
    }


def embed_query(query: str, backend: str) -> list[float]:
    if backend == "local":
        try:
            return build_embedding_client().embeddings.create(input=query, model=EMBEDDING_MODEL).data[0].embedding
        except Exception:
            raise CultureRetrievalError("Local embedding failed. Check fastembed and the model download.") from None
    if backend != "gemini":
        raise CultureRetrievalError("Set CULTURE_EMBEDDING_BACKEND to gemini or local, matching your stored vectors.")
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise CultureRetrievalError("Gemini retrieval requires GEMINI_API_KEY in your local .env.")
    import requests
    try:
        response = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent",
            headers={"x-goog-api-key": key, "Content-Type": "application/json"},
            json={"model": "models/gemini-embedding-001",
                  "content": {"parts": [{"text": query}]},
                  "taskType": "RETRIEVAL_QUERY", "outputDimensionality": 1536},
            timeout=30,
        )
        if response.status_code != 200:
            raise CultureRetrievalError(f"Gemini embedding returned HTTP {response.status_code}; check key, quota and model access.")
        vector = response.json()["embedding"]["values"]
        if len(vector) != 1536 or any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) for v in vector):
            raise CultureRetrievalError("Gemini returned an invalid 1536-dimension vector.")
        return [float(v) for v in vector]
    except CultureRetrievalError:
        raise
    except Exception:
        raise CultureRetrievalError("Gemini embedding request failed. Check connectivity and response format.") from None



COUNTRY_PAGE_SIZE = 200
MAX_COUNTRY_CANDIDATES = 2000


def _parse_vector(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return None
    if not isinstance(value, list) or not value:
        return None
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in value):
        return None
    return value


def _cosine(query_vector, stored_vector):
    if len(query_vector) != len(stored_vector):
        return None
    norm_q = math.sqrt(sum(x*x for x in query_vector))
    norm_d = math.sqrt(sum(x*x for x in stored_vector))
    if not norm_q or not norm_d:
        return None
    return max(0.0, min(1.0, sum(a*b for a,b in zip(query_vector, stored_vector)) / (norm_q*norm_d)))


def _lexical_coverage(query, text, country):
    # General query terms, never a hardcoded artist or an injected answer.
    stopwords = {'and','the','of','in','on','a','an','for','to','et','de','du','des','en','le','la','les'}
    country_words = {token for alias in ALIASES.get(country, ()) for token in re.findall(r'\w+', normalize(alias))}
    words = set(re.findall(r'\w+', normalize(query))) - stopwords - country_words
    tokens = set(re.findall(r'\w+', normalize(text)))
    return len(words & tokens) / len(words) if words else 0.0


def _country_first_candidates(client, country, query, query_vector, category=None):
    # Values come only from our fixed country registry, not raw user input.
    filters = [f'content.ilike."%{alias}%"' for alias in ALIASES[country]]
    filters.extend(f'metadata->>country.ilike."%{alias}%"' for alias in ALIASES[country])
    filters.append(f'metadata->>country_code.eq.{CODES[country]}')
    rows = []
    reached_cap = False
    try:
        for start in range(0, MAX_COUNTRY_CANDIDATES, COUNTRY_PAGE_SIZE):
            statement = client.table('chunks').select('id,document_id,content,embedding,metadata,documents(title,url,published_at)').or_(','.join(filters)).order('id')
            if category:
                statement = statement.eq('metadata->>category', category)
            page = statement.range(start, start + COUNTRY_PAGE_SIZE - 1).execute().data or []
            if not isinstance(page, list):
                raise TypeError('Expected list from Supabase')
            rows.extend(page)
            if len(page) < COUNTRY_PAGE_SIZE:
                break
        else:
            reached_cap = True
    except Exception:
        raise CultureRetrievalError('Country-first read failed. Check SELECT permissions on chunks/documents and their document_id relationship.') from None
    results = []
    skipped = 0
    for row in rows:
        doc = row.get('documents') or {}
        if not isinstance(doc, dict):
            doc = {}
        metadata = dict(row.get('metadata') or {})
        metadata.update({k:v for k,v in {'title':doc.get('title'),'url':doc.get('url'),'published_at':doc.get('published_at')}.items() if v})
        candidate = {**row, 'metadata':metadata}
        if not matches_country(candidate, country):
            continue
        stored = _parse_vector(row.get('embedding'))
        similarity = _cosine(query_vector, stored) if stored else None
        if similarity is None:
            skipped += 1
            continue
        lexical = _lexical_coverage(query, str(doc.get('title','')) + ' ' + str(row.get('content','')), country)
        metadata.update(lexical_coverage=lexical, hybrid_score=0.7*similarity + 0.3*lexical,
                        retrieval_method='country_first_hybrid')
        result = Retriever._row_to_result({**candidate, 'metadata':metadata, 'similarity':similarity})
        if result is not None:
            results.append(result)
    return results, {'country_rows_scanned':len(rows), 'country_candidates_count':len(results),
                     'country_scan_reached_cap':reached_cap, 'country_vectors_skipped':skipped}


def retrieve_culture(query: str, client, top_k: int = 5, category: str | None = None,
                     country: str | None = None, diagnostics: dict | None = None, reranker=None) -> list[RetrievalResult]:
    if not isinstance(query, str) or not query.strip() or len(query) > 2000:
        raise CultureRetrievalError("A query containing 1-2000 characters is required.")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 20:
        raise CultureRetrievalError("top_k must be an integer between 1 and 20.")
    scope = resolve_country(query, country)
    if diagnostics is not None:
        diagnostics.update(scope_country=scope, candidate_count=0, rejected_country_count=0, returned_count=0)
    backend = os.getenv("CULTURE_EMBEDDING_BACKEND", "").strip().lower()
    expected = {"local": 384, "gemini": 1536}.get(backend)
    if expected is None:
        raise CultureRetrievalError("First run --diagnose, confirm the ingestion model, then set CULTURE_EMBEDDING_BACKEND=gemini or local.")
    database_info = diagnose_supabase(client)
    dims = database_info["sample_dimensions"]
    if dims and dims != [expected]:
        raise CultureRetrievalError(f"Stored sample dimensions {dims} do not match {backend} ({expected}). No data was modified.")
    if database_info["chunks_count"] == 0:
        return []
    vector = embed_query(query, backend)
    # A wider semantic shortlist gives the geographic filter room to find evidence.
    candidate_k = min(100, max(80 if reranker else 0, top_k * 10)) if scope or reranker else top_k
    args = {"query_embedding": vector, "match_count": candidate_k}
    if category:
        args["filter"] = {"category": category}
    try:
        rows = client.rpc("match_chunks", args).execute().data or []
        results = [Retriever._row_to_result(row) for row in rows]
    except Exception:
        raise CultureRetrievalError("match_chunks failed. Check RPC signature, vector dimension and execute permissions using docs/diagnostic_supabase.sql.") from None
    ranked = sorted((r for r in results if r is not None), key=lambda r: r.similarity, reverse=True)
    scoped = [r for r in ranked if matches_country(r, scope)]
    scan_info = {}
    combined = {r.chunk_id:r for r in scoped}
    if scope:
        country_results, scan_info = _country_first_candidates(client, scope, query, vector, category)
        combined.update({r.chunk_id:r for r in country_results})
    def ranking_score(result):
        return result.metadata.get('hybrid_score',
            0.7*result.similarity + 0.3*_lexical_coverage(query, result.content, scope)) if scope else result.similarity
    pool = sorted(combined.values(), key=ranking_score, reverse=True)
    rerank_info = {}
    if reranker is not None:
        pool = reranker(pool, query, scope, rerank_info)
    # Avoid filling the answer with repeated chunks of one document.
    selected, seen_documents = [], set()
    for result in pool:
        key = result.document_id or result.chunk_id
        if reranker is not None and key in seen_documents:
            continue
        seen_documents.add(key)
        selected.append(result)
        if len(selected) == top_k:
            break
    if diagnostics is not None:
        diagnostics.update(candidate_count=len(ranked), rejected_country_count=len(ranked)-len(scoped),
                           returned_count=len(selected), requested_top_k=top_k,
                           retrieval_method='country_first_hybrid' if scope else 'semantic_rpc',
                           **scan_info, **rerank_info)
    return selected
