"""
Chunking strategies for the AI Museum RAG pipeline.

Two strategies are implemented:
  - FIXED_SIZE  : slide a token window over the text with configurable overlap.
  - RECURSIVE   : split on paragraph → line → fixed-size fallback.

Both store the strategy name in chunk.metadata so retrieval can filter by it.

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
from enum import Enum
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# Public data models  (Task 3.1)
# ─────────────────────────────────────────────────────────────────────────────

class ChunkingStrategy(str, Enum):
    FIXED_SIZE = "fixed_size"
    RECURSIVE  = "recursive"


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
    model_name:
        tiktoken encoding name used for tokenisation (default: cl100k_base,
        the encoding used by GPT-4 / text-embedding-3-small).
    """

    strategy: ChunkingStrategy = ChunkingStrategy.FIXED_SIZE
    chunk_size: int = 512
    overlap_pct: float = 0.20
    model_name: str = "cl100k_base"


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

        base_meta = {
            "source":      record.get("source", ""),
            "category":    record.get("category", ""),
            "lang":        record.get("lang"),
            "strategy":    self.config.strategy.value,
            "chunk_size":  self.config.chunk_size,
            "overlap_pct": self.config.overlap_pct,
        }

        if self.config.strategy == ChunkingStrategy.FIXED_SIZE:
            raw_chunks = self._fixed_size(text)
        else:
            raw_chunks = self._recursive(text)

        # Guarantee at least one non-empty chunk
        raw_chunks = [c for c in raw_chunks if c.strip()]
        if not raw_chunks:
            raw_chunks = [text.strip() or "(empty)"]

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
