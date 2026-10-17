"""
Chunking strategies for the AI Museum RAG pipeline.

Three strategies are implemented:
  - FIXED_SIZE  : slide a token window over the text with configurable overlap.
  - RECURSIVE   : split on paragraph → line → fixed-size fallback.
  - SENTENCE    : pack whole sentences up to a budget measured with the
                  EMBEDDING model's own tokenizer, one sentence of overlap.

The embedding model (paraphrase-multilingual-MiniLM-L12-v2) reads only its
first 128 tokens and silently ignores the rest, so a chunk longer than that is
only partly searchable by vector. SENTENCE sizes chunks to what the model
sees and never cuts a sentence. ``title_prefix`` prepends the document title,
so a chunk deep inside an article still names its subject. The choice is
justified by evaluation/compare_chunking.py (see rag/README.md).

All strategies store their settings in chunk.metadata so retrieval can filter by them.

Usage
-----
    from rag.chunking.chunker import Chunker, ChunkConfig, ChunkingStrategy

    config = ChunkConfig(strategy=ChunkingStrategy.FIXED_SIZE, chunk_size=512, overlap_pct=0.20)
    chunker = Chunker(config)
    chunks  = chunker.chunk(processed_record_dict)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from enum import Enum
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# Public data models  (Task 3.1)
# ─────────────────────────────────────────────────────────────────────────────

class ChunkingStrategy(str, Enum):
    FIXED_SIZE = "fixed_size"
    RECURSIVE  = "recursive"
    SENTENCE   = "sentence"


@dataclass
class ChunkConfig:
    """Configuration for the Chunker.

    Attributes
    ----------
    strategy:
        Which splitting algorithm to use.
    chunk_size:
        For FIXED_SIZE  — window size in *tokens*.
        For RECURSIVE   — maximum fragment size in *characters* before falling
                          back to a token-based split.
    overlap_pct:
        Fraction of ``chunk_size`` to repeat at chunk boundaries (0.10–0.30).
        For SENTENCE    — maximum size in tokens of the embedding model,
                          including the title prefix and special tokens.
    model_name:
        tiktoken encoding name used for tokenisation (default: cl100k_base,
        the encoding used by GPT-4 / text-embedding-3-small).
    title_prefix:
        Prepend "<title> — " to every chunk (contextual chunk header).
    """

    strategy: ChunkingStrategy = ChunkingStrategy.FIXED_SIZE
    chunk_size: int = 512
    overlap_pct: float = 0.20
    model_name: str = "cl100k_base"
    title_prefix: bool = False


# Chunking used for ingestion (data/ingest.py, data/fetch_all.py). Chosen by
# evaluation/compare_chunking.py on 23 passage-level questions over 557 long documents:
# best MRR@10 (0.47 vs 0.40 for the former fixed-512), hit@5 0.65 vs 0.52, no text beyond
# the embedder's 128-token window (fixed-512: 57% unseen). See rag/README.md.
PRODUCTION_CHUNK_CONFIG = ChunkConfig(
    strategy=ChunkingStrategy.SENTENCE, chunk_size=128, overlap_pct=0.20, title_prefix=True,
)


@dataclass
class Chunk:
    """A single text fragment produced by the Chunker.

    Attributes
    ----------
    document_id:
        The ``id`` of the parent ProcessedRecord (maps to documents.id in
        Supabase once the store layer is wired up).
    chunk_index:
        Zero-based position of this chunk within the parent document.
    content:
        The decoded text of this chunk.
    metadata:
        Dict containing at minimum ``source``, ``category``, ``lang``,
        ``strategy``, ``chunk_size``, and ``overlap_pct``.
    """

    document_id: str
    chunk_index: int
    content: str
    metadata: dict = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_encoding(model_name: str) -> Any:
    """Return a tiktoken encoding, with a graceful fallback when tiktoken is
    unavailable (e.g. in lightweight test environments)."""
    try:
        import tiktoken  # type: ignore[import]
        return tiktoken.get_encoding(model_name)
    except ImportError:
        return None


# Sentence ends: Latin and Arabic punctuation, or a line break (headings, lists).
_SENTENCE_END = re.compile(r"(?<=[.!?؟。])\s+|\n+")
TITLE_SEPARATOR = " — "


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_END.split(text) if s and s.strip()]


@lru_cache(maxsize=1)
def _embedding_token_counter() -> Any:
    """Token counter of the embedding model (special tokens included), or None if unavailable."""
    try:
        from rag.vector_store.local_embeddings import EMBEDDING_MODEL, _get_model

        from tokenizers import Tokenizer

        # A private copy: disabling truncation on the model's own tokenizer would make
        # it feed inputs longer than 512 tokens to the model, which then fails.
        tokenizer = Tokenizer.from_str(_get_model(EMBEDDING_MODEL).model.tokenizer.to_str())
        tokenizer.no_truncation()  # count every token
        return lambda text: len(tokenizer.encode(text).ids)
    except Exception:  # noqa: BLE001 - no fastembed (e.g. light test environments)
        return None


def _last_sentence(text: str) -> str:
    """Return the last sentence of *text* (best-effort, used for overlap)."""
    text = text.rstrip()
    # Try splitting on sentence-ending punctuation
    parts = re.split(r"(?<=[.!?])\s+", text)
    return parts[-1] if parts else text


# ─────────────────────────────────────────────────────────────────────────────
# Chunker  (Tasks 3.2 & 3.3)
# ─────────────────────────────────────────────────────────────────────────────

class Chunker:
    """Split a ProcessedRecord into a list of Chunks.

    Parameters
    ----------
    config:
        A ``ChunkConfig`` instance controlling strategy and parameters.
    """

    def __init__(self, config: ChunkConfig | None = None) -> None:
        self.config = config or ChunkConfig()
        self._enc = _get_encoding(self.config.model_name)
        self._count = None  # embedding-model token counter, loaded on first SENTENCE use

    # ── public API ──────────────────────────────────────────────────────────

    def chunk(self, record: dict) -> list[Chunk]:
        """Split *record* into Chunks according to ``self.config.strategy``.

        Parameters
        ----------
        record:
            A dict conforming to the ProcessedRecord schema (must have an
            ``id`` field and a ``text`` field).

        Returns
        -------
        list[Chunk]
            At least one Chunk; no Chunk will have an empty ``content``.
        """
        text: str = record.get("text", "") or record.get("title", "") or ""
        doc_id: str = str(record.get("id", ""))

        title = str(record.get("title") or "").strip()
        prefix = f"{title}{TITLE_SEPARATOR}" if self.config.title_prefix and title and title != text.strip() else ""

        base_meta = {
            "source":      record.get("source", ""),
            "category":    record.get("category", ""),
            "lang":        record.get("lang"),
            "strategy":    self.config.strategy.value,
            "chunk_size":  self.config.chunk_size,
            "overlap_pct": self.config.overlap_pct,
        }
        if self.config.title_prefix:
            base_meta["title_prefix"] = bool(prefix)

        if self.config.strategy == ChunkingStrategy.FIXED_SIZE:
            raw_chunks = self._fixed_size(text)
        elif self.config.strategy == ChunkingStrategy.SENTENCE:
            raw_chunks = self._sentence(text, prefix)
        else:
            raw_chunks = self._recursive(text)

        # Guarantee at least one non-empty chunk
        raw_chunks = [c for c in raw_chunks if c.strip()]
        if not raw_chunks:
            raw_chunks = [text.strip() or "(empty)"]
        if prefix:
            raw_chunks = [prefix + c for c in raw_chunks]

        return [
            Chunk(
                document_id=doc_id,
                chunk_index=i,
                content=content,
                metadata=dict(base_meta),
            )
            for i, content in enumerate(raw_chunks)
        ]

    # ── fixed-size strategy  (Task 3.2) ─────────────────────────────────────

    def _fixed_size(self, text: str) -> list[str]:
        """Slide a token window over *text* with configurable overlap.

        Falls back to character-based splitting when tiktoken is unavailable.
        """
        size    = self.config.chunk_size
        overlap = max(1, int(size * self.config.overlap_pct))

        if self._enc is not None:
            return self._fixed_size_tokens(text, size, overlap)
        else:
            return self._fixed_size_chars(text, size, overlap)

    def _fixed_size_tokens(self, text: str, size: int, overlap: int) -> list[str]:
        tokens = self._enc.encode(text)
        if not tokens:
            return []

        chunks: list[str] = []
        start = 0
        step  = size - overlap  # advance by (size - overlap) each iteration

        while start < len(tokens):
            end    = min(start + size, len(tokens))
            window = tokens[start:end]
            decoded = self._enc.decode(window)
            if decoded.strip():
                chunks.append(decoded)
            if end == len(tokens):
                break
            start += step

        return chunks

    def _fixed_size_chars(self, text: str, size: int, overlap: int) -> list[str]:
        """Character-based fallback (no tiktoken)."""
        if not text:
            return []

        chunks: list[str] = []
        step   = size - overlap
        start  = 0

        while start < len(text):
            end   = min(start + size, len(text))
            chunk = text[start:end]
            if chunk.strip():
                chunks.append(chunk)
            if end == len(text):
                break
            start += step

        return chunks

    # ── recursive strategy  (Task 3.3) ──────────────────────────────────────

    def _recursive(self, text: str) -> list[str]:
        """Split on paragraphs → lines → fixed-size fallback.

        Overlap is applied at the paragraph level by prepending the last
        sentence of the previous paragraph to the current one.
        """
        max_chars = self.config.chunk_size  # treat chunk_size as char limit here
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

        if not paragraphs:
            return self._fixed_size(text)

        fragments: list[str] = []
        prev_tail  = ""          # last sentence of previous paragraph (overlap)

        for para in paragraphs:
            # Prepend overlap from previous paragraph
            candidate = (prev_tail + " " + para).strip() if prev_tail else para

            if len(candidate) <= max_chars:
                fragments.append(candidate)
            else:
                # Split on single newlines first
                lines = [ln.strip() for ln in candidate.split("\n") if ln.strip()]
                for line in lines:
                    if len(line) <= max_chars:
                        fragments.append(line)
                    else:
                        # Final fallback: fixed-size character split
                        fragments.extend(self._fixed_size_chars(line, max_chars, max(1, int(max_chars * self.config.overlap_pct))))

            prev_tail = _last_sentence(para)

        return [f for f in fragments if f.strip()]

    # ── sentence strategy ───────────────────────────────────────────────────

    def _sentence(self, text: str, prefix: str = "") -> list[str]:
        """Pack whole sentences into chunks that fit the embedding model's window.

        The budget (``chunk_size``) counts the embedding model's tokens, special
        tokens and the title prefix included. The last sentence of a chunk is
        repeated at the start of the next one when it is short (overlap). A
        single sentence longer than the budget is split on words.
        """
        if self._count is None:
            counter = _embedding_token_counter()
            if counter is None and self._enc is not None:
                counter = lambda t: len(self._enc.encode(t)) + 2  # noqa: E731 - tiktoken approximation
            self._count = counter or (lambda t: len(t.split()) + 2)  # noqa: E731
        # Each sentence/word is tokenized once and sizes are added up: re-tokenizing
        # the growing chunk at every step made this quadratic. Token counts of joined
        # sentences add up (within a token or two) with this model's tokenizer.
        def size(t: str) -> int:
            return max(1, self._count(t) - 2)  # content tokens, without [CLS]/[SEP]

        budget = max(16, self.config.chunk_size - 2 - (size(prefix) if prefix else 0))

        pieces: list[tuple[str, int]] = []
        for sentence in _sentences(text):
            n = size(sentence)
            if n <= budget:
                pieces.append((sentence, n))
                continue
            current, used = [], 0  # an over-long sentence: cut on words
            for word in sentence.split():
                w = size(word)
                if current and used + w > budget:
                    pieces.append((" ".join(current), used))
                    current, used = [], 0
                current.append(word)
                used += w
            if current:
                pieces.append((" ".join(current), used))

        chunks: list[str] = []
        current: list[tuple[str, int]] = []
        used = 0
        for piece, n in pieces:
            if current and used + n > budget:
                chunks.append(" ".join(p for p, _ in current))
                tail = current[-1]
                keep_tail = (self.config.overlap_pct > 0 and tail[1] <= budget * self.config.overlap_pct * 2
                             and tail[1] + n <= budget)
                current = [tail] if keep_tail else []
                used = tail[1] if keep_tail else 0
            current.append((piece, n))
            used += n
        if current:
            chunks.append(" ".join(p for p, _ in current))
        return chunks
