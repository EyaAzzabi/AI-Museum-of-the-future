"""Hybrid evidence search: vector + keyword, filtered, diversified and reranked.

The plain Retriever only does a vector search, which on this corpus returns
near-identical statistics rows ("Population, total for Tunisia in 2021: ...")
for most social queries, and misses exact names ("Kaïs Saïed", "Startup Act")
whose meaning a small embedding model does not capture well.

HybridRetriever.search():
  1. Vector candidates  — match_chunks RPC (rag/schema.sql), over-fetched.
  2. Keyword candidates — Postgres full-text search on chunks.content.
  3. Reciprocal-rank fusion of both lists.
  4. Document metadata  — title, date, url and image of each chunk's document.
  5. Filters            — country (explicit mention), year range, categories.
  6. Statistics rows are down-weighted.
  7. Diversity          — one chunk per document, no near-duplicate texts,
                          at most `max_statistics` statistics rows.
  8. Optional LLM rerank of the remaining candidates.

It also exposes ``retrieve(query, filter=None, rerank=False)`` and
``match_count`` so it can stand in for Retriever (the sociologist's HyDE
retriever uses that interface).
"""
from __future__ import annotations

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from functools import lru_cache
from typing import Any

from rag.vector_store.local_embeddings import EMBEDDING_MODEL
from rag.vector_store.retriever import RetrievalResult, llm_rerank

logger = logging.getLogger(__name__)

RRF_K = 60
STATISTICS_CATEGORY = "statistics"
_WORD = re.compile(r"[^\W_]+", re.UNICODE)
_STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "into", "about", "between", "their",
    "les", "des", "dans", "pour", "avec", "une", "sur", "par", "aux", "est", "sont", "qui",
}


@dataclass
class SearchFilters:
    """Constraints applied after fusion. ``None`` means "no constraint"."""

    country: str | None = None            # e.g. "Tunisia"; matched on text/title mentions
    year_from: int | None = 2020
    year_to: int | None = 2026
    keep_undated: bool = True             # half the corpus has no published_at
    categories: tuple[str, ...] | None = None        # keep only these categories
    exclude_categories: tuple[str, ...] = ()


@dataclass
class SearchConfig:
    candidate_pool: int = 40          # candidates fetched per channel before filtering
    statistics_weight: float = 0.35   # score multiplier for statistics rows
    max_statistics: int = 1           # statistics rows allowed in one result set
    duplicate_threshold: float = 0.6  # token Jaccard above which two chunks are near-duplicates
    rerank_pool: int = 20             # candidates sent to the LLM reranker
    # When the country filter leaves fewer than k results, top up with the best
    # results from elsewhere, marked metadata["in_scope"] = False. The corpus has
    # little country-specific material for some agents (images, technology).
    relax_country: bool = True
    # LLM-rerank the agents' own searches. Off by default: it adds one large LLM
    # call per agent and run, for +0.04 precision@5 in evaluation/ (0.68 -> 0.72).
    rerank_agent_searches: bool = False


@dataclass
class _Candidate:
    result: RetrievalResult
    score: float = 0.0
    channels: set[str] = field(default_factory=set)


def tokens(text: str) -> set[str]:
    return {w.casefold() for w in _WORD.findall(text or "")}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def keyword_query(query: str, keywords: list[str] | tuple[str, ...] | None = None) -> str:
    """Build a Postgres tsquery: explicit keywords as phrases, else the query's content words, OR-ed."""
    terms: list[str] = []
    for phrase in (keywords or []):
        words = [w for w in _WORD.findall(phrase)]
        if words:
            terms.append(" <-> ".join(w.lower() for w in words))
    if not terms:
        terms = sorted({w.lower() for w in _WORD.findall(query) if len(w) >= 4 and w.lower() not in _STOPWORDS})
    return " | ".join(f"({t})" if "<->" in t else t for t in terms)


def year_of(value: Any) -> int | None:
    match = re.match(r"(\d{4})", str(value or ""))
    return int(match.group(1)) if match else None


