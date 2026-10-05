"""
Ingestion module — reads processed JSON files and upserts them into the vector store.

Usage (called programmatically from data/fetch_all.py or directly):

    from data.ingest import ingest_processed, IngestionReport
    from pathlib import Path

    report = ingest_processed(
        processed_dir=Path("data/processed"),
        chunker=my_chunker,           # any object with a .chunk(record) method
        supabase_client=my_client,    # Supabase client (or None during testing)
    )

Stubs
-----
``upsert_document`` and ``upsert_chunks`` are stubs here (Task 2.1).
They will be replaced by real implementations in rag/vector_store/store.py (Task 4.2).
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, TypeVar

T = TypeVar("T")


def _retry(fn: Callable[[], T], attempts: int = 3, backoff_s: float = 2.0) -> T:
    """Retry a network call a few times before giving up — Supabase calls over a
    few thousand records will hit the occasional transient timeout/connection
    reset, and that shouldn't kill the whole ingestion run."""
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < attempts:
                time.sleep(backoff_s * attempt)
    raise last_exc  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class IngestionReport:
    """Summary of one `ingest_processed` run."""

    documents_processed: int = 0
    chunks_by_strategy: dict[str, int] = field(default_factory=dict)
    total_chunks_stored: int = 0
    skipped_chunks: int = 0


# ─────────────────────────────────────────────────────────────────────────────
# Delegate to real store layer (rag/vector_store/store.py)
# Falls back to stubs when the store module is not yet available.
# ─────────────────────────────────────────────────────────────────────────────

try:
    from rag.vector_store.store import (  # type: ignore[import]
        upsert_document,
        upsert_chunks,
    )
except ImportError:
    # Stub fallback — used during testing or before Task 4.2 is wired
    def upsert_document(supabase_client: Any, record: dict) -> str:  # type: ignore[misc]
        """Stub: returns a fake UUID string."""
        return str(uuid.uuid4())

    def upsert_chunks(  # type: ignore[misc]
        supabase_client: Any,
        chunk_embeddings: list[Any],
        document_uuid: str,
    ) -> int:
        """Stub: returns the count of items provided."""
        return len(chunk_embeddings)

try:
    from rag.vector_store.embedder import embed_chunks  # type: ignore[import]
except ImportError:
    def embed_chunks(chunks: list[Any], openai_client: Any, **kwargs: Any) -> list[Any]:  # type: ignore[misc]
        """Stub: pretends every chunk embedded with an empty vector."""
        return [(c, []) for c in chunks]


# ─────────────────────────────────────────────────────────────────────────────
# Main ingestion function
# ─────────────────────────────────────────────────────────────────────────────

def ingest_processed(
    processed_dir: Path,
    chunker: Any,
    supabase_client: Any,
    openai_client: Any = None,
) -> IngestionReport:
    """
    Read all ``*.json`` files in *processed_dir*, chunk each record, embed
    the chunks, and upsert the results into the vector store.

    Parameters
    ----------
    processed_dir:
        Directory containing ``<source>_<date>.json`` files produced by
        ``data/process_raw.py``.
    chunker:
        Any object that exposes ``chunker.chunk(record: dict) -> list``.
        Expected to be a ``rag.chunking.chunker.Chunker`` instance once Task 3
        is complete.
    supabase_client:
        A Supabase client instance (from the ``supabase`` library) or ``None``
        when running with stub helpers.
    openai_client:
        An OpenAI client used to embed each chunk's content before storage.
        When omitted, chunks are passed straight to ``upsert_chunks`` as-is
        (only correct when ``upsert_chunks`` is itself stubbed/mocked, as in
        this module's own unit tests — the real store layer expects
        ``(Chunk, vector)`` pairs).

    Returns
    -------
    IngestionReport
        Populated counts for documents, chunks per strategy, total stored, and
        skipped chunks.
    """
    report = IngestionReport()

    json_files = sorted(processed_dir.glob("*.json"))
    if not json_files:
        print("[ingest] No processed JSON files found — nothing to ingest.")
        return report

    for json_file in json_files:
        try:
            with open(json_file, encoding="utf-8") as fh:
                records = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            print(f"  [ingest][error] Could not read {json_file.name}: {exc}")
            continue

        if not isinstance(records, list):
            records = [records]

        for record in records:
            if not isinstance(record, dict):
                continue

            # upsert_document/upsert_chunks hit the network (Supabase) —
            # transient failures (timeouts, connection resets) are expected
            # over a few thousand calls and must not kill the whole batch.
            try:
                doc_uuid = _retry(lambda: upsert_document(supabase_client, record))
            except Exception as exc:  # noqa: BLE001
                print(
                    f"  [ingest][error] upsert_document failed for record "
                    f"'{record.get('id', '?')}' after retries: {exc} — skipping record"
                )
                report.documents_processed += 1
                report.skipped_chunks += 0  # record itself never got chunked/embedded
                continue

            report.documents_processed += 1

            # Chunk the record
            try:
                chunks = chunker.chunk(record)
            except Exception as exc:  # noqa: BLE001
                print(
                    f"  [ingest][error] Chunking failed for record "
                    f"'{record.get('id', '?')}': {exc}"
                )
                continue

            # Accumulate chunk counts by strategy
            for chunk in chunks:
                strategy = "unknown"
                if isinstance(getattr(chunk, "metadata", None), dict):
                    strategy = chunk.metadata.get("strategy", "unknown")
                report.chunks_by_strategy[strategy] = (
                    report.chunks_by_strategy.get(strategy, 0) + 1
                )

            # Embed before storing — the real upsert_chunks expects
            # (Chunk, vector) pairs, not bare Chunks.
            if openai_client is not None:
                chunk_embeddings = embed_chunks(chunks, openai_client)
                report.skipped_chunks += len(chunks) - len(chunk_embeddings)
            else:
                chunk_embeddings = chunks

            try:
                stored = _retry(lambda: upsert_chunks(supabase_client, chunk_embeddings, doc_uuid))
            except Exception as exc:  # noqa: BLE001
                print(
                    f"  [ingest][error] upsert_chunks failed for record "
                    f"'{record.get('id', '?')}' after retries: {exc} — chunks not stored"
                )
                report.skipped_chunks += len(chunk_embeddings)
                continue
            report.total_chunks_stored += stored

    # ── Human-readable summary ────────────────────────────────────────────────
    print()
    print("=" * 50)
    print("  Ingestion Report")
    print("=" * 50)
    print(f"  Documents processed : {report.documents_processed}")
    print(f"  Total chunks stored : {report.total_chunks_stored}")
    print(f"  Skipped chunks      : {report.skipped_chunks}")
    if report.chunks_by_strategy:
        print("  Chunks by strategy  :")
        for strategy, count in sorted(report.chunks_by_strategy.items()):
            print(f"    {strategy:<20} {count}")
    else:
        print("  Chunks by strategy  : (none)")
    print("=" * 50)
    print()

    return report
