"""Standalone demo of the Technology agent (Tasnim).

    python demo_technology.py --dry-run     # no key: evidence selection, coverage and the prompt
    python demo_technology.py               # LLM_API_KEY: run the agent on the live-run evidence
    python demo_technology.py --rag         # + Supabase keys: the agent searches the knowledge base
    python demo_technology.py --rag --country "" --save

Default evidence: every chunk cited by the five specialists in the live run of
2026-10-14 (evaluation/prompt_iterations/live_run_2026-10-14.json), a real mix of
technology and non-technology sources. --save writes the run to runs/<run_id>/.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
LIVE_RUN = ROOT / "evaluation" / "prompt_iterations" / "live_run_2026-10-14.json"


def load_live_run_evidence(path: Path = LIVE_RUN) -> list:
    """Every chunk cited in the saved live run, once, as RetrievalResult."""
    from rag.vector_store.retriever import RetrievalResult

    insights = json.loads(path.read_text(encoding="utf-8"))["insights"]
    chunks: dict[str, RetrievalResult] = {}
    for insight in insights.values():
        for cid, item in (insight.get("evidence") or {}).items():
            chunks.setdefault(cid, RetrievalResult(
                chunk_id=cid, document_id=cid, content=item.get("content") or "",
                metadata={k: item.get(k) for k in ("title", "source", "category", "year", "url")},
            ))
    return list(chunks.values())


def _rule(title: str) -> None:
    print("\n" + "=" * 78 + f"\n  {title}\n" + "=" * 78)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="no LLM call: show the evidence and the prompt")
    parser.add_argument("--rag", action="store_true", help="let the agent search the Supabase knowledge base")
    parser.add_argument("--country", default="Tunisia", help='with --rag: country filter ("" for none)')
    parser.add_argument("--save", action="store_true", help="save the run to runs/<run_id>/run.json")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    logging.basicConfig(level=logging.INFO, format="  [log] %(message)s")

    from agents.run_log import RunRecorder
    from agents.technology import TechnologyAgent

    _rule("AI MUSEUM OF THE FUTURE - SCIENCE & TECHNOLOGY AGENT (Tasnim)")
    print("  agents/technology.py · agents/technology_tools.py · prompts/technology.md (v3)")

    has_key = bool(os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY"))
    if not args.dry_run and not has_key:
        print("\n  No LLM_API_KEY in .env: running --dry-run instead (add LLM_API_KEY=gsk_... for a live run).")
        args.dry_run = True

    client = None
    if not args.dry_run:
        from agents.llm_config import build_llm_client, get_model
        client = build_llm_client()
        print(f"  model: {get_model()}")

    agent = TechnologyAgent(client)
    agent.recorder = RunRecorder(config={"demo": "technology", "rag": args.rag, "country": args.country})
    chunks = []
    if args.rag:
        from rag.vector_store.hybrid_retriever import SearchFilters, build_hybrid_retriever
        agent.retriever = build_hybrid_retriever(filters=SearchFilters(country=args.country or None))
        print(f"  evidence: own hybrid search on Supabase (country={args.country or 'none'})")
    else:
        chunks = load_live_run_evidence()
        print(f"  evidence: {len(chunks)} chunks cited in the live run of 2026-10-14")

    evidence = agent.gather_evidence(chunks)
    selection = agent.recorder.events_of("evidence_selection")[-1]
    _rule(f"1. EVIDENCE SENT TO THE MODEL ({len(evidence)} of a pool of {selection['pool']})")
    for chunk in evidence:
        print("  " + agent.format_evidence(chunk)[:160])
    _rule("2. COVERAGE BY DOMAIN (injected into the prompt)")
    print(selection["coverage"])

    if args.dry_run:
        _rule("3. PROMPT (first 2,500 characters)")
        print(agent._render_prompt(evidence, agent.name, agent.system_prompt)[:2500])
        return

    _rule("3. LLM ANALYSIS")
    payload = agent._call_llm(agent.system_prompt, agent._render_prompt(evidence, agent.name, agent.system_prompt))
    insight = agent.finalize(payload, evidence)
    print(f"\n  Perspective: {insight.perspective or '(abstained)'}")
    print(f"\n  Findings kept ({len(insight.key_findings)} of {len(payload.get('key_findings') or [])} returned):")
    for i, finding in enumerate(insight.key_findings, 1):
        print(f"    {i}. {finding}")
    for event in agent.recorder.events_of("guardrail"):
        if event.get("rule") == "finding_budget":
            for finding in event["dropped"]:
                print(f"\n  Dropped by the finding budget ({agent.max_findings} max, "
                      f"{agent.max_interpretations} interpretations): {finding}")
        else:
            print(f"\n  Dropped by the figure guardrail ({', '.join(event['figures'])}): {event['finding']}")
    print(f"\n  Domains covered (model): {payload.get('domains_covered')}")
    print(f"  Evidence gaps (model):   {payload.get('evidence_gaps')}")
    print(f"  Selected artifacts:      {insight.selected_artifacts}")
    if args.save:
        print(f"\n  Run saved to {agent.recorder.save()}")


if __name__ == "__main__":
    main()