class HybridRetriever:
    def __init__(
        self,
        supabase_client: Any,
        embed_client: Any,
        llm_client: Any = None,
        match_count: int = 8,
        config: SearchConfig | None = None,
        filters: SearchFilters | None = None,
    ) -> None:
        self.supabase_client = supabase_client
        self.embed_client = embed_client
        self.llm_client = llm_client
        self.match_count = match_count
        self.config = config or SearchConfig()
        self.default_filters = filters or SearchFilters()
        self._embed_cached = lru_cache(maxsize=512)(self._embed)

    # ── Retriever-compatible API ─────────────────────────────────────────────

    def retrieve(self, query: str, filter: dict | None = None, rerank: bool = False) -> list[RetrievalResult]:
        categories = (filter or {}).get("category")
        filters = self.default_filters
        if categories:
            filters = replace(filters, categories=(categories,))
        return self.search(query, k=self.match_count, filters=filters, rerank=rerank)

    # ── Main entry points ────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        k: int | None = None,
        filters: SearchFilters | None = None,
        keywords: list[str] | tuple[str, ...] | None = None,
        rerank: bool = True,
    ) -> list[RetrievalResult]:
        return self.search_many([query], k=k, filters=filters, keywords=keywords, rerank_query=query if rerank else None)

    def search_many(
        self,
        queries: list[str],
        k: int | None = None,
        filters: SearchFilters | None = None,
        keywords: list[str] | tuple[str, ...] | None = None,
        rerank_query: str | None = None,
    ) -> list[RetrievalResult]:
        """Run several queries in parallel, fuse everything, filter, diversify and optionally rerank once."""
        k = k or self.match_count
        filters = filters or self.default_filters
        queries = [q for q in queries if q and q.strip()]
        if not queries or self.supabase_client is None:
            return []

        with ThreadPoolExecutor(max_workers=min(8, 2 * len(queries))) as pool:
            vector_jobs = [pool.submit(self._vector_candidates, q, filters) for q in queries]
            # Explicit keywords are the same for every query: search them once.
            keyword_inputs = [queries[0]] if keywords else queries
            keyword_jobs = [pool.submit(self._keyword_candidates, q, keywords, filters) for q in keyword_inputs]
            ranked_lists = [("vector", job.result()) for job in vector_jobs] + [("keyword", job.result()) for job in keyword_jobs]

        candidates = self._fuse(ranked_lists)
        self._attach_documents(candidates)
        for c in candidates:
            if self._category(c.result) == STATISTICS_CATEGORY:
                c.score *= self.config.statistics_weight
        candidates.sort(key=lambda c: c.score, reverse=True)

        in_scope = [c for c in candidates if self._passes(c.result, filters)]
        limit = max(k, self.config.rerank_pool) if rerank_query else k
        diverse = self._diversify(in_scope, limit=limit)
        if filters.country and self.config.relax_country and len(diverse) < k:
            relaxed = replace(filters, country=None)
            taken = {id(c) for c in in_scope}
            outside = [c for c in candidates if id(c) not in taken and self._passes(c.result, relaxed)]
            for c in outside:
                c.result = replace(c.result, metadata={**(c.result.metadata or {}), "in_scope": False})
            diverse += self._diversify(outside, limit=k - len(diverse), chosen=diverse)

        results = [self._with_score(c) for c in diverse]
        if rerank_query:
            results = llm_rerank(self.llm_client, rerank_query, results)
            # Keep in-scope evidence ahead of the top-up, whatever the reranker says.
            results.sort(key=lambda r: (r.metadata or {}).get("in_scope") is False)
        return results[:k]

    # ── Candidate channels ───────────────────────────────────────────────────

    def _embed(self, text: str) -> tuple[float, ...]:
        response = self.embed_client.embeddings.create(input=text, model=EMBEDDING_MODEL)
        return tuple(response.data[0].embedding)

    def _vector_candidates(self, query: str, filters: SearchFilters) -> list[RetrievalResult]:
        try:
            embedding = list(self._embed_cached(query))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to embed query: %s", exc)
            return []
        args: dict[str, Any] = {"query_embedding": embedding, "match_count": self.config.candidate_pool}
        if filters.categories and len(filters.categories) == 1:
            args["filter"] = {"category": filters.categories[0]}
        try:
            rows = _execute(lambda: self.supabase_client.rpc("match_chunks", args)).data or []
        except Exception as exc:  # noqa: BLE001
            logger.warning("match_chunks RPC failed: %s", exc)
            return []
        return [r for r in (_row_to_result(row) for row in rows) if r is not None]

    def _keyword_candidates(self, query: str, keywords, filters: SearchFilters) -> list[RetrievalResult]:
        tsquery = keyword_query(query, keywords)
        if not tsquery:
            return []
        try:
            request = (
                self.supabase_client.table("chunks")
                .select("id,document_id,content,metadata")
                .filter("content", "fts(simple)", tsquery)
            )
            if filters.categories and len(filters.categories) == 1:
                request = request.contains("metadata", {"category": filters.categories[0]})
            rows = _execute(lambda: request.limit(self.config.candidate_pool)).data or []
        except Exception as exc:  # noqa: BLE001
            logger.warning("Keyword search failed for %r: %s", tsquery, exc)
            return []
        # Rank keyword hits by how many query terms they contain.
        wanted = tokens(" ".join(keywords or []) or query)
        results = [r for r in (_row_to_result({**row, "similarity": 0.0}) for row in rows) if r is not None]
        return sorted(results, key=lambda r: len(wanted & tokens(r.content)), reverse=True)

    # ── Fusion, metadata, filters, diversity ─────────────────────────────────

    @staticmethod
    def _fuse(ranked_lists: list[tuple[str, list[RetrievalResult]]]) -> list[_Candidate]:
        fused: dict[str, _Candidate] = {}
        for channel, results in ranked_lists:
            for rank, result in enumerate(results):
                cand = fused.setdefault(result.chunk_id, _Candidate(result=result))
                cand.score += 1.0 / (RRF_K + rank + 1)
                cand.channels.add(channel)
                if result.similarity > cand.result.similarity:
                    cand.result = replace(cand.result, similarity=result.similarity)
        return list(fused.values())

    def _attach_documents(self, candidates: list[_Candidate]) -> None:
        doc_ids = sorted({c.result.document_id for c in candidates if c.result.document_id})
        documents: dict[str, dict] = {}
        for start in range(0, len(doc_ids), 100):
            try:
                batch = doc_ids[start:start + 100]
                rows = _execute(lambda: (
                    self.supabase_client.table("documents")
                    .select("id,source,category,title,url,published_at,metadata")
                    .in_("id", batch)
                )).data or []
            except Exception as exc:  # noqa: BLE001
                logger.warning("Document lookup failed: %s", exc)
                rows = []
            documents.update({row["id"]: row for row in rows})
        for c in candidates:
            doc = documents.get(c.result.document_id) or {}
            doc_meta = doc.get("metadata") or {}
            meta = dict(c.result.metadata or {})
            meta.setdefault("source", doc.get("source"))
            meta.setdefault("category", doc.get("category"))
            meta.update({
                "title": doc.get("title"),
                "url": doc.get("url"),
                "published_at": doc.get("published_at"),
                # GDELT rows have no published_at but keep the source date in date_raw
                "year": year_of(doc.get("published_at")) or year_of(doc_meta.get("date_raw")),
                "image_url": doc_meta.get("image_url"),
                "channels": sorted(c.channels),
            })
            c.result = replace(c.result, metadata=meta)

    @staticmethod
    def _category(result: RetrievalResult) -> str:
        return str((result.metadata or {}).get("category") or "")

    def _passes(self, result: RetrievalResult, filters: SearchFilters) -> bool:
        category = self._category(result)
        if filters.categories and category not in filters.categories:
            return False
        if category in filters.exclude_categories:
            return False
        year = (result.metadata or {}).get("year")
        if year is None:
            if not filters.keep_undated:
                return False
        elif (filters.year_from and year < filters.year_from) or (filters.year_to and year > filters.year_to):
            return False
        if filters.country:
            from agents.culture_scope import mentions

            title = str((result.metadata or {}).get("title") or "")
            if not (mentions(result.content, filters.country) or mentions(title, filters.country)):
                return False
        return True

    def _diversify(self, candidates: list[_Candidate], limit: int,
                   chosen: list[_Candidate] | None = None) -> list[_Candidate]:
        """Greedy selection; ``chosen`` are earlier picks the new ones must also differ from."""
        earlier = list(chosen or [])
        chosen = []
        chosen_tokens = [tokens(c.result.content) for c in earlier]
        documents = {c.result.document_id for c in earlier}
        statistics = sum(self._category(c.result) == STATISTICS_CATEGORY for c in earlier)
        for cand in candidates:
            if len(chosen) >= limit:
                break
            result = cand.result
            if result.document_id and result.document_id in documents:
                continue
            is_stat = self._category(result) == STATISTICS_CATEGORY
            if is_stat and statistics >= self.config.max_statistics:
                continue
            words = tokens(result.content)
            if any(jaccard(words, other) >= self.config.duplicate_threshold for other in chosen_tokens):
                continue
            chosen.append(cand)
            chosen_tokens.append(words)
            documents.add(result.document_id)
            statistics += is_stat
        return chosen

    @staticmethod
    def _with_score(cand: _Candidate) -> RetrievalResult:
        meta = dict(cand.result.metadata or {})
        meta["fused_score"] = round(cand.score, 5)
        return replace(cand.result, metadata=meta)


