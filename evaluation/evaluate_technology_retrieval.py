"""Retrieval evaluation of the Technology agent (Tasnim).

    python -m evaluation.evaluate_technology_retrieval                    # Tunisia + global, k=5
    python -m evaluation.evaluate_technology_retrieval --country "" --k 8

Two measurements, no LLM call (needs SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY):

1. Per domain query: each search query of agents/technology.py is run alone
   through the hybrid retriever with the agent's filters, and scored with the
   term rules of technology_retrieval_cases.json (precision@k, hit@k, MRR,
   document diversity; metrics from evaluation/metrics.py).
2. Evidence balance: the agent's full own search (all queries fused) gives the
   candidate pool; we compare the first 14 items of the pool ("before", what
   BaseAgent alone would send) with diversify() ("after"): technology domains
   covered (of 6), share of the largest domain, share of research papers, share
   of evidence inside the requested country. Domains are those of
   agents.technology_tools.classify_domain, so this measures the balance by the
   agent's own taxonomy, not relevance.

Writes evaluation/results/technology_retrieval_<date>.json.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import replace
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from agents.technology_tools import OTHER, TECH_DOMAINS, classify_domain, diversify, evidence_kind
from evaluation.metrics import average, retrieval_metrics

HERE = Path(__file__).resolve().parent


def load_cases(path: Path = HERE / "technology_retrieval_cases.json") -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def selection_stats(evidence: list) -> dict:
    """Balance of a set of evidence items, by technology domain and source kind."""
    if not evidence:
        return {"items": 0, "domains_covered": 0, "largest_domain_share": 0.0,
                "research_share": 0.0, "not_technology_share": 0.0, "in_scope_share": 0.0}
    domains = Counter(classify_domain(e) for e in evidence)
    tech = {d: n for d, n in domains.items() if d != OTHER}
    n = len(evidence)
    return {
        "items": n,
        "domains_covered": len(tech),
        "largest_domain_share": round(max(tech.values()) / n, 3) if tech else 0.0,
        "research_share": round(sum(evidence_kind(e) == "research paper" for e in evidence) / n, 3),
        "not_technology_share": round(domains.get(OTHER, 0) / n, 3),
        "in_scope_share": round(sum((e.metadata or {}).get("in_scope") is not False for e in evidence) / n, 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--country", default=None,
                        help='one country filter ("" for none); default: both "Tunisia" and none')
    args = parser.parse_args()
    load_dotenv()

    from agents.technology import TechnologyAgent
    from rag.vector_store.hybrid_retriever import SearchFilters, build_hybrid_retriever

    cases = load_cases()
    queries = TechnologyAgent.search_queries
    assert len(cases) == len(queries), "one case per search query of TechnologyAgent"
    countries = [args.country or None] if args.country is not None else ["Tunisia", None]
    retriever = build_hybrid_retriever()
    report: dict = {"date": date.today().isoformat(), "k": args.k, "by_country": {}}

    for country in countries:
        filters = replace(SearchFilters(country=country),
                          exclude_categories=TechnologyAgent.search_exclude_categories)
        retriever.default_filters = filters
        rows = []
        for case, query in zip(cases, queries):
            results = retriever.search(query, k=args.k, filters=filters, rerank=False)
            rows.append({"id": case["id"], "query": query,
                         **retrieval_metrics(results, case["relevant"], args.k),
                         "top": [(r.metadata.get("title") or r.content)[:90] for r in results[: args.k]]})

        agent = TechnologyAgent(openai_client=None)
        agent.retriever = retriever
        pool = agent.search_own_evidence()[: agent.max_evidence]
        before, after = pool[: agent.prompt_evidence], diversify(pool, agent.prompt_evidence)
        report["by_country"][country or "none"] = {
            "per_query": {"mean": average([{k: v for k, v in r.items() if k not in {"id", "query", "top"}}
                                           for r in rows]), "cases": rows},
            "balance": {"pool": len(pool), "before": selection_stats(before), "after": selection_stats(after),
                        "after_domains": dict(Counter(classify_domain(e) for e in after))},
        }

    out = HERE / "results" / f"technology_retrieval_{report['date']}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    for country, data in report["by_country"].items():
        print(f"\n## country filter: {country}  (k={args.k})\n")
        print("| query | precision@k | hit@k | MRR | doc diversity |\n|---|---|---|---|---|")
        for row in data["per_query"]["cases"]:
            print(f"| {row['id']} | {row['precision']:.2f} | {row['hit']:.2f} | {row['rr']:.2f} | {row['diversity']:.2f} |")
        m = data["per_query"]["mean"]
        print(f"| **mean** | {m['precision']:.2f} | {m['hit']:.2f} | {m['rr']:.2f} | {m['diversity']:.2f} |")
        b = data["balance"]
        print(f"\nEvidence sent to the model (pool of {b['pool']}), before vs after diversify():\n")
        print("| | domains (of %d) | largest domain | research papers | not technology | in country |" % len(TECH_DOMAINS))
        print("|---|---|---|---|---|---|")
        for label in ("before", "after"):
            s = b[label]
            print(f"| {label} | {s['domains_covered']} | {s['largest_domain_share']:.2f} | {s['research_share']:.2f} | "
                  f"{s['not_technology_share']:.2f} | {s['in_scope_share']:.2f} |")
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
