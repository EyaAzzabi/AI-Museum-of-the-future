"""
Ingestion module — reads processed JSON files and upserts them into the vector store.

Usage from the command line (only the given files, with the production chunking):

    python -m data.ingest data/processed/tunisia_wikipedia_2026-10-14.json data/processed/fulltext_2026-10-14.json
    python -m data.ingest --all            # every data/processed/*.json

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

EMBED_BATCH = 64  # chunks per embedding call: one call per chunk was the bottleneck of ingestion


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
        delete_stale_chunks,
        upsert_document,
        upsert_chunks,
    )
except ImportError:
    def delete_stale_chunks(supabase_client: Any, document_uuid: str, keep: int) -> None:  # type: ignore[misc]
        """Stub: nothing to delete."""

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

def load_records(json_files: list[Path]) -> list[dict]:
    """Read records from the files, one per (source, id), keeping the longest text.

    The same document can appear in several files: a GDELT article as a
    one-line headline in global_gdelt_*.json and as full text in
    fulltext_*.json. Without this, whichever file sorts last would win.
    """
    chosen: dict[tuple[str, str], dict] = {}
    order: list[tuple[str, str]] = []
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
            key = (str(record.get("source", "")), str(record.get("id", "")))
            if key not in chosen:
                order.append(key)
                chosen[key] = record
            elif len(record.get("text") or "") > len(chosen[key].get("text") or ""):
                chosen[key] = record
    return [chosen[key] for key in order]


def ingest_processed(
    processed_dir: Path,
    chunker: Any,
    supabase_client: Any,
    openai_client: Any = None,
    files: list[Path] | None = None,
) -> IngestionReport:
    """
    Read all ``*.json`` files in *processed_dir*, chunk each record, embed
    the chunks, and upsert the results into the vector store.

    Parameters
    ----------
    processed_dir:
        Directory containing ``<source>_<date>.json`` files produced by
        ``data/process_raw.py``.
    files:
        Ingest only these files instead of every ``*.json`` in *processed_dir*.
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

    json_files = [Path(f) for f in files] if files is not None else sorted(processed_dir.glob("*.json"))
    json_files = [f for f in json_files if f.name != "quality_report.json"]
    if not json_files:
        print("[ingest] No processed JSON files found — nothing to ingest.")
        return report

    for record in load_records(json_files):

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
            chunk_embeddings = embed_chunks(chunks, openai_client, batch_size=EMBED_BATCH)
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
        if supabase_client is not None:
            try:
                _retry(lambda: delete_stale_chunks(supabase_client, doc_uuid, len(chunks)))
            except Exception as exc:  # noqa: BLE001
                print(f"  [ingest][warn] could not delete stale chunks of '{record.get('id', '?')}': {exc}")

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


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Chunk, embed and store processed records in Supabase.")
    parser.add_argument("files", nargs="*", type=Path, help="processed JSON files to ingest")
    parser.add_argument("--all", action="store_true", help="ingest every data/processed/*.json")
    args = parser.parse_args()
    if not args.files and not args.all:
        parser.error("give processed files to ingest, or --all")

    from dotenv import load_dotenv

    load_dotenv()
    from supabase import create_client

    from rag.chunking.chunker import PRODUCTION_CHUNK_CONFIG, Chunker
    from rag.vector_store.local_embeddings import build_embedding_client
    from scripts.config import SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL

    processed_dir = Path(__file__).resolve().parent / "processed"
    print(f"[ingest] chunking: {PRODUCTION_CHUNK_CONFIG}")
    ingest_processed(
        processed_dir,
        Chunker(PRODUCTION_CHUNK_CONFIG),
        create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY),
        build_embedding_client(),
        files=None if args.all else args.files,
    )


if __name__ == "__main__":
    main()
