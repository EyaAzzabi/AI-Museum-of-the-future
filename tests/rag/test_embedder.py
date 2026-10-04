"""
Unit tests for rag/vector_store/embedder.py and rag/vector_store/store.py.

Task 4.3 — Requirements: 2.5, 2.6

Tests cover:
  - embed_chunks: happy path (all succeed)
  - embed_chunks: retry logic (first attempt fails, second succeeds)
  - embed_chunks: all retries exhausted (chunk excluded and logged)
  - upsert_document: returns UUID from Supabase response
  - upsert_chunks: returns correct written count
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from rag.chunking.chunker import Chunk
from rag.vector_store.embedder import embed_chunks
from rag.vector_store.store import upsert_chunks, upsert_document


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_chunk(index: int = 0, doc_id: str = "doc-1") -> Chunk:
    return Chunk(
        document_id=doc_id,
        chunk_index=index,
        content=f"chunk content {index}",
        metadata={"source": "wikimedia", "category": "art", "lang": "en"},
    )


def _fake_embedding(n: int = 4) -> list[float]:
    return [0.1 * i for i in range(n)]


def _mock_openai_client(embedding: list[float] | None = None) -> MagicMock:
    """Return a mock OpenAI client whose embeddings.create() returns a fixed vector."""
    vector = embedding or _fake_embedding()
    client = MagicMock()
    response = MagicMock()
    response.data = [MagicMock(embedding=vector)]
    client.embeddings.create.return_value = response
    return client


# ─────────────────────────────────────────────────────────────────────────────
# embed_chunks — happy path
# ─────────────────────────────────────────────────────────────────────────────

class TestEmbedChunksHappyPath:
    """embed_chunks returns one (Chunk, vector) pair per input chunk on success."""

    def test_returns_same_count_as_input(self) -> None:
        """All chunks embedded → output length equals input length (Req 2.5)."""
        chunks = [_make_chunk(i) for i in range(5)]
        client = _mock_openai_client()

        result = embed_chunks(chunks, client, model="text-embedding-3-small", max_retries=3)

        assert len(result) == len(chunks), (
            f"Expected {len(chunks)} pairs, got {len(result)}"
        )

    def test_pairs_contain_original_chunk_and_vector(self) -> None:
        """Each returned pair holds the original Chunk and a non-empty vector (Req 2.5)."""
        vector = [0.1, 0.2, 0.3]
        chunks = [_make_chunk(0)]
        client = _mock_openai_client(embedding=vector)

        result = embed_chunks(chunks, client)

        assert len(result) == 1
        returned_chunk, returned_vector = result[0]
        assert returned_chunk is chunks[0]
        assert returned_vector == vector

    def test_embeddings_create_called_once_per_chunk(self) -> None:
        """openai_client.embeddings.create() is called exactly once per chunk (Req 2.5)."""
        n = 3
        chunks = [_make_chunk(i) for i in range(n)]
        client = _mock_openai_client()

        embed_chunks(chunks, client, max_retries=3)

        assert client.embeddings.create.call_count == n

    def test_empty_input_returns_empty_list(self) -> None:
        """No chunks → empty result (edge case)."""
        client = _mock_openai_client()
        result = embed_chunks([], client)
        assert result == []


# ─────────────────────────────────────────────────────────────────────────────
# embed_chunks — retry logic
# ─────────────────────────────────────────────────────────────────────────────

class TestEmbedChunksRetry:
    """Retry: first call raises, second succeeds → chunk is included in output."""

    def test_chunk_included_after_retry_success(self) -> None:
        """Transient failure on attempt 1, success on attempt 2 → chunk kept (Req 2.6)."""
        vector = [0.5, 0.6]
        chunk = _make_chunk(0)

        success_response = MagicMock()
        success_response.data = [MagicMock(embedding=vector)]

        client = MagicMock()
        client.embeddings.create.side_effect = [
            Exception("transient API error"),
            success_response,
        ]

        with patch("time.sleep"):  # skip back-off delays
            result = embed_chunks([chunk], client, max_retries=3)

        assert len(result) == 1, "Chunk should be present after a successful retry"
        returned_chunk, returned_vector = result[0]
        assert returned_chunk is chunk
        assert returned_vector == vector

    def test_embeddings_create_called_twice_on_one_failure(self) -> None:
        """create() must be called twice when the first attempt fails (Req 2.6)."""
        success_response = MagicMock()
        success_response.data = [MagicMock(embedding=[1.0])]

        client = MagicMock()
        client.embeddings.create.side_effect = [
            RuntimeError("oops"),
            success_response,
        ]

        with patch("time.sleep"):
            embed_chunks([_make_chunk()], client, max_retries=3)

        assert client.embeddings.create.call_count == 2

    def test_retry_succeeds_on_last_allowed_attempt(self) -> None:
        """Failures on attempts 1 and 2, success on attempt 3 → chunk included (Req 2.6)."""
        success_response = MagicMock()
        success_response.data = [MagicMock(embedding=[0.9])]

        client = MagicMock()
        client.embeddings.create.side_effect = [
            Exception("err 1"),
            Exception("err 2"),
            success_response,
        ]

        with patch("time.sleep"):
            result = embed_chunks([_make_chunk()], client, max_retries=3)

        assert len(result) == 1


# ─────────────────────────────────────────────────────────────────────────────
# embed_chunks — all retries exhausted
# ─────────────────────────────────────────────────────────────────────────────

class TestEmbedChunksAllRetriesFail:
    """When every retry fails the chunk is excluded from output and a skip message is logged."""

    def test_chunk_excluded_when_all_retries_fail(self) -> None:
        """Chunk missing from result when embeddings.create() always raises (Req 2.6)."""
        client = MagicMock()
        client.embeddings.create.side_effect = Exception("permanent failure")

        with patch("time.sleep"):
            result = embed_chunks([_make_chunk()], client, max_retries=3)

        assert result == [], "Failed chunk must be excluded from results"

    def test_skip_message_printed_when_all_retries_fail(self, capsys: pytest.CaptureFixture) -> None:
        """[skip] log line is printed for a chunk that exhausts all retries (Req 2.6)."""
        client = MagicMock()
        client.embeddings.create.side_effect = Exception("permanent failure")

        with patch("time.sleep"):
            embed_chunks([_make_chunk(index=2, doc_id="my-doc")], client, max_retries=3)

        captured = capsys.readouterr()
        assert "[skip]" in captured.out, (
            "Expected '[skip]' in printed output when chunk is excluded"
        )

    def test_create_called_exactly_max_retries_times(self) -> None:
        """embeddings.create() is called exactly max_retries times on total failure (Req 2.6)."""
        max_retries = 4
        client = MagicMock()
        client.embeddings.create.side_effect = Exception("fail")

        with patch("time.sleep"):
            embed_chunks([_make_chunk()], client, max_retries=max_retries)

        assert client.embeddings.create.call_count == max_retries

    def test_successful_chunks_preserved_when_one_fails(self) -> None:
        """When one of many chunks fails, the successful ones are still returned (Req 2.6)."""
        good_vec = [1.0, 2.0]
        good_response = MagicMock()
        good_response.data = [MagicMock(embedding=good_vec)]

        client = MagicMock()
        # chunk 0 always fails; chunk 1 always succeeds
        client.embeddings.create.side_effect = (
            lambda input, model: (_ for _ in ()).throw(Exception("fail"))
            if "chunk content 0" in input
            else good_response
        )

        chunks = [_make_chunk(0), _make_chunk(1)]

        with patch("time.sleep"):
            result = embed_chunks(chunks, client, max_retries=3)

        result_chunks = [pair[0] for pair in result]
        assert chunks[1] in result_chunks, "chunk 1 (always succeeds) should be in results"
        assert chunks[0] not in result_chunks, "chunk 0 (always fails) should be excluded"


# ─────────────────────────────────────────────────────────────────────────────
# upsert_document
# ─────────────────────────────────────────────────────────────────────────────

class TestUpsertDocument:
    """upsert_document inserts/updates a row and returns its UUID string."""

    def _make_supabase_client(self, returned_uuid: str = "test-uuid-1234") -> MagicMock:
        """Return a mock Supabase client that simulates a successful upsert."""
        client = MagicMock()
        response = MagicMock()
        response.data = [{"id": returned_uuid}]
        (
            client.table.return_value
            .upsert.return_value
            .execute.return_value
        ) = response
        return client

    def test_returns_uuid_from_response(self) -> None:
        """upsert_document returns the UUID string from the Supabase response."""
        expected_uuid = "abc-123-def"
        client = self._make_supabase_client(returned_uuid=expected_uuid)
        record = {
            "id": "source-id-1",
            "source": "arxiv",
            "category": "science",
            "title": "Test title",
            "text": "Some text.",
        }

        result = upsert_document(client, record)

        assert result == expected_uuid

    def test_upsert_called_on_documents_table(self) -> None:
        """upsert_document targets the 'documents' table."""
        client = self._make_supabase_client()
        upsert_document(client, {"id": "x"})
        client.table.assert_called_once_with("documents")

    def test_returns_empty_string_when_response_data_is_empty(self) -> None:
        """Returns '' if response.data is empty (edge case)."""
        client = MagicMock()
        response = MagicMock()
        response.data = []
        (
            client.table.return_value
            .upsert.return_value
            .execute.return_value
        ) = response

        result = upsert_document(client, {"id": "x"})
        assert result == ""

    def test_record_fields_passed_to_upsert(self) -> None:
        """source_id field in the upserted row matches record['id']."""
        client = self._make_supabase_client()
        record = {
            "id": "my-source-id",
            "source": "wikimedia",
            "category": "art",
            "title": "A painting",
            "text": "Painted in 1503.",
        }

        upsert_document(client, record)

        upsert_call = client.table.return_value.upsert.call_args
        row = upsert_call.args[0]
        assert row["source_id"] == "my-source-id"
        assert row["source"] == "wikimedia"


# ─────────────────────────────────────────────────────────────────────────────
# upsert_chunks
# ─────────────────────────────────────────────────────────────────────────────

class TestUpsertChunks:
    """upsert_chunks batch-upserts chunk rows and returns the written count."""

    def _make_supabase_client(self, n_written: int = 3) -> MagicMock:
        client = MagicMock()
        response = MagicMock()
        response.data = [{"id": f"row-{i}"} for i in range(n_written)]
        (
            client.table.return_value
            .upsert.return_value
            .execute.return_value
        ) = response
        return client

    def test_returns_written_count(self) -> None:
        """upsert_chunks returns the number of rows written."""
        chunks = [_make_chunk(i) for i in range(3)]
        pairs = [(c, _fake_embedding()) for c in chunks]
        client = self._make_supabase_client(n_written=3)

        count = upsert_chunks(client, pairs, document_uuid="doc-uuid-42")

        assert count == 3

    def test_returns_zero_for_empty_input(self) -> None:
        """Empty chunk_embeddings → returns 0 without calling Supabase."""
        client = self._make_supabase_client()

        count = upsert_chunks(client, [], document_uuid="doc-uuid-99")

        assert count == 0
        client.table.assert_not_called()

    def test_upsert_called_on_chunks_table(self) -> None:
        """upsert_chunks targets the 'chunks' table."""
        pairs = [(_make_chunk(0), _fake_embedding())]
        client = self._make_supabase_client(n_written=1)

        upsert_chunks(client, pairs, document_uuid="doc-uuid-1")

        client.table.assert_called_once_with("chunks")

    def test_rows_contain_document_uuid(self) -> None:
        """Each upserted row has document_id equal to the given document_uuid."""
        doc_uuid = "my-document-uuid"
        pairs = [(_make_chunk(i), _fake_embedding()) for i in range(2)]
        client = self._make_supabase_client(n_written=2)

        upsert_chunks(client, pairs, document_uuid=doc_uuid)

        upsert_call = client.table.return_value.upsert.call_args
        rows = upsert_call.args[0]
        for row in rows:
            assert row["document_id"] == doc_uuid

    def test_rows_contain_chunk_content_and_embedding(self) -> None:
        """Each row carries 'content' and 'embedding' fields."""
        vector = [0.1, 0.2, 0.3]
        chunk = _make_chunk(0)
        pairs = [(chunk, vector)]
        client = self._make_supabase_client(n_written=1)

        upsert_chunks(client, pairs, document_uuid="d")

        row = client.table.return_value.upsert.call_args.args[0][0]
        assert row["content"] == chunk.content
        assert row["embedding"] == vector
        assert row["chunk_index"] == 0
