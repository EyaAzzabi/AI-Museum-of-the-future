"""Run the whole museum pipeline on the knowledge base and save the run.

    python run_exhibition.py                      # Tunisia, 2020-2026
    python run_exhibition.py --country ""         # no country filter (global corpus)
    python run_exhibition.py --no-review --no-fact-check
    python run_exhibition.py --from-run runs/<run_id>   # rerun only curator + fact-check

Every specialist searches the Supabase knowledge base with its own queries
(hybrid vector + keyword search), then the peer reviewer, the curator and the
fact-checker run. The full run (evidence, prompts, outputs, timings) is saved
to runs/<run_id>/run.json; score it with:

    python -m evaluation.evaluate_run --latest --judge
"""
from __future__ import annotations

import argparse
import logging

from dotenv import load_dotenv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--country", default="Tunisia", help='country the evidence must mention ("" for none)')
    parser.add_argument("--year-from", type=int, default=2020)
    parser.add_argument("--year-to", type=int, default=2026)
    parser.add_argument("--timeout", type=int, default=180, help="seconds for the specialists")
    parser.add_argument("--no-review", action="store_true")
    parser.add_argument("--no-fact-check", action="store_true")
    parser.add_argument("--rerank", action="store_true", help="LLM-rerank each agent's search (1 call per agent)")
    parser.add_argument("--from-run", help="reuse the specialists' insights and review of a saved run")
    args = parser.parse_args()
    load_dotenv()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    from agents.llm_config import build_llm_client, get_model
    from agents.pipeline import context_from_run, curate, run_pipeline
    from agents.run_log import RunRecorder, load_run
    from rag.vector_store.hybrid_retriever import SearchConfig, SearchFilters, build_hybrid_retriever

    llm = build_llm_client()
    filters = SearchFilters(country=args.country or None, year_from=args.year_from, year_to=args.year_to)
    retriever = build_hybrid_retriever(llm_client=llm, filters=filters,
                                       config=SearchConfig(rerank_agent_searches=args.rerank))
    recorder = RunRecorder(config={
        "model": get_model(), "country": filters.country, "years": [filters.year_from, filters.year_to],
        "review": not args.no_review, "fact_check": not args.no_fact_check, "timeout": args.timeout,
        "rerank": args.rerank,
    })

    if args.from_run:
        recorder.config["from_run"] = args.from_run
        source = load_run(args.from_run)
        # Keep the specialists' events so the new run can be evaluated on its own.
        for event in source["events"]:
            if event["kind"] in ("evidence", "insight", "abstain", "agent_error", "review"):
                recorder.events.append(event)
        try:
            result = curate(context_from_run(source), llm, recorder, fact_check=not args.no_fact_check)
        finally:
            recorder.save()
    else:
        result = run_pipeline([], llm, timeout_secs=args.timeout, retriever=retriever, recorder=recorder,
                              review=not args.no_review, fact_check=not args.no_fact_check)

    print(f"\n{result.exhibition_title}\n{result.concept}\n")
    for i, section in enumerate(result.sections, 1):
        print(f"{i}. {section.title}\n   {section.narrative}\n   artifacts: {', '.join(section.artifacts)}\n")
    if result.missing_perspectives:
        print("Missing perspectives:", ", ".join(result.missing_perspectives))
    if result.fact_check:
        ok = sum(1 for v in result.fact_check if v.get("supported"))
        print(f"Fact-check: {ok}/{len(result.fact_check)} sections fully supported")
    print(f"Run saved to {recorder.runs_dir / recorder.run_id / 'run.json'}")


if __name__ == "__main__":
    main()
