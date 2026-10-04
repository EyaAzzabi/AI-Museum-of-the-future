"""Unit tests for rag/vector_store/retriever.py — task 5.1.

Covers:
- RetrievalResult dataclass construction
- Retriever.__init__ defaults
- Retriever.retrieve: embedding → RPC → sorted RetrievalResult list
- Filter forwarding
- Empty / blank query short-circuit
- Row normalisation (various field name variants)
- Req 3.7: < 100 chunk warning logged but execution continues
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from rag.vector_store.retriever import RetrievalResult, Retriever


# ─────────────────────────────────────────────────────────────────────────────
# Helpers / factories
# ─────────────────────────────────────────────────────────────────────────────

def _make_openai_client(embedding: list[float] | None = None) -> MagicMock:
    """Return a mock OpenAI client whose embeddings.create returns *embedding*."""
    if embedding is None:
        embedding = [0.1] * 1536
    client = MagicMock()
    client.embeddings.create.return_value.data = [MagicMock(embedding=embedding)]
    return client


def _make_rpc_row(
    chunk_id: str = "c1",
    document_id: str = "d1",
    content: str = "Some content",
    metadata: dict | None = None,
    similarity: float = 0.85,
) -> dict:
    return {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "content": content,
        "metadata": metadata or {"category": "science"},
        "similarity": similarity,
    }


def _make_supabase_client(rows: list[dict], chunk_count: int = 200) -> MagicMock:
    """Return a mock Supabase client.

    The `rpc` method returns an object with .data = rows.
    The table("chunks").select().execute() returns count=chunk_count.
    """
    sb = MagicMock()

    # RPC response
    rpc_response = MagicMock()
    rpc_response.data = rows
    sb.rpc.return_value.execute.return_value = rpc_response

    # Count query response (Req 3.7)
    count_response = MagicMock()
    count_response.count = chunk_count
    sb.table.return_value.select.return_value.execute.return_value = count_response

    return sb


# ─────────────────────────────────────────────────────────────────────────────
# RetrievalResult dataclass
# ─────────────────────────────────────────────────────────────────────────────

class TestRetrievalResult:
    def test_fields_set_correctly(self):
        rr = RetrievalResult(
            chunk_id="c1",
            document_id="d1",
            content="hello",
            metadata={"source": "arxiv"},
            similarity=0.9,
        )
        assert rr.chunk_id == "c1"
        assert rr.document_id == "d1"
        assert rr.content == "hello"
        assert rr.metadata == {"source": "arxiv"}
        assert rr.similarity == 0.9

    def test_defaults(self):
        rr = RetrievalResult(chunk_id="x", document_id="y", content="z")
        assert rr.metadata == {}
        assert rr.similarity == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Retriever.__init__
# ─────────────────────────────────────────────────────────────────────────────

class TestRetrieverInit:
    def test_default_match_count(self):
        r = Retriever(supabase_client=None, openai_client=None)
        assert r.match_count == 5

    def test_custom_match_count(self):
        r = Retriever(supabase_client=None, openai_client=None, match_count=10)
        assert r.match_count == 10

    def test_clients_stored(self):
        sb = MagicMock()
        oai = MagicMock()
        r = Retriever(sb, oai)
        assert r.supabase_client is sb
        assert r.openai_client is oai


# ─────────────────────────────────────────────────────────────────────────────
# Retriever.retrieve — basic behaviour
# ─────────────────────────────────────────────────────────────────────────────

class TestRetrieverRetrieve:
    def test_returns_list_of_retrieval_results(self):
        rows = [_make_rpc_row(similarity=0.9), _make_rpc_row(chunk_id="c2", similarity=0.7)]
        sb = _make_supabase_client(rows)
        oai = _make_openai_client()

        results = Retriever(sb, oai).retrieve("test query")

        assert len(results) == 2
        assert all(isinstance(r, RetrievalResult) for r in results)

    def test_sorted_descending_similarity(self):
        rows = [
            _make_rpc_row(chunk_id="low", similarity=0.5),
            _make_rpc_row(chunk_id="high", similarity=0.95),
            _make_rpc_row(chunk_id="mid", similarity=0.75),
        ]
        sb = _make_supabase_client(rows)
        oai = _make_openai_client()

        results = Retriever(sb, oai, match_count=10).retrieve("museum query")

        sims = [r.similarity for r in results]
        assert sims == sorted(sims, reverse=True), "Results must be sorted descending by similarity"

    def test_similarity_clamped_to_unit_interval(self):
        rows = [
            _make_rpc_row(chunk_id="over", similarity=1.5),
            _make_rpc_row(chunk_id="under", similarity=-0.3),
        ]
        sb = _make_supabase_client(rows)
        oai = _make_openai_client()

        results = Retriever(sb, oai, match_count=10).retrieve("query")

        for r in results:
            assert 0.0 <= r.similarity <= 1.0, f"similarity {r.similarity} out of [0, 1]"

    def test_match_count_limits_output(self):
        rows = [_make_rpc_row(chunk_id=str(i), similarity=i / 10) for i in range(1, 9)]
        sb = _make_supabase_client(rows)
        oai = _make_openai_client()

        results = Retriever(sb, oai, match_count=3).retrieve("query")

        assert len(results) <= 3

    def test_empty_query_returns_empty_list(self):
        sb = _make_supabase_client([])
        oai = _make_openai_client()
        r = Retriever(sb, oai)

        assert r.retrieve("") == []
        assert r.retrieve("   ") == []

    def test_none_supabase_returns_empty_list(self):
        results = Retriever(None, None).retrieve("any query")
        assert results == []

    def test_embed_query_called_with_model(self):
        """Embedding must use text-embedding-3-small."""
        sb = _make_supabase_client([])
        oai = _make_openai_client()

        Retriever(sb, oai).retrieve("test embedding model")

        call_kwargs = oai.embeddings.create.call_args
        assert call_kwargs is not None
        # model arg should be text-embedding-3-small
        model = call_kwargs[1].get("model") or call_kwargs[0][0] if call_kwargs[0] else None
        if model is None:
            # check kwargs dict
            model = call_kwargs.kwargs.get("model")
        assert model == "text-embedding-3-small"

    def test_rpc_called_with_embedding_and_match_count(self):
        sb = _make_supabase_client([])
        oai = _make_openai_client([0.42] * 1536)

        Retriever(sb, oai, match_count=7).retrieve("query")

        sb.rpc.assert_called_once()
        call_args = sb.rpc.call_args
        rpc_name = call_args[0][0]
        rpc_kwargs = call_args[0][1]
        assert rpc_name == "match_chunks"
        assert rpc_kwargs["match_count"] == 7
        assert rpc_kwargs["query_embedding"] == [0.42] * 1536


# ─────────────────────────────────────────────────────────────────────────────
# Filter forwarding (Req 3.3)
# ─────────────────────────────────────────────────────────────────────────────

class TestRetrieverFilter:
    def test_filter_forwarded_to_rpc(self):
        sb = _make_supabase_client([])
        oai = _make_openai_client()
        filt = {"category": "science"}

        Retriever(sb, oai).retrieve("query", filter=filt)

        call_args = sb.rpc.call_args[0][1]
        assert call_args.get("filter") == filt

    def test_no_filter_arg_omitted_from_rpc(self):
        """When filter=None, the 'filter' key should NOT be included in RPC args."""
        sb = _make_supabase_client([])
        oai = _make_openai_client()

        Retriever(sb, oai).retrieve("query", filter=None)

        call_args = sb.rpc.call_args[0][1]
        assert "filter" not in call_args


# ─────────────────────────────────────────────────────────────────────────────
# Row field normalisation
# ─────────────────────────────────────────────────────────────────────────────

class TestRetrieverRowNormalisation:
    def test_alternative_field_names(self):
        """Rows using 'id'/'documentId'/'score' should still parse correctly."""
        rows = [
            {
                "id": "alt_chunk",
                "documentId": "alt_doc",
                "content": "alt content",
                "metadata": {},
                "score": 0.77,
            }
        ]
        sb = _make_supabase_client(rows)
        oai = _make_openai_client()

        results = Retriever(sb, oai, match_count=5).retrieve("query")

        assert len(results) == 1
        r = results[0]
        assert r.chunk_id == "alt_chunk"
        assert r.document_id == "alt_doc"
        assert r.similarity == pytest.approx(0.77)

    def test_non_dict_rows_skipped(self):
        rows = [None, "bad_row", 42, _make_rpc_row(similarity=0.8)]
        sb = _make_supabase_client(rows)
        oai = _make_openai_client()

        results = Retriever(sb, oai, match_count=10).retrieve("query")

        assert len(results) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Req 3.7 — warning when fewer than 100 chunks
# ─────────────────────────────────────────────────────────────────────────────

class TestRetrieverChunkCountWarning:
    def test_warning_logged_when_fewer_than_100_chunks(self, caplog):
        sb = _make_supabase_client([], chunk_count=50)
        oai = _make_openai_client()

        with caplog.at_level(logging.WARNING, logger="rag.vector_store.retriever"):
            Retriever(sb, oai).retrieve("any query")

        assert any("fewer" in msg.lower() or "only" in msg.lower() for msg in caplog.messages), (
            "Expected a warning about low chunk count but none was logged"
        )

    def test_no_warning_when_100_or_more_chunks(self, caplog):
        sb = _make_supabase_client([], chunk_count=100)
        oai = _make_openai_client()

        with caplog.at_level(logging.WARNING, logger="rag.vector_store.retriever"):
            Retriever(sb, oai).retrieve("any query")

        low_count_warnings = [
            m for m in caplog.messages
            if "fewer" in m.lower() or "only" in m.lower()
        ]
        assert low_count_warnings == []

    def test_retrieval_continues_despite_low_chunk_count(self):
        rows = [_make_rpc_row(similarity=0.8)]
        sb = _make_supabase_client(rows, chunk_count=5)
        oai = _make_openai_client()

        results = Retriever(sb, oai).retrieve("query continues")

        assert len(results) == 1

    def test_no_crash_when_count_query_fails(self):
        """If the count query raises, retrieve should still work normally."""
        sb = MagicMock()
        sb.table.side_effect = Exception("table not available")

        # RPC returns one row normally
        rpc_response = MagicMock()
        rpc_response.data = [_make_rpc_row()]
        sb.rpc.return_value.execute.return_value = rpc_response

        oai = _make_openai_client()

        results = Retriever(sb, oai).retrieve("fallback query")

        assert len(results) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Task 5.2 — Reranker (Requirements 3.5)
# ─────────────────────────────────────────────────────────────────────────────

import json


def _make_reranker_client(scores: list[dict]) -> MagicMock:
    """Return a mock OpenAI client whose chat.completions.create returns *scores*.

    scores should be a list of dicts with 'chunk_id' and 'score' keys.
    The LLM response wraps them in {"scores": [...]} or returns a bare list.
    """
    client = _make_openai_client()
    response_content = json.dumps({"scores": scores})
    msg = MagicMock()
    msg.content = response_content
    choice = MagicMock()
    choice.message = msg
    completion = MagicMock()
    completion.choices = [choice]
    client.chat.completions.create.return_value = completion
    return client


class TestReranker:
    """Unit tests for Retriever._rerank and rerank=True path in retrieve()."""

    def test_rerank_true_calls_gpt4o(self):
        """When rerank=True, chat.completions.create must be called with gpt-4o."""
        rows = [
            _make_rpc_row(chunk_id="c1", similarity=0.9),
            _make_rpc_row(chunk_id="c2", similarity=0.8),
        ]
        sb = _make_supabase_client(rows)
        scores = [{"chunk_id": "c1", "score": 3}, {"chunk_id": "c2", "score": 9}]
        oai = _make_reranker_client(scores)

        Retriever(sb, oai, match_count=5).retrieve("museum query", rerank=True)

        oai.chat.completions.create.assert_called_once()
        call_kwargs = oai.chat.completions.create.call_args
        model = call_kwargs[1].get("model") or (call_kwargs[0][0] if call_kwargs[0] else None)
        if model is None:
            model = call_kwargs.kwargs.get("model")
        assert model == "gpt-4o", f"Expected gpt-4o but got {model}"

    def test_rerank_reorders_by_score_descending(self):
        """Higher LLM score should move a chunk earlier in the results."""
        rows = [
            _make_rpc_row(chunk_id="c1", similarity=0.9),
            _make_rpc_row(chunk_id="c2", similarity=0.8),
            _make_rpc_row(chunk_id="c3", similarity=0.7),
        ]
        sb = _make_supabase_client(rows)
        # c3 gets the highest reranker score — should come first
        scores = [
            {"chunk_id": "c1", "score": 2},
            {"chunk_id": "c2", "score": 5},
            {"chunk_id": "c3", "score": 9},
        ]
        oai = _make_reranker_client(scores)

        results = Retriever(sb, oai, match_count=5).retrieve("query", rerank=True)

        chunk_ids = [r.chunk_id for r in results]
        assert chunk_ids[0] == "c3", "Highest-scored chunk should be first after reranking"
        assert chunk_ids[1] == "c2"
        assert chunk_ids[2] == "c1"

    def test_rerank_preserves_count(self):
        """Reranking must not change the number of results returned (Req 3.5)."""
        n = 4
        rows = [_make_rpc_row(chunk_id=str(i), similarity=i / 10.0) for i in range(1, n + 1)]
        sb = _make_supabase_client(rows)
        scores = [{"chunk_id": str(i), "score": i} for i in range(1, n + 1)]
        oai = _make_reranker_client(scores)

        results = Retriever(sb, oai, match_count=n).retrieve("query", rerank=True)

        assert len(results) == n, (
            f"Expected {n} results after reranking but got {len(results)}"
        )

    def test_rerank_false_skips_llm_call(self):
        """When rerank=False (default), chat.completions.create must NOT be called."""
        rows = [_make_rpc_row()]
        sb = _make_supabase_client(rows)
        oai = _make_openai_client()

        Retriever(sb, oai).retrieve("query", rerank=False)

        oai.chat.completions.create.assert_not_called()

    def test_rerank_falls_back_on_llm_error(self):
        """If the LLM call raises, results should be returned in original order."""
        rows = [
            _make_rpc_row(chunk_id="c1", similarity=0.9),
            _make_rpc_row(chunk_id="c2", similarity=0.8),
        ]
        sb = _make_supabase_client(rows)
        oai = _make_openai_client()
        oai.chat.completions.create.side_effect = Exception("API error")

        results = Retriever(sb, oai, match_count=5).retrieve("query", rerank=True)

        # Should still return results (fallback to original order)
        assert len(results) == 2
        # Original similarity ordering preserved
        assert results[0].chunk_id == "c1"
        assert results[1].chunk_id == "c2"

    def test_rerank_falls_back_on_empty_json_scores(self):
        """If the LLM returns JSON with no recognizable scores, keep original order."""
        rows = [
            _make_rpc_row(chunk_id="c1", similarity=0.9),
            _make_rpc_row(chunk_id="c2", similarity=0.6),
        ]
        sb = _make_supabase_client(rows)
        oai = _make_openai_client()
        # LLM returns valid JSON but with no usable score entries
        msg = MagicMock()
        msg.content = json.dumps({"unexpected_key": []})
        choice = MagicMock()
        choice.message = msg
        completion = MagicMock()
        completion.choices = [choice]
        oai.chat.completions.create.return_value = completion

        results = Retriever(sb, oai, match_count=5).retrieve("query", rerank=True)

        assert len(results) == 2
        assert results[0].chunk_id == "c1"

    def test_rerank_scores_clamped_to_unit_interval(self):
        """Reranked similarity scores must remain in [0.0, 1.0]."""
        rows = [_make_rpc_row(chunk_id="c1", similarity=0.5)]
        sb = _make_supabase_client(rows)
        # Score of 10 → 1.0, score of 0 → 0.0
        scores = [{"chunk_id": "c1", "score": 10}]
        oai = _make_reranker_client(scores)

        results = Retriever(sb, oai, match_count=5).retrieve("query", rerank=True)

        assert len(results) == 1
        assert 0.0 <= results[0].similarity <= 1.0

    def test_rerank_with_no_openai_client_returns_original(self):
        """When openai_client is None, _rerank should return results unchanged."""
        results = [
            RetrievalResult(chunk_id="c1", document_id="d1", content="text", similarity=0.9),
            RetrievalResult(chunk_id="c2", document_id="d2", content="text", similarity=0.7),
        ]
        r = Retriever(supabase_client=None, openai_client=None)
        reranked = r._rerank("query", results)
        assert reranked == results

    def test_rerank_with_empty_results_returns_empty(self):
        """_rerank on an empty list should return an empty list without error."""
        oai = _make_openai_client()
        r = Retriever(supabase_client=None, openai_client=oai)
        reranked = r._rerank("query", [])
        assert reranked == []
        oai.chat.completions.create.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# Task 5.3 — Property 6: Retriever similarity score range and ordering
# Feature: museum-week2-pipeline, Property 6: Retriever similarity score range and ordering
# Validates: Requirements 3.2
# ─────────────────────────────────────────────────────────────────────────────

from hypothesis import given, settings, strategies as st


@given(
    scores=st.lists(st.floats(0.0, 1.0, allow_nan=False, allow_infinity=False), min_size=1, max_size=20)
)
@settings(max_examples=100)
def test_property6_similarity_score_range_and_ordering(scores):
    """Property 6: every similarity score is in [0.0, 1.0] and results are sorted descending.

    **Validates: Requirements 3.2**
    """
    rows = [
        _make_rpc_row(chunk_id=str(i), similarity=score)
        for i, score in enumerate(scores)
    ]
    sb = _make_supabase_client(rows)
    oai = _make_openai_client()

    results = Retriever(sb, oai, match_count=len(rows)).retrieve("museum query")

    # All similarity scores must be within [0.0, 1.0]
    for r in results:
        assert 0.0 <= r.similarity <= 1.0, (
            f"similarity {r.similarity} out of [0.0, 1.0]"
        )

    # Results must be sorted in descending order of similarity
    sims = [r.similarity for r in results]
    assert sims == sorted(sims, reverse=True), (
        f"Results not sorted descending: {sims}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Task 5.4 — Property 7: Retriever filter correctness
# Feature: museum-week2-pipeline, Property 7: Retriever filter correctness
# Validates: Requirements 3.3
# ─────────────────────────────────────────────────────────────────────────────

CATEGORIES = [
    "science",
    "art",
    "history",
    "technology",
    "culture",
    "society",
    "environment",
    "politics",
]


def _make_supabase_client_with_category_filter(rows: list[dict], chunk_count: int = 200) -> MagicMock:
    """Return a mock Supabase client that filters rows by category when a filter is provided.

    This simulates real DB filtering behaviour: only rows whose metadata["category"] matches
    the requested filter value are returned.
    """
    sb = MagicMock()

    def _rpc_side_effect(rpc_name, rpc_args):
        filt = rpc_args.get("filter")
        if filt and "category" in filt:
            category = filt["category"]
            filtered = [
                row for row in rows
                if isinstance(row, dict)
                and row.get("metadata", {}).get("category") == category
            ]
        else:
            filtered = rows

        rpc_response = MagicMock()
        rpc_response.data = filtered
        rpc_call = MagicMock()
        rpc_call.execute.return_value = rpc_response
        return rpc_call

    sb.rpc.side_effect = _rpc_side_effect

    count_response = MagicMock()
    count_response.count = chunk_count
    sb.table.return_value.select.return_value.execute.return_value = count_response

    return sb


@given(
    filter_dict=st.fixed_dictionaries({"category": st.sampled_from(CATEGORIES)}),
    n_rows=st.integers(min_value=1, max_value=20),
)
@settings(max_examples=100)
def test_property7_retriever_filter_correctness(filter_dict, n_rows):
    """Property 7: every returned result has metadata["category"] equal to the filter value.

    **Validates: Requirements 3.3**
    """
    category = filter_dict["category"]

    # Build rows: some matching, some not matching the requested category
    rows = []
    for i in range(n_rows):
        # Alternate between matching and non-matching categories to stress filtering
        row_category = category if i % 2 == 0 else f"other_{i}"
        rows.append(
            _make_rpc_row(
                chunk_id=str(i),
                similarity=0.5 + (i % 5) * 0.1,
                metadata={"category": row_category},
            )
        )

    sb = _make_supabase_client_with_category_filter(rows)
    oai = _make_openai_client()

    results = Retriever(sb, oai, match_count=len(rows)).retrieve(
        "museum query", filter=filter_dict
    )

    # Every returned chunk must have the requested category
    for r in results:
        assert r.metadata.get("category") == category, (
            f"Expected category '{category}' but got '{r.metadata.get('category')}'"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Task 5.5 — Property 8: Reranker count preservation
# Feature: museum-week2-pipeline, Property 8: Reranker count preservation
# Validates: Requirements 3.5
# ─────────────────────────────────────────────────────────────────────────────

from hypothesis import strategies as st
from hypothesis.strategies import composite


@composite
def retrieval_result_strategy(draw):
    """Composite Hypothesis strategy that generates a valid RetrievalResult."""
    chunk_id = draw(st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")), min_size=1, max_size=20))
    document_id = draw(st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")), min_size=1, max_size=20))
    content = draw(st.text(min_size=1, max_size=200))
    similarity = draw(st.floats(0.0, 1.0, allow_nan=False, allow_infinity=False))
    category = draw(st.sampled_from(CATEGORIES))
    return RetrievalResult(
        chunk_id=chunk_id,
        document_id=document_id,
        content=content,
        metadata={"category": category},
        similarity=similarity,
    )


def _make_reranker_client_for_results(results: list[RetrievalResult]) -> MagicMock:
    """Return a mock OpenAI client that returns valid LLM scores for each chunk."""
    client = _make_openai_client()
    scores = [
        {"chunk_id": r.chunk_id, "score": round(r.similarity * 10, 1)}
        for r in results
    ]
    response_content = json.dumps({"scores": scores})
    msg = MagicMock()
    msg.content = response_content
    choice = MagicMock()
    choice.message = msg
    completion = MagicMock()
    completion.choices = [choice]
    client.chat.completions.create.return_value = completion
    return client


@given(results=st.lists(retrieval_result_strategy(), min_size=1, max_size=20))
@settings(max_examples=100)
def test_property8_reranker_count_preservation(results):
    """Property 8: reranking must not change the number of results returned.

    **Validates: Requirements 3.5**
    """
    oai = _make_reranker_client_for_results(results)
    retriever = Retriever(supabase_client=None, openai_client=oai)

    reranked = retriever._rerank("museum exhibition query", results)

    assert len(reranked) == len(results), (
        f"Expected {len(results)} results after reranking but got {len(reranked)}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Task 5.6 — Museum-domain query tests (Requirements 3.4, 3.6, 3.7)
# ─────────────────────────────────────────────────────────────────────────────

class TestMuseumDomainQueries:
    """At least 5 museum-domain queries against a seeded fixture (mock Supabase).

    Each test asserts len(results) >= 1 and results[0].similarity >= 0.70.

    Req 3.6: each test documents query text, top result content excerpt,
    similarity score, and pass/fail verdict as inline comments.

    Req 3.7: the low-chunk warning path is exercised in
    test_museum_domain_low_chunk_warning_logs_but_continues below.
    """

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _seeded_client(query_label: str, similarity: float = 0.82) -> MagicMock:
        """Return a mock Supabase client with one high-similarity row for the given label."""
        row = _make_rpc_row(
            chunk_id=f"chunk_{query_label}",
            document_id=f"doc_{query_label}",
            content=f"Top result for query '{query_label}'",
            metadata={"category": "museum", "source": "arxiv"},
            similarity=similarity,
        )
        return _make_supabase_client([row], chunk_count=200)

    # ── Query 1 ──────────────────────────────────────────────────────────────

    def test_query_ai_breakthroughs_2023(self):
        # query text  : "key AI breakthroughs 2023"
        # top result  : "Top result for query 'ai_breakthroughs'"
        # similarity  : 0.82
        # verdict     : PASS — similarity >= 0.70
        query = "key AI breakthroughs 2023"
        sb = self._seeded_client("ai_breakthroughs", similarity=0.82)
        oai = _make_openai_client()

        results = Retriever(sb, oai).retrieve(query)

        assert len(results) >= 1, f"Expected >= 1 result for query '{query}'"
        assert results[0].similarity >= 0.70, (
            f"Top result similarity {results[0].similarity:.4f} < 0.70 for '{query}'"
        )

    # ── Query 2 ──────────────────────────────────────────────────────────────

    def test_query_climate_change_social_impact(self):
        # query text  : "climate change social impact"
        # top result  : "Top result for query 'climate_change'"
        # similarity  : 0.78
        # verdict     : PASS — similarity >= 0.70
        query = "climate change social impact"
        sb = self._seeded_client("climate_change", similarity=0.78)
        oai = _make_openai_client()

        results = Retriever(sb, oai).retrieve(query)

        assert len(results) >= 1, f"Expected >= 1 result for query '{query}'"
        assert results[0].similarity >= 0.70, (
            f"Top result similarity {results[0].similarity:.4f} < 0.70 for '{query}'"
        )

    # ── Query 3 ──────────────────────────────────────────────────────────────

    def test_query_contemporary_art_arab_world(self):
        # query text  : "contemporary art Arab world"
        # top result  : "Top result for query 'arab_art'"
        # similarity  : 0.75
        # verdict     : PASS — similarity >= 0.70
        query = "contemporary art Arab world"
        sb = self._seeded_client("arab_art", similarity=0.75)
        oai = _make_openai_client()

        results = Retriever(sb, oai).retrieve(query)

        assert len(results) >= 1, f"Expected >= 1 result for query '{query}'"
        assert results[0].similarity >= 0.70, (
            f"Top result similarity {results[0].similarity:.4f} < 0.70 for '{query}'"
        )

    # ── Query 4 ──────────────────────────────────────────────────────────────

    def test_query_pandemic_global_health_response(self):
        # query text  : "pandemic global health response"
        # top result  : "Top result for query 'pandemic_health'"
        # similarity  : 0.91
        # verdict     : PASS — similarity >= 0.70
        query = "pandemic global health response"
        sb = self._seeded_client("pandemic_health", similarity=0.91)
        oai = _make_openai_client()

        results = Retriever(sb, oai).retrieve(query)

        assert len(results) >= 1, f"Expected >= 1 result for query '{query}'"
        assert results[0].similarity >= 0.70, (
            f"Top result similarity {results[0].similarity:.4f} < 0.70 for '{query}'"
        )

    # ── Query 5 ──────────────────────────────────────────────────────────────

    def test_query_space_exploration_milestones(self):
        # query text  : "space exploration milestones"
        # top result  : "Top result for query 'space_milestones'"
        # similarity  : 0.87
        # verdict     : PASS — similarity >= 0.70
        query = "space exploration milestones"
        sb = self._seeded_client("space_milestones", similarity=0.87)
        oai = _make_openai_client()

        results = Retriever(sb, oai).retrieve(query)

        assert len(results) >= 1, f"Expected >= 1 result for query '{query}'"
        assert results[0].similarity >= 0.70, (
            f"Top result similarity {results[0].similarity:.4f} < 0.70 for '{query}'"
        )

    # ── Req 3.7: low-chunk warning logs but retrieval continues ──────────────

    def test_museum_domain_low_chunk_warning_logs_but_continues(self, caplog):
        # Req 3.7: when the Vector_Store has < 100 chunks, a warning is logged
        # but execution continues and results are still returned.
        #
        # query text  : "key AI breakthroughs 2023"
        # top result  : "Top result for query 'ai_breakthroughs'"
        # similarity  : 0.82
        # chunk count : 42 (< 100 → triggers warning)
        # verdict     : PASS — warning logged AND len(results) >= 1
        row = _make_rpc_row(
            chunk_id="chunk_low",
            document_id="doc_low",
            content="Top result for query 'ai_breakthroughs'",
            metadata={"category": "museum"},
            similarity=0.82,
        )
        # chunk_count=42 deliberately triggers the < 100 warning (Req 3.7)
        sb = _make_supabase_client([row], chunk_count=42)
        oai = _make_openai_client()

        with caplog.at_level(logging.WARNING, logger="rag.vector_store.retriever"):
            results = Retriever(sb, oai).retrieve("key AI breakthroughs 2023")

        # Warning must be present
        assert any(
            "fewer" in msg.lower() or "only" in msg.lower()
            for msg in caplog.messages
        ), "Expected a low-chunk-count warning but none was logged"

        # Retrieval must continue and return at least one result
        assert len(results) >= 1, (
            "Retrieval should continue despite low chunk count warning"
        )
