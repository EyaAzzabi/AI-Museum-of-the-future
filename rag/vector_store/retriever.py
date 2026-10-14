"""Query the Supabase vector store for relevant chunks, with optional LLM reranking.

Task 5.1-5.6 — Requirements: 3.2, 3.3, 3.4, 3.5, 3.6, 3.7
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, replace

from agents.llm_config import get_model
from rag.vector_store.local_embeddings import EMBEDDING_MODEL

logger = logging.getLogger(__name__)

LOW_CHUNK_COUNT_THRESHOLD = 100


@dataclass
class RetrievalResult:
    chunk_id: str
    document_id: str
    content: str
    metadata: dict = field(default_factory=dict)
    similarity: float = 0.0


class Retriever:
    def __init__(self, supabase_client, openai_client, match_count: int = 5, embed_client=None) -> None:
        # openai_client: any OpenAI-compatible chat client (used for reranking).
        # embed_client: embeddings client; defaults to openai_client for backwards compatibility.
        self.supabase_client = supabase_client
        self.openai_client = openai_client
        self.embed_client = embed_client if embed_client is not None else openai_client
        self.match_count = match_count

    # ── public API ──────────────────────────────────────────────────────────

    def retrieve(
        self,
        query: str,
        filter: dict | None = None,
        rerank: bool = False,
    ) -> list[RetrievalResult]:
        if not query or not query.strip():
            return []
        if self.supabase_client is None:
            return []

        try:
            embed_response = self.embed_client.embeddings.create(input=query, model=EMBEDDING_MODEL)
            query_embedding = embed_response.data[0].embedding
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to embed query: {e}")
            return []

        self._warn_if_few_chunks()

        rpc_args: dict = {"query_embedding": query_embedding, "match_count": self.match_count}
        if filter is not None:
            rpc_args["filter"] = filter

        try:
            rpc_response = self.supabase_client.rpc("match_chunks", rpc_args).execute()
            rows = rpc_response.data or []
        except Exception as e:  # noqa: BLE001
            logger.warning(f"match_chunks RPC failed: {e}")
            rows = []

        results = [r for r in (self._row_to_result(row) for row in rows) if r is not None]
        results.sort(key=lambda r: r.similarity, reverse=True)
        results = results[: self.match_count]

        if rerank:
            results = self._rerank(query, results)

        return results

    # ── helpers ─────────────────────────────────────────────────────────────

    def _warn_if_few_chunks(self) -> None:
        """Req 3.7: warn (don't fail) when the vector store is too small to be meaningful."""
        try:
            count_response = self.supabase_client.table("chunks").select("id", count="exact").execute()
            count = getattr(count_response, "count", None)
        except Exception:  # noqa: BLE001
            return
        if count is not None and count < LOW_CHUNK_COUNT_THRESHOLD:
            logger.warning(
                f"Vector store has only {count} chunks (fewer than {LOW_CHUNK_COUNT_THRESHOLD}) — "
                "retrieval quality may be degraded"
            )

    @staticmethod
    def _row_to_result(row) -> RetrievalResult | None:
        if not isinstance(row, dict):
            return None

        chunk_id = row.get("chunk_id") or row.get("id") or ""
        document_id = row.get("document_id") or row.get("documentId") or ""
        content = row.get("content", "")
        metadata = row.get("metadata") or {}

        similarity = row.get("similarity")
        if similarity is None:
            similarity = row.get("score", 0.0)
        similarity = max(0.0, min(1.0, float(similarity)))

        return RetrievalResult(
            chunk_id=chunk_id,
            document_id=document_id,
            content=content,
            metadata=metadata,
            similarity=similarity,
        )

    def _rerank(self, query: str, results: list[RetrievalResult]) -> list[RetrievalResult]:
        """Req 3.5: re-score top results with an LLM judge; fall back to original order on any failure."""
        return llm_rerank(self.openai_client, query, results)


def llm_rerank(client: Any, query: str, results: list[RetrievalResult]) -> list[RetrievalResult]:
    """Re-score results 0-10 with an LLM judge; keep the original order on any failure."""
    if not results or client is None:
        return results
    try:
        items = [{"chunk_id": r.chunk_id, "content": r.content[:500]} for r in results]
        prompt = (
            "Rate how relevant each chunk is to the query on a 0-10 scale.\n\n"
            f"Query: {query}\n\n"
            f"Chunks: {json.dumps(items, ensure_ascii=False)}\n\n"
            'Respond with JSON only: {"scores": [{"chunk_id": "...", "score": 0-10}, ...]}'
        )
        completion = client.chat.completions.create(
            model=get_model("RERANK_MODEL"),
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
        scores = json.loads(completion.choices[0].message.content).get("scores") or []
        score_map = {s["chunk_id"]: s["score"] for s in scores if "chunk_id" in s and "score" in s}
        if not score_map:
            return results
        reranked = sorted(results, key=lambda r: score_map.get(r.chunk_id, r.similarity * 10), reverse=True)
        return [
            replace(r, similarity=max(0.0, min(1.0, float(score_map[r.chunk_id]) / 10.0)))
            if r.chunk_id in score_map else r
            for r in reranked
        ]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Reranking failed, keeping fused order: %s", exc)
        return results
