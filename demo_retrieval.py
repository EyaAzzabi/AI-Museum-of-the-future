"""Live retrieval demo — run real queries against the live Supabase vector store.

Usage: python demo_retrieval.py
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()

import os
from openai import OpenAI
from supabase import create_client

from rag.vector_store.retriever import Retriever

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not all([SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, OPENAI_API_KEY]):
    print("[ERROR] Missing SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY / OPENAI_API_KEY in .env")
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
    oai = OpenAI(api_key=OPENAI_API_KEY)
    retriever = Retriever(sb, oai, match_count=3)

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
