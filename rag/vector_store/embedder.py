"""Embed Chunks via an embeddings client (local fastembed by default, see local_embeddings.py), with per-chunk retry.

Task 4.3 — Requirements: 2.5, 2.6
"""

from __future__ import annotations

import time

from rag.chunking.chunker import Chunk
from rag.vector_store.local_embeddings import EMBEDDING_MODEL


def embed_chunks(
    chunks: list[Chunk],
    openai_client,
    model: str = EMBEDDING_MODEL,
    max_retries: int = 3,
    batch_size: int = 1,
) -> list[tuple[Chunk, list[float]]]:
    """Embed each chunk's content, retrying transient failures.

    A chunk that still fails after ``max_retries`` attempts is excluded from
    the result (logged with a ``[skip]`` line) rather than aborting the
    whole batch — a handful of bad chunks shouldn't block everything else.

    ``batch_size`` > 1 embeds that many chunks per call (several times faster
    with the local model); a failed batch falls back to one call per chunk.
    """
    if batch_size > 1:
        results: list[tuple[Chunk, list[float]]] = []
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start:start + batch_size]
            try:
                response = openai_client.embeddings.create(input=[c.content for c in batch], model=model)
                vectors = [item.embedding for item in response.data]
                if len(vectors) != len(batch):
                    raise ValueError("embedding count does not match the batch")
                results.extend(zip(batch, vectors))
            except Exception:  # noqa: BLE001 - retry this batch chunk by chunk
                results.extend(embed_chunks(batch, openai_client, model, max_retries))
        return results

    results = []

    for chunk in chunks:
        vector: list[float] | None = None
        last_error: Exception | None = None

        for attempt in range(1, max_retries + 1):
            try:
                response = openai_client.embeddings.create(input=chunk.content, model=model)
                vector = response.data[0].embedding
                break
            except Exception as e:  # noqa: BLE001 - any embedding-call failure is retryable
                last_error = e
                if attempt == max_retries:
                    print(
                        f"[skip] chunk {chunk.chunk_index} of document {chunk.document_id} "
                        f"failed after {max_retries} attempts: {last_error}"
                    )
                else:
                    time.sleep(2 ** attempt * 0.1)

        if vector is not None:
            results.append((chunk, vector))

    return results
