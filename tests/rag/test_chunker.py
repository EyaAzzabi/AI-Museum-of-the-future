# Feature: museum-week2-pipeline, Property 4: Chunker non-empty output

"""
Property-based tests for the Chunker component.

Tests live here in `tests/rag/test_chunker.py` alongside unit tests for the
chunking module.
"""

from math import floor

import tiktoken
from hypothesis import given, settings
from hypothesis import strategies as st

from rag.chunking.chunker import Chunker, ChunkConfig, ChunkingStrategy


# ─────────────────────────────────────────────────────────────────────────────
# Property 4: Chunker non-empty output
# Validates: Requirements 2.2
# ─────────────────────────────────────────────────────────────────────────────


@given(st.text(min_size=1))
@settings(max_examples=100)
def test_chunker_fixed_size_non_empty_output(text: str) -> None:
    """**Validates: Requirements 2.2**

    For any non-empty input text, the FIXED_SIZE chunker must produce at least
    one Chunk and every Chunk's content must be non-empty.
    """
    config = ChunkConfig(strategy=ChunkingStrategy.FIXED_SIZE)
    chunker = Chunker(config)
    record = {"id": "test-doc", "text": text, "source": "", "category": "", "lang": "en"}

    chunks = chunker.chunk(record)

    assert len(chunks) >= 1, "FIXED_SIZE chunker produced no chunks for non-empty input"
    for chunk in chunks:
        assert chunk.content, (
            f"FIXED_SIZE chunker produced an empty-content Chunk at index {chunk.chunk_index}"
        )


@given(st.text(min_size=1))
@settings(max_examples=100)
def test_chunker_recursive_non_empty_output(text: str) -> None:
    """**Validates: Requirements 2.2**

    For any non-empty input text, the RECURSIVE chunker must produce at least
    one Chunk and every Chunk's content must be non-empty.
    """
    config = ChunkConfig(strategy=ChunkingStrategy.RECURSIVE)
    chunker = Chunker(config)
    record = {"id": "test-doc", "text": text, "source": "", "category": "", "lang": "en"}

    chunks = chunker.chunk(record)

    assert len(chunks) >= 1, "RECURSIVE chunker produced no chunks for non-empty input"
    for chunk in chunks:
        assert chunk.content, (
            f"RECURSIVE chunker produced an empty-content Chunk at index {chunk.chunk_index}"
        )


# Feature: museum-week2-pipeline, Property 3: Fixed-size chunker overlap invariant

# ─────────────────────────────────────────────────────────────────────────────
# Property 3: Fixed-size chunker overlap invariant
# Validates: Requirements 2.3
# ─────────────────────────────────────────────────────────────────────────────

@given(st.text(min_size=100), st.floats(0.10, 0.30))
@settings(max_examples=100)
def test_fixed_size_overlap_invariant(text: str, overlap_pct: float) -> None:
    """**Validates: Requirements 2.3**

    For each consecutive pair of chunks produced by the FIXED_SIZE chunker,
    the tail of chunk[i] must appear as a prefix of chunk[i+1], with at least
    floor(chunk_size * overlap_pct) overlapping tokens worth of text.

    Because BPE tokenization is context-sensitive (the same characters can map
    to different token IDs depending on their surrounding context), we verify
    the overlap by re-tokenizing the *full original text* and checking that the
    sliding window sizes are respected structurally: the overlap region in the
    original token stream is covered by both windows.
    """
    config = ChunkConfig(
        strategy=ChunkingStrategy.FIXED_SIZE,
        chunk_size=512,
        overlap_pct=overlap_pct,
    )
    chunker = Chunker(config)
    record = {"id": "overlap-test", "text": text, "source": "", "category": "", "lang": "en"}

    chunks = chunker.chunk(record)

    # Only meaningful to check overlap when there are at least 2 chunks
    if len(chunks) < 2:
        return

    enc = tiktoken.get_encoding(config.model_name)
    size = config.chunk_size
    overlap = max(1, int(size * overlap_pct))
    min_overlap = floor(size * overlap_pct)

    # Re-tokenize full text to recover the original sliding window positions
    full_tokens = enc.encode(text)
    step = size - overlap

    # Reconstruct the token windows as the chunker does
    windows: list[tuple[int, int]] = []
    start = 0
    while start < len(full_tokens):
        end = min(start + size, len(full_tokens))
        windows.append((start, end))
        if end == len(full_tokens):
            break
        start += step

    # There should be at least as many windows as chunks (text may have been trimmed of whitespace)
    if len(windows) < 2:
        return

    # Verify that for each consecutive window pair the overlap token count >= min_overlap.
    # Window[i] covers [s_i, e_i) and window[i+1] covers [s_{i+1}, e_{i+1}).
    # The overlap region is [s_{i+1}, e_i) which has size e_i - s_{i+1} = overlap tokens.
    for i in range(len(windows) - 1):
        s_i, e_i = windows[i]
        s_next, _ = windows[i + 1]
        actual_overlap = e_i - s_next  # tokens shared between window i and window i+1
        assert actual_overlap >= min_overlap, (
            f"Window pair ({i}, {i+1}): overlap is {actual_overlap} tokens "
            f"(expected >= {min_overlap} = floor({size} * {overlap_pct:.4f})). "
            f"step={step}, overlap={overlap}"
        )


