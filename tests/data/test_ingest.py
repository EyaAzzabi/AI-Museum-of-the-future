"""
Unit tests for data/ingest.py

Tests:
1. ingest_processed returns an IngestionReport with correct counts on a small
   fixture corpus (5 processed JSON records).
2. --skip-ingest flag prevents ingest_processed from being called.

Requirements: 1.7, 2.7
"""

from __future__ import annotations

import json
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from data.ingest import IngestionReport, ingest_processed


# ─────────────────────────────────────────────────────────────────────────────
# Store stubs — patch the *imported* names inside data.ingest so tests never
# require a live Supabase connection regardless of which store implementation
# is currently active.
# ─────────────────────────────────────────────────────────────────────────────

def _fake_upsert_document(supabase_client, record):  # noqa: ANN001
    """Stub for rag.vector_store.store.upsert_document."""
    return str(uuid.uuid4())


def _fake_upsert_chunks(supabase_client, chunk_embeddings, document_uuid):  # noqa: ANN001
    """Stub for rag.vector_store.store.upsert_chunks — returns chunk count."""
    return len(chunk_embeddings)


# Convenience context-manager that patches both store helpers at once.
from contextlib import contextmanager


@contextmanager
def _patched_store():
    """Patch upsert_document and upsert_chunks inside data.ingest."""
    with patch("data.ingest.upsert_document", side_effect=_fake_upsert_document), \
         patch("data.ingest.upsert_chunks", side_effect=_fake_upsert_chunks):
        yield


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _make_records(n: int) -> list[dict]:
    """Return n minimal processed-record dicts."""
    return [
        {
            "id": f"record-{i}",
            "source": "arxiv",
            "category": "science",
            "title": f"Test paper {i}",
            "text": f"This is the text body for record number {i}. " * 10,
            "url": f"https://example.com/{i}",
            "image_url": None,
            "date": "2026-10-04",
            "lang": "en",
            "tags": ["ai", "test"],
            "raw_source": "arxiv_test.json",
            "processed_on": "2026-10-04",
        }
        for i in range(n)
    ]


@dataclass
class _FakeChunk:
    """Minimal stand-in for rag.chunking.chunker.Chunk."""
    document_id: str
    chunk_index: int
    content: str
    metadata: dict


