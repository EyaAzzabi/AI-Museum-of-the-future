"""Embed Chunks via the OpenAI embeddings API, with per-chunk retry.

Task 4.3 — Requirements: 2.5, 2.6
"""

from __future__ import annotations

import time

from rag.chunking.chunker import Chunk


def embed_chunks(
    chunks: list[Chunk],
    openai_client,
    model: str = "text-embedding-3-small",
    max_retries: int = 3,
) -> list[tuple[Chunk, list[float]]]:
    """Embed each chunk's content, retrying transient failures.

    A chunk that still fails after ``max_retries`` attempts is excluded from
    the result (logged with a ``[skip]`` line) rather than aborting the
    whole batch — a handful of bad chunks shouldn't block everything else.
    """
    results: list[tuple[Chunk, list[float]]] = []

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
