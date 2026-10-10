from __future__ import annotations

from unittest.mock import MagicMock, patch

from rag.vector_store import local_embeddings
from rag.vector_store.local_embeddings import EMBEDDING_DIM, LocalEmbeddingClient


def test_client_mimics_openai_embeddings_interface():
    fake_model = MagicMock()
    fake_model.embed.side_effect = lambda texts: ([0.5] * EMBEDDING_DIM for _ in texts)
    with patch.dict(local_embeddings._model_cache, {local_embeddings.EMBEDDING_MODEL: fake_model}):
        client = LocalEmbeddingClient()
        single = client.embeddings.create(input="bonjour", model=local_embeddings.EMBEDDING_MODEL)
        batch = client.embeddings.create(input=["a", "b"], model=local_embeddings.EMBEDDING_MODEL)
    assert len(single.data) == 1 and len(single.data[0].embedding) == EMBEDDING_DIM
    assert [d.index for d in batch.data] == [0, 1]


def test_schema_dimension_matches_embedding_model():
    from pathlib import Path

    schema = (Path(__file__).resolve().parents[2] / "rag" / "schema.sql").read_text(encoding="utf-8")
    assert f"vector({EMBEDDING_DIM})" in schema and "vector(1536)" not in schema
