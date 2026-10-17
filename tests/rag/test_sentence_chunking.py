"""SENTENCE chunking: whole sentences, sized to the embedding model's 128-token window."""
from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from rag.chunking.chunker import (
    TITLE_SEPARATOR,
    Chunker,
    ChunkConfig,
    ChunkingStrategy,
    _embedding_token_counter,
    _sentences,
)

COUNT = _embedding_token_counter()
SENTENCE = ChunkConfig(strategy=ChunkingStrategy.SENTENCE, chunk_size=128, overlap_pct=0.20)

ARTICLE = " ".join(
    f"In {2000 + i}, the Tunisian parliament debated reform number {i} of the national budget and public debt."
    for i in range(40)
)


def _record(text: str, title: str = "Economy of Tunisia") -> dict:
    return {"id": "doc-1", "source": "wikipedia", "category": "economy", "lang": "en", "title": title, "text": text}


def test_chunks_fit_the_embedding_window() -> None:
    chunks = Chunker(SENTENCE).chunk(_record(ARTICLE))
    assert len(chunks) > 1
    assert all(COUNT(c.content) <= 130 for c in chunks)  # 128, give or take a token at sentence joins


def test_sentences_are_never_cut() -> None:
    chunks = Chunker(SENTENCE).chunk(_record(ARTICLE))
    for chunk in chunks:
        assert chunk.content.startswith("In ") and chunk.content.endswith(".")


def test_consecutive_chunks_overlap_by_one_sentence() -> None:
    chunks = Chunker(SENTENCE).chunk(_record(ARTICLE))
    last_sentence = _sentences(chunks[0].content)[-1]
    assert chunks[1].content.startswith(last_sentence)


def test_title_prefix_is_added_and_counted_in_the_budget() -> None:
    config = ChunkConfig(strategy=ChunkingStrategy.SENTENCE, chunk_size=128, overlap_pct=0.20, title_prefix=True)
    chunks = Chunker(config).chunk(_record(ARTICLE))
    assert all(c.content.startswith(f"Economy of Tunisia{TITLE_SEPARATOR}") for c in chunks)
    assert all(COUNT(c.content) <= 130 for c in chunks)
    assert chunks[0].metadata["title_prefix"] is True


def test_no_title_prefix_when_the_text_is_only_the_title() -> None:
    config = ChunkConfig(strategy=ChunkingStrategy.SENTENCE, chunk_size=128, title_prefix=True)
    chunks = Chunker(config).chunk(_record("Short headline", title="Short headline"))
    assert [c.content for c in chunks] == ["Short headline"]


def test_arabic_and_french_sentences_are_split() -> None:
    assert _sentences("تونس دولة. أعلن الرئيس التدابير؟ نعم") == ["تونس دولة.", "أعلن الرئيس التدابير؟", "نعم"]
    assert _sentences("Le 25 juillet 2022, référendum.\nTitre\n\nSuite !") == ["Le 25 juillet 2022, référendum.", "Titre", "Suite !"]


def test_an_over_long_sentence_is_split_on_words() -> None:
    sentence = " ".join(f"word{i}" for i in range(400)) + "."
    chunks = Chunker(SENTENCE).chunk(_record(sentence))
    assert len(chunks) > 1
    assert " ".join(c.content for c in chunks).replace("  ", " ").startswith("word0 word1")


@given(st.text(min_size=1, max_size=600))
@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_any_text_gives_non_empty_chunks(text: str) -> None:
    chunks = Chunker(SENTENCE).chunk(_record(text))
    assert chunks and all(c.content.strip() for c in chunks)


def test_counting_tokens_does_not_change_the_models_truncation() -> None:
    """Regression: the counter once disabled truncation on the model's shared tokenizer,
    and embedding any text longer than 512 tokens then crashed."""
    from rag.vector_store.local_embeddings import EMBEDDING_MODEL, _get_model, build_embedding_client

    _embedding_token_counter()
    assert _get_model(EMBEDDING_MODEL).model.tokenizer.truncation["max_length"] == 128
    vector = build_embedding_client().embeddings.create(input="Tunisian budget debate. " * 400).data[0].embedding
    assert len(vector) == 384
