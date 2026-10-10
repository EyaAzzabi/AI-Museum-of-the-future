"""Live retrieval demo — run real queries against the live Supabase vector store.

Usage: python demo_retrieval.py
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()

import os
from agents.llm_config import build_llm_client
from rag.vector_store.local_embeddings import build_embedding_client
from supabase import create_client

from rag.vector_store.retriever import Retriever

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
if not all([SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY]):
    print("[ERROR] Missing SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY in .env")
    raise SystemExit(1)

QUERIES = [
    "key AI breakthroughs in 2026",
    "Tunisia economy and unemployment",
    "climate change protests and activism",
    "contemporary art in North Africa",
    "space exploration milestones",
]


def main():
    sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    # Embeddings are local; the chat client is only used when reranking.
    retriever = Retriever(sb, build_llm_client(), match_count=3, embed_client=build_embedding_client())

    total = sb.table("documents").select("id", count="exact").limit(1).execute().count
    print("=" * 65)
    print("  AI Museum of the Future — Live Retrieval Test")
    print(f"  Corpus size: {total} documents")
    print("=" * 65)

    for query in QUERIES:
        print(f"\nQUERY: {query!r}")
        print("-" * 65)
        results = retriever.retrieve(query)
        if not results:
            print("  (no results)")
            continue
        for r in results:
            preview = r.content[:100].replace("\n", " ")
            print(f"  similarity={r.similarity:.3f}  [{r.metadata.get('source', '?')}]")
            print(f"    {preview}...")

    print("\n" + "=" * 65)
    print("  Done.")
    print("=" * 65)


if __name__ == "__main__":
    main()
