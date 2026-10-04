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
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


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


# ─────────────────────────────────────────────────────────────────────────────
# Main ingestion function
# ─────────────────────────────────────────────────────────────────────────────

def ingest_processed(
    processed_dir: Path,
    chunker: Any,
    supabase_client: Any,
) -> IngestionReport:
    """
    Read all ``*.json`` files in *processed_dir*, chunk each record, and
    upsert the results into the vector store (via stub helpers in this task).

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

            # Upsert document (stub returns a fake UUID)
            doc_uuid = upsert_document(supabase_client, record)
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

            # Upsert chunks (stub returns len(chunk_embeddings))
            # At this stage we pass chunks directly (no embeddings yet).
            stored = upsert_chunks(supabase_client, chunks, doc_uuid)
            report.total_chunks_stored += stored
            # skipped_chunks stays 0 — stubs never fail

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
