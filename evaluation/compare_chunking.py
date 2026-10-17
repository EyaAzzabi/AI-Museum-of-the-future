"""Compare chunking strategies on the long-text corpus (local, no database writes, no LLM).

    python -m evaluation.compare_chunking            # all configurations
    python -m evaluation.compare_chunking --k 5

Corpus: the long documents in data/processed/ (Tunisian Wikipedia articles in
English, French and Arabic, full-text news and archive items, arXiv
abstracts). Most of the database is one-line headlines that no strategy
splits, so comparing chunking there would measure nothing.

For every configuration the corpus is chunked, every chunk is embedded with
the production model (local MiniLM, rag/vector_store/local_embeddings.py) and
the questions of evaluation/chunking_cases.json are answered by cosine
search over all chunks, as match_chunks does. A retrieved chunk is a hit when
its text (title prefix excluded) contains the answer terms.

Embeddings are cached in .cache/chunking/ (one file per configuration and
corpus), so a rerun only embeds what changed. Results go to
evaluation/results/chunking_<date>.json and are printed as Markdown.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np

from evaluation.metrics import matches_terms, mean
from rag.chunking.chunker import (
    TITLE_SEPARATOR,
    ChunkConfig,
    Chunker,
    ChunkingStrategy,
    _embedding_token_counter,
)

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
CACHE = ROOT / ".cache" / "chunking"
MODEL_WINDOW = 128  # tokens the embedding model reads; the rest of a chunk is ignored


@dataclass(frozen=True)
class Setup:
    name: str
    config: ChunkConfig
    note: str


SETUPS = [
    Setup("fixed-512", ChunkConfig(ChunkingStrategy.FIXED_SIZE, 512, 0.20),
          "current production: 512 tiktoken tokens, 20% overlap"),
    Setup("fixed-100", ChunkConfig(ChunkingStrategy.FIXED_SIZE, 100, 0.20),
          "100 tiktoken tokens, 20% overlap: sized to the model window"),
    Setup("recursive-600", ChunkConfig(ChunkingStrategy.RECURSIVE, 600, 0.20),
          "paragraphs up to 600 characters (existing recursive strategy)"),
    Setup("sentence-128", ChunkConfig(ChunkingStrategy.SENTENCE, 128, 0.20),
          "whole sentences packed up to 128 tokens of the embedding model"),
    Setup("sentence-128+title", ChunkConfig(ChunkingStrategy.SENTENCE, 128, 0.20, title_prefix=True),
          "same, each chunk prefixed with its document title"),
]


def load_corpus(min_chars: int = 1000) -> list[dict]:
    """Long documents only, deduplicated by id (the longest text wins)."""
    records: dict[str, dict] = {}
    files = sorted(PROCESSED.glob("tunisia_wikipedia_*.json")) + sorted(PROCESSED.glob("fulltext_*.json")) \
        + sorted(PROCESSED.glob("*arxiv*.json"))
    for path in files:
        for record in json.loads(path.read_text(encoding="utf-8")):
            text = record.get("text") or ""
            if len(text) < min_chars:
                continue
            key = str(record.get("id"))
            if key not in records or len(text) > len(records[key]["text"]):
                records[key] = record
    return list(records.values())


def body(chunk_text: str, title: str, prefixed: bool) -> str:
    head = f"{title}{TITLE_SEPARATOR}"
    return chunk_text[len(head):] if prefixed and chunk_text.startswith(head) else chunk_text


def embed(texts: list[str]) -> np.ndarray:
    from rag.vector_store.local_embeddings import EMBEDDING_MODEL, _get_model

    vectors = np.array(list(_get_model(EMBEDDING_MODEL).embed(texts, batch_size=64)), dtype=np.float32)
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


def run_setup(setup: Setup, corpus: list[dict], cases: list[dict], query_vectors: np.ndarray, k: int, count) -> dict:
    chunker = Chunker(setup.config)
    chunks, bodies, owners = [], [], []
    for doc_index, record in enumerate(corpus):
        for chunk in chunker.chunk(record):
            chunks.append(chunk.content)
            bodies.append(body(chunk.content, str(record.get("title") or "").strip(), setup.config.title_prefix))
            owners.append(doc_index)

    key = hashlib.sha256(("\0".join(chunks)).encode("utf-8")).hexdigest()[:16]
    cache = CACHE / f"{setup.name}-{key}.npy"
    started = time.monotonic()
    if cache.exists():
        vectors = np.load(cache)
    else:
        vectors = embed(chunks)
        CACHE.mkdir(parents=True, exist_ok=True)
        np.save(cache, vectors)
    embed_s = time.monotonic() - started

    tokens = [count(c) for c in chunks]
    rows = []
    for case, qv in zip(cases, query_vectors):
        ranking = np.argsort(-(vectors @ qv))[:10]
        hits = [matches_terms(bodies[i], case["answer"]) for i in ranking]
        first = next((r for r, h in enumerate(hits) if h), None)
        answerable = any(matches_terms(b, case["answer"]) for b in bodies)
        rows.append({
            "id": case["id"],
            "hit@1": float(hits[0]),
            f"hit@{k}": float(any(hits[:k])),
            "rr@10": 1.0 / (first + 1) if first is not None else 0.0,
            "answerable": answerable,
            "top": [chunks[i][:160] for i in ranking[:3]],
        })
    return {
        "note": setup.note,
        "chunks": len(chunks),
        "chunks_per_doc": round(len(chunks) / len(corpus), 1),
        "mean_tokens": round(mean(tokens), 1),
        "share_over_window": round(sum(t > MODEL_WINDOW for t in tokens) / len(tokens), 3),
        "text_unseen_by_embedder": round(sum(max(0, t - MODEL_WINDOW) for t in tokens) / sum(tokens), 3),
        "hit@1": round(mean(r["hit@1"] for r in rows), 3),
        f"hit@{k}": round(mean(r[f"hit@{k}"] for r in rows), 3),
        "mrr@10": round(mean(r["rr@10"] for r in rows), 3),
        "answerable": round(mean(r["answerable"] for r in rows), 3),
        "context_tokens_top_k": round(mean(tokens) * k),
        "embed_seconds": round(embed_s, 1),
        "cases": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()

    corpus = load_corpus()
    cases = json.loads((ROOT / "evaluation" / "chunking_cases.json").read_text(encoding="utf-8"))["cases"]
    count = _embedding_token_counter()
    query_vectors = embed([c["query"] for c in cases])
    chars = sum(len(r["text"]) for r in corpus)
    print(f"Corpus: {len(corpus)} long documents, {chars:,} characters; {len(cases)} questions\n")

    report = {"date": date.today().isoformat(), "k": args.k, "corpus_documents": len(corpus),
              "corpus_characters": chars, "setups": {}}
    for setup in SETUPS:
        print(f"... {setup.name}", flush=True)
        report["setups"][setup.name] = run_setup(setup, corpus, cases, query_vectors, args.k, count)

    out = ROOT / "evaluation" / "results" / f"chunking_{report['date']}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    k = args.k
    print(f"\n| strategy | chunks | mean tokens | text unseen by embedder | hit@1 | hit@{k} | MRR@10 | answerable | context tokens (top {k}) |")
    print("|---|---|---|---|---|---|---|---|---|")
    for name, r in report["setups"].items():
        print(f"| {name} | {r['chunks']} | {r['mean_tokens']} | {r['text_unseen_by_embedder']:.0%} | {r['hit@1']:.2f} | "
              f"{r[f'hit@{k}']:.2f} | {r['mrr@10']:.2f} | {r['answerable']:.2f} | {r['context_tokens_top_k']} |")
    print("\nPer question (hit@{}):".format(k))
    print("| question | " + " | ".join(report["setups"]) + " |")
    print("|---|" + "---|" * len(report["setups"]))
    for i, case in enumerate(cases):
        print(f"| {case['id']} | " + " | ".join(f"{int(r['cases'][i][f'hit@{k}'])}" for r in report["setups"].values()) + " |")
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
