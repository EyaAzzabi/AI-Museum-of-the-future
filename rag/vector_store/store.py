"""Upsert documents and chunks into Supabase (see rag/schema.sql).

Task 4.3 — Requirements: 2.5, 2.6
"""

from __future__ import annotations

from datetime import datetime

from rag.chunking.chunker import Chunk


def _parse_published_at(value) -> str | None:
    """Return an ISO datetime string if `value` parses as one, else None.

    Source records aren't consistent here — e.g. some Wikidata records carry
    a bare year like "2013" instead of a full date, which Postgres's
    `timestamptz` column rejects outright (not silently truncates). Rather
    than crash the whole ingestion run on one malformed record, skip
    `published_at` for anything that doesn't parse and keep the raw value in
    metadata instead.
    """
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            dt = datetime.strptime(text, fmt)
        except ValueError:
            continue
        if fmt == "%Y":
            dt = dt.replace(month=1, day=1)
        elif fmt == "%Y-%m":
            dt = dt.replace(day=1)
        return dt.isoformat()
    return None


def upsert_document(supabase_client, record: dict) -> str:
    """Upsert one processed-schema record into the `documents` table.

    Returns the row's UUID (`documents.id`), or `""` if the response carried
    no data.
    """
    raw_date = record.get("date")
    row = {
        "source_id": record.get("id", ""),
        "source": record.get("source", ""),
        "category": record.get("category", ""),
        "title": record.get("title", ""),
        "raw_text": record.get("text", ""),
        "url": record.get("url"),
        "metadata": {
            "image_url": record.get("image_url"),
            "lang": record.get("lang"),
            "tags": record.get("tags", []),
            "raw_source": record.get("raw_source"),
            "processed_on": record.get("processed_on"),
            "date_raw": raw_date,
        },
    }
    published_at = _parse_published_at(raw_date)
    if published_at:
        row["published_at"] = published_at

    # Without on_conflict, PostgREST's upsert only dedupes on the primary key
    # (id) — since we never pass one, every call would just INSERT a fresh
    # row even for a record we've already ingested. source_id is the actual
    # natural key (see rag/schema.sql's documents_source_source_id_idx).
    response = (
        supabase_client.table("documents")
        .upsert(row, on_conflict="source,source_id")
        .execute()
    )
    data = response.data
    return data[0].get("id", "") if data else ""


def upsert_chunks(
    supabase_client,
    chunk_embeddings: list[tuple[Chunk, list[float]]],
    document_uuid: str,
) -> int:
    """Batch-upsert (chunk, embedding) pairs into the `chunks` table.

    Returns the number of rows written. Does nothing (and returns 0) for an
    empty input — no point round-tripping to Supabase for zero rows.
    """
    if not chunk_embeddings:
        return 0

    rows = [
        {
            "document_id": document_uuid,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "embedding": vector,
            "metadata": chunk.metadata,
        }
        for chunk, vector in chunk_embeddings
    ]

    # Matches chunks_doc_chunk_idx (see rag/schema.sql) — without this,
    # re-ingesting a document already in the table hits that unique
    # constraint as a hard error instead of updating the existing rows.
    response = (
        supabase_client.table("chunks")
        .upsert(rows, on_conflict="document_id,chunk_index")
        .execute()
    )
    return len(response.data) if response.data else 0