def _execute(build: Any, attempts: int = 3) -> Any:
    """Execute a Supabase request, retrying transient failures ("Server disconnected").

    ``build`` returns a fresh request each time.
    """
    for attempt in range(attempts):
        try:
            return build().execute()
        except Exception:  # noqa: BLE001
            if attempt == attempts - 1:
                raise
            time.sleep(0.5 * (attempt + 1))


def _row_to_result(row: Any) -> RetrievalResult | None:
    if not isinstance(row, dict):
        return None
    chunk_id = row.get("chunk_id") or row.get("id") or ""
    if not chunk_id:
        return None
    similarity = row.get("similarity")
    return RetrievalResult(
        chunk_id=str(chunk_id),
        document_id=str(row.get("document_id") or ""),
        content=str(row.get("content") or ""),
        metadata=row.get("metadata") or {},
        similarity=max(0.0, min(1.0, float(similarity or 0.0))),
    )


def build_hybrid_retriever(llm_client: Any = None, **kwargs: Any) -> HybridRetriever:
    """Hybrid retriever on the project's Supabase database with local embeddings."""
    from supabase import create_client

    from rag.vector_store.local_embeddings import build_embedding_client
    from scripts.config import SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL

    return HybridRetriever(
        create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY),
        build_embedding_client(),
        llm_client=llm_client,
        **kwargs,
    )
