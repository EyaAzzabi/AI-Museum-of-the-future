"""
Master fetch script — runs all data source fetches then normalizes the output.

Usage:
    python data/fetch_all.py                  # all sources
    python data/fetch_all.py --sources gdelt  # specific source(s)
    python data/fetch_all.py --skip-process   # fetch only, skip normalization
    python data/fetch_all.py --skip-ingest    # fetch + normalize, skip ingestion

Sources available: gdelt, wikimedia, arxiv, wikipedia, worldbank
"""

import argparse
import importlib
import sys
import traceback
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))


SOURCES = {
    "gdelt": "data.fetch_gdelt",
    "wikimedia": "data.fetch_wikimedia",
    "arxiv": "data.fetch_arxiv",
    "wikipedia": "data.fetch_wikipedia",
    "worldbank": "data.fetch_worldbank",
}

PROCESSED_DIR = Path(__file__).parent / "processed"


def _run_ingestion() -> None:
    """
    Attempt to create a Chunker and Supabase client, then call ingest_processed.

    Guards against missing dependencies so the script degrades gracefully
    when Task 3 (chunker) or Task 4.2 (Supabase store) are not yet complete.
    """
    from data.ingest import ingest_processed  # always available after Task 2.1

    # ── Chunker guard ─────────────────────────────────────────────────────────
    try:
        from rag.chunking.chunker import ChunkConfig, Chunker  # type: ignore[import]
        chunker = Chunker(ChunkConfig())
    except ImportError:
        print(
            "  [ingest] Chunker not yet implemented — skipping ingestion."
            " Run again after Task 3."
        )
        return

    # ── Supabase client guard ─────────────────────────────────────────────────
    # Service-role key, not anon — this writes server-side and should bypass RLS.
    try:
        from scripts.config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY  # type: ignore[import]
        if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
            print("  [ingest] SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY not configured — skipping ingestion.")
            return
        from supabase import create_client  # type: ignore[import]
        supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    except ImportError:
        print("  [ingest] supabase library not available — skipping ingestion.")
        return
    except Exception as exc:  # noqa: BLE001
        print(f"  [ingest] Could not create Supabase client: {exc} — skipping ingestion.")
        return

    # ── Embedding client ──────────────────────────────────────────────────────
    # Local fastembed model: free, no API key. Chunks need real vectors for retrieval.
    try:
        from rag.vector_store.local_embeddings import build_embedding_client  # type: ignore[import]
        embed_client = build_embedding_client()
    except Exception as exc:  # noqa: BLE001
        print(f"  [ingest] Could not create embedding client: {exc} — skipping ingestion.")
        return

    ingest_processed(PROCESSED_DIR, chunker, supabase_client, embed_client)


def run_module(module_path: str) -> bool:
    """Import and run a fetch module's __main__ block via its main logic."""
    try:
        # Each fetch module is self-contained; we import and run its top-level
        # code by running it as __main__ via runpy.
        import runpy
        runpy.run_module(module_path, run_name="__main__", alter_sys=False)
        return True
    except SystemExit:
        return True   # clean exit from the module
    except Exception as exc:
        print(f"\n[ERROR] {module_path} failed: {exc}")
        traceback.print_exc()
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch all AI Museum data sources")
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=list(SOURCES.keys()),
        default=list(SOURCES.keys()),
        help="Which sources to fetch (default: all)",
    )
    parser.add_argument(
        "--skip-process",
        action="store_true",
        help="Skip the normalization step after fetching",
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Skip the RAG ingestion step after normalization",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  AI Museum of the Future — Data Fetch Pipeline")
    print("=" * 60)

    results: dict[str, bool] = {}
    for name in args.sources:
        print(f"\n{'─'*60}")
        print(f"  Source: {name.upper()}")
        print(f"{'─'*60}")
        ok = run_module(SOURCES[name])
        results[name] = ok

    if not args.skip_process:
        print(f"\n{'─'*60}")
        print("  Processing & normalizing raw data …")
        print(f"{'─'*60}")
        run_module("data.process_raw")

        # ── Ingestion step ────────────────────────────────────────────────────
        if args.skip_ingest:
            print("\nSkipping ingestion (--skip-ingest passed)")
        else:
            print(f"\n{'─'*60}")
            print("  Ingesting processed data into vector store …")
            print(f"{'─'*60}")
            _run_ingestion()

    # Summary
    print(f"\n{'='*60}")
    print("  Fetch summary")
    print(f"{'='*60}")
    for name, ok in results.items():
        status = "✓" if ok else "✗ FAILED"
        print(f"  {name:<15} {status}")
    print()

    if not all(results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
