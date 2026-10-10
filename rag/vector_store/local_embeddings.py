"""Free, local text embeddings (no API key, no network after the first model download).

Exposes the small slice of the OpenAI client interface the codebase uses
(``client.embeddings.create(input=..., model=...)`` -> ``.data[i].embedding``),
so embed_chunks / Retriever / analyze_image work with it unchanged.

The model is multilingual (the corpus mixes English, French, Arabic...) and
outputs 384-dim vectors, which is what rag/schema.sql is sized for.
"""
from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384

_model_cache: dict[str, Any] = {}


def _get_model(name: str) -> Any:
    if name not in _model_cache:
        from fastembed import TextEmbedding

        _model_cache[name] = TextEmbedding(name)
    return _model_cache[name]


class _Embeddings:
    def create(self, input: str | list[str], model: str = EMBEDDING_MODEL, **_: Any) -> Any:
        texts = [input] if isinstance(input, str) else list(input)
        vectors = _get_model(model or EMBEDDING_MODEL).embed(texts)
        return SimpleNamespace(
            data=[SimpleNamespace(embedding=[float(x) for x in v], index=i) for i, v in enumerate(vectors)]
        )


class LocalEmbeddingClient:
    def __init__(self) -> None:
        self.embeddings = _Embeddings()


def build_embedding_client() -> LocalEmbeddingClient:
    return LocalEmbeddingClient()