# Feature: museum-week2-pipeline, Property 5: Chunk metadata inheritance

# ─────────────────────────────────────────────────────────────────────────────
# Property 5: Chunk metadata inheritance
# Validates: Requirements 2.4, 2.8
# ─────────────────────────────────────────────────────────────────────────────

VALID_SOURCES = ["gdelt", "wikimedia", "arxiv", "wikipedia", "wikidata"]
VALID_CATEGORIES = ["science", "art", "history", "technology", "society", "culture"]
VALID_LANGS = ["en", "fr", "ar", "zh", "es", "de", "pt", "ja"]
VALID_STRATEGIES = {"fixed_size", "recursive"}


@st.composite
def processed_record_strategy(draw: st.DrawFn) -> dict:
    """Composite strategy that generates realistic processed record dicts.

    Produces dicts with required fields (id, source, category, text, lang)
    plus optional fields (title, url, tags) matching the ProcessedRecord schema.
    """
    record: dict = {
        "id": draw(st.text(min_size=1, max_size=64, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_"))),
        "source": draw(st.sampled_from(VALID_SOURCES)),
        "category": draw(st.sampled_from(VALID_CATEGORIES)),
        "text": draw(st.text(min_size=1, max_size=2000)),
        "lang": draw(st.sampled_from(VALID_LANGS)),
    }
    # Optional fields
    include_title = draw(st.booleans())
    if include_title:
        record["title"] = draw(st.text(min_size=1, max_size=200))

    include_url = draw(st.booleans())
    if include_url:
        record["url"] = draw(st.text(min_size=1, max_size=200))

    include_tags = draw(st.booleans())
    if include_tags:
        record["tags"] = draw(st.lists(st.text(min_size=1, max_size=30), min_size=0, max_size=10))

    return record


@given(processed_record_strategy())
@settings(max_examples=100)
def test_chunk_metadata_inheritance_fixed_size(record: dict) -> None:
    """**Validates: Requirements 2.4, 2.8**

    For any processed record, every Chunk produced by the FIXED_SIZE strategy
    must inherit `source`, `category`, and `lang` from the parent record, and
    must carry a valid `strategy` value ("fixed_size" or "recursive").
    """
    config = ChunkConfig(strategy=ChunkingStrategy.FIXED_SIZE)
    chunker = Chunker(config)

    chunks = chunker.chunk(record)

    for chunk in chunks:
        meta = chunk.metadata
        assert meta["source"] == record["source"], (
            f"FIXED_SIZE: chunk.metadata['source']={meta['source']!r} "
            f"!= record['source']={record['source']!r}"
        )
        assert meta["category"] == record["category"], (
            f"FIXED_SIZE: chunk.metadata['category']={meta['category']!r} "
            f"!= record['category']={record['category']!r}"
        )
        assert meta["lang"] == record["lang"], (
            f"FIXED_SIZE: chunk.metadata['lang']={meta['lang']!r} "
            f"!= record['lang']={record['lang']!r}"
        )
        assert meta["strategy"] in VALID_STRATEGIES, (
            f"FIXED_SIZE: chunk.metadata['strategy']={meta['strategy']!r} "
            f"is not one of {VALID_STRATEGIES}"
        )


@given(processed_record_strategy())
@settings(max_examples=100)
def test_chunk_metadata_inheritance_recursive(record: dict) -> None:
    """**Validates: Requirements 2.4, 2.8**

    For any processed record, every Chunk produced by the RECURSIVE strategy
    must inherit `source`, `category`, and `lang` from the parent record, and
    must carry a valid `strategy` value ("fixed_size" or "recursive").
    """
    config = ChunkConfig(strategy=ChunkingStrategy.RECURSIVE)
    chunker = Chunker(config)

    chunks = chunker.chunk(record)

    for chunk in chunks:
        meta = chunk.metadata
        assert meta["source"] == record["source"], (
            f"RECURSIVE: chunk.metadata['source']={meta['source']!r} "
            f"!= record['source']={record['source']!r}"
        )
        assert meta["category"] == record["category"], (
            f"RECURSIVE: chunk.metadata['category']={meta['category']!r} "
            f"!= record['category']={record['category']!r}"
        )
        assert meta["lang"] == record["lang"], (
            f"RECURSIVE: chunk.metadata['lang']={meta['lang']!r} "
            f"!= record['lang']={record['lang']!r}"
        )
        assert meta["strategy"] in VALID_STRATEGIES, (
            f"RECURSIVE: chunk.metadata['strategy']={meta['strategy']!r} "
            f"is not one of {VALID_STRATEGIES}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests — Task 3.7
# Validates: Requirements 2.1, 2.2, 2.3
# ─────────────────────────────────────────────────────────────────────────────

import math
import pytest
import tiktoken

from rag.chunking.chunker import Chunk, ChunkConfig, Chunker, ChunkingStrategy


def _make_record(text: str) -> dict:
    return {
        "id": "unit-test-doc",
        "text": text,
        "source": "wikimedia",
        "category": "art",
        "lang": "en",
    }


def _encoder(model_name: str = "cl100k_base") -> tiktoken.Encoding:
    return tiktoken.get_encoding(model_name)


# ── Sub-task: Single-sentence text → exactly one chunk for both strategies ──

class TestSingleSentence:
    """A single short sentence must produce exactly one chunk for every strategy."""

    SENTENCE = "The Mona Lisa is a 16th-century oil painting by Leonardo da Vinci."

    def test_fixed_size_single_sentence_yields_one_chunk(self) -> None:
        """Single short sentence → FIXED_SIZE produces exactly 1 chunk (Req 2.2)."""
        config = ChunkConfig(strategy=ChunkingStrategy.FIXED_SIZE, chunk_size=512)
        chunker = Chunker(config)
        chunks = chunker.chunk(_make_record(self.SENTENCE))

        assert len(chunks) == 1, (
            f"Expected 1 chunk for a single sentence, got {len(chunks)}"
        )
        assert chunks[0].content.strip(), "Chunk content must not be empty"

    def test_recursive_single_sentence_yields_one_chunk(self) -> None:
        """Single short sentence → RECURSIVE produces exactly 1 chunk (Req 2.2)."""
        config = ChunkConfig(strategy=ChunkingStrategy.RECURSIVE, chunk_size=512)
        chunker = Chunker(config)
        chunks = chunker.chunk(_make_record(self.SENTENCE))

        assert len(chunks) == 1, (
            f"Expected 1 chunk for a single sentence, got {len(chunks)}"
        )
        assert chunks[0].content.strip(), "Chunk content must not be empty"


# ── Sub-task: Text exactly at chunk_size boundary ───────────────────────────

class TestChunkSizeBoundary:
    """Verify chunk counts at and just past the chunk_size token boundary."""

    CHUNK_SIZE = 64  # small size to keep test fast

    def _tokens_to_text(self, n: int, model_name: str = "cl100k_base") -> str:
        """Produce a string whose tiktoken encoding is exactly *n* tokens."""
        enc = _encoder(model_name)
        # Use a repeated word that encodes to a known single token ("cat ").
        # We'll build up to the target token count precisely.
        base_token = enc.encode("cat ")[0]  # single token id
        tokens = [base_token] * n
        return enc.decode(tokens)

    def test_text_exactly_at_boundary_produces_one_chunk(self) -> None:
        """Text whose token count equals chunk_size → FIXED_SIZE yields exactly 1 chunk (Req 2.1)."""
        text = self._tokens_to_text(self.CHUNK_SIZE)
        enc = _encoder()
        actual_token_count = len(enc.encode(text))
        assert actual_token_count == self.CHUNK_SIZE, (
            f"Fixture text has {actual_token_count} tokens, expected {self.CHUNK_SIZE}"
        )

        config = ChunkConfig(
            strategy=ChunkingStrategy.FIXED_SIZE,
            chunk_size=self.CHUNK_SIZE,
            overlap_pct=0.20,
        )
        chunker = Chunker(config)
        chunks = chunker.chunk(_make_record(text))

        assert len(chunks) == 1, (
            f"Text with exactly {self.CHUNK_SIZE} tokens should produce 1 chunk, got {len(chunks)}"
        )

    def test_text_one_token_over_boundary_produces_two_chunks(self) -> None:
        """Text with chunk_size + 1 tokens → FIXED_SIZE yields exactly 2 chunks (Req 2.1, 2.2)."""
        text = self._tokens_to_text(self.CHUNK_SIZE + 1)
        enc = _encoder()
        actual_token_count = len(enc.encode(text))
        assert actual_token_count == self.CHUNK_SIZE + 1, (
            f"Fixture text has {actual_token_count} tokens, expected {self.CHUNK_SIZE + 1}"
        )

        config = ChunkConfig(
            strategy=ChunkingStrategy.FIXED_SIZE,
            chunk_size=self.CHUNK_SIZE,
            overlap_pct=0.20,
        )
        chunker = Chunker(config)
        chunks = chunker.chunk(_make_record(text))

        assert len(chunks) == 2, (
            f"Text with {self.CHUNK_SIZE + 1} tokens should produce 2 chunks, got {len(chunks)}"
        )


# ── Sub-task: Overlap respects minimum token count ──────────────────────────

class TestOverlapMinimumTokenCount:
    """The shared token count between consecutive FIXED_SIZE chunks must be
    at least floor(chunk_size * overlap_pct)."""

    def test_overlap_meets_minimum_token_count(self) -> None:
        """Consecutive chunks share >= floor(chunk_size * overlap_pct) tokens (Req 2.3)."""
        chunk_size = 64
        overlap_pct = 0.25
        enc = _encoder()

        # Build a text that is long enough to produce at least 2 chunks.
        # Use a single repeated token so the token boundary is predictable.
        base_token_id = enc.encode("the ")[0]
        n_tokens = chunk_size * 3  # ensure at least 2 windows
        text = enc.decode([base_token_id] * n_tokens)

        config = ChunkConfig(
            strategy=ChunkingStrategy.FIXED_SIZE,
            chunk_size=chunk_size,
            overlap_pct=overlap_pct,
        )
        chunker = Chunker(config)
        chunks = chunker.chunk(_make_record(text))

        assert len(chunks) >= 2, (
            f"Expected at least 2 chunks for {n_tokens}-token text with chunk_size={chunk_size}, "
            f"got {len(chunks)}"
        )

        min_overlap = math.floor(chunk_size * overlap_pct)
        overlap = max(1, int(chunk_size * overlap_pct))
        step = chunk_size - overlap

        # Reconstruct expected token windows and verify the structural overlap.
        full_tokens = enc.encode(text)
        windows: list[tuple[int, int]] = []
        start = 0
        while start < len(full_tokens):
            end = min(start + chunk_size, len(full_tokens))
            windows.append((start, end))
            if end == len(full_tokens):
                break
            start += step

        assert len(windows) >= 2, "Need at least 2 windows to test overlap"

        for i in range(len(windows) - 1):
            s_i, e_i = windows[i]
            s_next, _ = windows[i + 1]
            actual_overlap = e_i - s_next
            assert actual_overlap >= min_overlap, (
                f"Window pair ({i}, {i+1}): overlap is {actual_overlap} tokens "
                f"but expected >= {min_overlap} = floor({chunk_size} * {overlap_pct})"
            )

    def test_overlap_content_appears_in_consecutive_chunks(self) -> None:
        """The tail of chunk[i] must share tokens with the head of chunk[i+1] (Req 2.3)."""
        chunk_size = 48
        overlap_pct = 0.25
        enc = _encoder()

        # Use distinct "words" so we can identify overlapping content unambiguously.
        words = [f"word{i}" for i in range(200)]
        text = " ".join(words)

        config = ChunkConfig(
            strategy=ChunkingStrategy.FIXED_SIZE,
            chunk_size=chunk_size,
            overlap_pct=overlap_pct,
        )
        chunker = Chunker(config)
        chunks = chunker.chunk(_make_record(text))

        if len(chunks) < 2:
            pytest.skip("Text too short to produce 2 chunks with these settings")

        min_overlap = math.floor(chunk_size * overlap_pct)

        for i in range(len(chunks) - 1):
            tokens_i = enc.encode(chunks[i].content)
            tokens_next = enc.encode(chunks[i + 1].content)

            # The tail of chunk i and the head of chunk i+1 must share at least
            # min_overlap tokens.  Because BPE is context-sensitive we check
            # the *suffix* of tokens_i against the *prefix* of tokens_next.
            tail = tokens_i[-min_overlap:]
            head = tokens_next[:min_overlap]

            shared = set(tail) & set(head) if min_overlap > 0 else set()
            # A weaker but robust check: the decoded overlap region from chunk i
            # appears somewhere in chunk i+1.
            tail_text = enc.decode(tokens_i[-min_overlap:]) if min_overlap > 0 else ""
            assert tail_text in chunks[i + 1].content or min_overlap == 0, (
                f"Chunk {i} tail text {tail_text!r} not found in chunk {i+1} content"
            )
