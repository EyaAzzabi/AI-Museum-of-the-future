"""Start offline, inspect configuration, then run CultureArtAgent on real evidence."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from unittest.mock import Mock

from agents.culture_art import CultureArtAgent
from rag.vector_store.culture_reranker import CultureReranker, DEFAULT_CACHE_DIR
from agents.culture_scope import analysis_status, resolve_country

ROOT = Path(__file__).resolve().parent


def print_json(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def offline_demo():
    chunks = json.loads((ROOT / "examples/culture_art_fixture.json").read_text(encoding="utf-8"))
    agent = CultureArtAgent(None)
    agent._call_llm = Mock(return_value={
        "perspective": "Illustrative example: digital art and local identity.",
        "key_findings": ["Observation: an exhibition in Tunis explores local identity through digital artworks [demo-art-1]."],
        "selected_artifacts": ["demo-art-1", "invented-id"]})
    return {"mode": "offline_simulation", "notice": "Synthetic evidence and mocked LLM. No Supabase or real AI call.",
            "query": "digital art and local identity in Tunisia",
            "retrieved_evidence": chunks,
            "insight": asdict(agent.run(chunks, query="digital art and local identity in Tunisia"))}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--offline", action="store_true")
    modes.add_argument("--diagnose", action="store_true")
    modes.add_argument("--fixture", action="store_true", help="Real LLM on synthetic evidence, without Supabase")
    parser.add_argument("--no-rerank", action="store_true", help="Explicit V4 baseline; skip LLM evidence screening")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--country", help="Explicit country scope, e.g. Tunisia; single countries in the query are detected automatically")
    parser.add_argument("--category", help="Exact chunks.metadata.category, only after checking the corpus")
    args = parser.parse_args()
    if args.offline:
        print_json(offline_demo())
        return 0
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
        if args.diagnose:
            from rag.vector_store.culture_retrieval import build_supabase_client, diagnose_supabase
            print_json(diagnose_supabase(build_supabase_client()))
            return 0
        from agents.llm_config import build_llm_client
        retrieval_info = {}
        resolve_country(args.query or "", args.country)
        client = None
        if args.fixture:
            chunks = json.loads((ROOT / "examples/culture_art_fixture.json").read_text(encoding="utf-8"))
        else:
            if not args.query:
                parser.error("Provide a query or use --offline, --fixture or --diagnose.")
            from rag.vector_store.culture_retrieval import build_supabase_client, retrieve_culture
            chunks = retrieve_culture(args.query, build_supabase_client(), args.top_k, args.category,
                                      country=args.country, diagnostics=retrieval_info,
                                      reranker=None if args.no_rerank else CultureReranker(build_llm_client, cache_dir=DEFAULT_CACHE_DIR,
                                          progress=lambda message: print(message, file=sys.stderr, flush=True)))
        query = args.query or "digital art and local identity in Tunisia"
        if chunks:
            client = build_llm_client()
        result = CultureArtAgent(client).run(chunks, query=query, country=args.country)
        evidence = [asdict(c) if not isinstance(c, dict) else c for c in chunks]
        print_json({"mode": "real_llm_synthetic_evidence" if args.fixture else "live_supabase",
                    "query": query, "retrieved_evidence": evidence,
                    "retrieval": retrieval_info,
                    **analysis_status(result, chunks, query, args.country, retrieval_info),
                    "insight": asdict(result)})
        return 0
    except Exception as exc:
        # Known retrieval errors have safe text. Avoid printing arbitrary SDK exceptions.
        from rag.vector_store.culture_retrieval import CultureRetrievalError
        message = str(exc) if isinstance(exc, CultureRetrievalError) else (
            f"{type(exc).__name__}: check installed dependencies, .env and LLM provider access. Keys are not displayed.")
        print(message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
