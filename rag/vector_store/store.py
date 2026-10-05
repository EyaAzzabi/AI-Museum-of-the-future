"""Upsert documents and chunks into Supabase (see rag/schema.sql).

Task 4.3 — Requirements: 2.5, 2.6
"""

from __future__ import annotations

from rag.chunking.chunker import Chunk


def upsert_document(supabase_client, record: dict) -> str:
    """Upsert one processed-schema record into the `documents` table.

    Returns the row's UUID (`documents.id`), or `""` if the response carried
    no data.
    """
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
        },
    }
    if record.get("date"):
        row["published_at"] = record["date"]

    response = supabase_client.table("documents").upsert(row).execute()
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

    response = supabase_client.table("chunks").upsert(rows).execute()
    return len(response.data) if response.data else 0