class _FakeChunker:
    """Deterministic chunker stub: splits text into exactly 2 chunks per record."""

    def chunk(self, record: dict) -> list[_FakeChunk]:
        text = record.get("text", "no text")
        mid = max(1, len(text) // 2)
        return [
            _FakeChunk(
                document_id=record.get("id", "unknown"),
                chunk_index=0,
                content=text[:mid],
                metadata={"strategy": "fixed_size", "source": record.get("source")},
            ),
            _FakeChunk(
                document_id=record.get("id", "unknown"),
                chunk_index=1,
                content=text[mid:],
                metadata={"strategy": "fixed_size", "source": record.get("source")},
            ),
        ]


# ─────────────────────────────────────────────────────────────────────────────
# Test 1 — IngestionReport counts on 5-record fixture corpus
# ─────────────────────────────────────────────────────────────────────────────

class TestIngestProcessed:
    """Tests for ingest_processed() return value correctness."""

    def test_report_has_correct_document_count(self, tmp_path: Path) -> None:
        """ingest_processed should count one document per JSON record."""
        records = _make_records(5)
        fixture_file = tmp_path / "arxiv_test.json"
        fixture_file.write_text(json.dumps(records), encoding="utf-8")

        with _patched_store():
            report = ingest_processed(tmp_path, _FakeChunker(), supabase_client=None)

        assert report.documents_processed == 5

    def test_report_total_chunks_stored(self, tmp_path: Path) -> None:
        """_FakeChunker produces 2 chunks per record; 5 records → 10 total."""
        records = _make_records(5)
        (tmp_path / "source.json").write_text(json.dumps(records), encoding="utf-8")

        with _patched_store():
            report = ingest_processed(tmp_path, _FakeChunker(), supabase_client=None)

        assert report.total_chunks_stored == 10

    def test_report_chunks_by_strategy(self, tmp_path: Path) -> None:
        """Chunks with strategy='fixed_size' metadata should be bucketed correctly."""
        records = _make_records(5)
        (tmp_path / "source.json").write_text(json.dumps(records), encoding="utf-8")

        with _patched_store():
            report = ingest_processed(tmp_path, _FakeChunker(), supabase_client=None)

        assert "fixed_size" in report.chunks_by_strategy
        assert report.chunks_by_strategy["fixed_size"] == 10

    def test_report_skipped_chunks_zero_when_no_errors(self, tmp_path: Path) -> None:
        """No chunking errors → skipped_chunks should be 0."""
        records = _make_records(5)
        (tmp_path / "source.json").write_text(json.dumps(records), encoding="utf-8")

        with _patched_store():
            report = ingest_processed(tmp_path, _FakeChunker(), supabase_client=None)

        assert report.skipped_chunks == 0

    def test_report_returns_ingestion_report_instance(self, tmp_path: Path) -> None:
        """Return type must be IngestionReport."""
        records = _make_records(5)
        (tmp_path / "source.json").write_text(json.dumps(records), encoding="utf-8")

        with _patched_store():
            report = ingest_processed(tmp_path, _FakeChunker(), supabase_client=None)

        assert isinstance(report, IngestionReport)

    def test_empty_directory_returns_zero_counts(self, tmp_path: Path) -> None:
        """An empty processed directory should yield an all-zero IngestionReport."""
        with _patched_store():
            report = ingest_processed(tmp_path, _FakeChunker(), supabase_client=None)

        assert report.documents_processed == 0
        assert report.total_chunks_stored == 0
        assert report.skipped_chunks == 0
        assert report.chunks_by_strategy == {}

    def test_multiple_json_files_are_all_processed(self, tmp_path: Path) -> None:
        """Records split across two files should both be ingested."""
        (tmp_path / "file_a.json").write_text(
            json.dumps(_make_records(3)), encoding="utf-8"
        )
        (tmp_path / "file_b.json").write_text(
            json.dumps(_make_records(2)), encoding="utf-8"
        )

        with _patched_store():
            report = ingest_processed(tmp_path, _FakeChunker(), supabase_client=None)

        assert report.documents_processed == 5
        assert report.total_chunks_stored == 10

    def test_chunker_exception_skips_record_but_continues(self, tmp_path: Path) -> None:
        """If chunker.chunk() raises for one record, the rest are still processed."""

        class _BurstChunker:
            def __init__(self):
                self._call_count = 0

            def chunk(self, record: dict) -> list[_FakeChunk]:
                self._call_count += 1
                if self._call_count == 1:
                    raise ValueError("simulated chunking failure")
                return [
                    _FakeChunk(
                        document_id=record.get("id", "?"),
                        chunk_index=0,
                        content=record.get("text", "x"),
                        metadata={"strategy": "fixed_size"},
                    )
                ]

        records = _make_records(5)
        (tmp_path / "source.json").write_text(json.dumps(records), encoding="utf-8")

        chunker = _BurstChunker()
        with _patched_store():
            report = ingest_processed(tmp_path, chunker, supabase_client=None)

        # 5 records attempted → 5 documents_processed (upsert_document called
        # before chunk); first chunking fails, so only 4 records contribute chunks
        assert report.documents_processed == 5
        assert report.total_chunks_stored == 4


# ─────────────────────────────────────────────────────────────────────────────
# Test 2 — --skip-ingest flag prevents ingestion from running
# ─────────────────────────────────────────────────────────────────────────────

class TestSkipIngestFlag:
    """Tests that the --skip-ingest CLI flag prevents ingest_processed from running."""

    def test_skip_ingest_prevents_ingestion(self) -> None:
        """
        When --skip-ingest is passed to fetch_all.main(), ingest_processed must
        NOT be called, even if --skip-process is not set.
        """
        with patch("data.fetch_all._run_ingestion") as mock_run_ingestion, \
             patch("data.fetch_all.run_module"):
            # Import main lazily to avoid side-effects at import time
            from data.fetch_all import main

            with patch("sys.argv", ["fetch_all.py", "--skip-ingest"]):
                main()

        mock_run_ingestion.assert_not_called()

    def test_without_skip_ingest_ingestion_is_called(self) -> None:
        """
        Without --skip-ingest, _run_ingestion SHOULD be called (after normalization).
        """
        with patch("data.fetch_all._run_ingestion") as mock_run_ingestion, \
             patch("data.fetch_all.run_module"):
            from data.fetch_all import main

            with patch("sys.argv", ["fetch_all.py"]):
                main()

        mock_run_ingestion.assert_called_once()

    def test_skip_ingest_with_skip_process_also_skips(self) -> None:
        """
        When both --skip-process and --skip-ingest are passed, ingestion is not
        reached anyway (normalization block is skipped entirely).
        """
        with patch("data.fetch_all._run_ingestion") as mock_run_ingestion, \
             patch("data.fetch_all.run_module"):
            from data.fetch_all import main

            with patch("sys.argv", ["fetch_all.py", "--skip-process", "--skip-ingest"]):
                main()

        mock_run_ingestion.assert_not_called()
