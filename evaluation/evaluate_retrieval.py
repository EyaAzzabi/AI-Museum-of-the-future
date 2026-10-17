"""Compare retrieval methods on evaluation/retrieval_cases.json.

    python -m evaluation.evaluate_retrieval            # vector vs hybrid (no LLM calls)
    python -m evaluation.evaluate_retrieval --rerank   # also hybrid + LLM rerank (1 call per case)
    python -m evaluation.evaluate_retrieval --k 8

Writes evaluation/results/retrieval_<date>.json and prints a Markdown table.
Needs SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY (and LLM_API_KEY for --rerank).
"""
from __future__ import annotations

import argparse
import json
import time
from dataclasses import replace
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from evaluation.metrics import average, retrieval_metrics

HERE = Path(__file__).resolve().parent


def load_cases(path: Path = HERE / "retrieval_cases.json") -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--rerank", action="store_true", help="add the hybrid + LLM rerank method")
    args = parser.parse_args()
    load_dotenv()

    from rag.vector_store.hybrid_retriever import SearchFilters, build_hybrid_retriever
    from rag.vector_store.retriever import Retriever

    llm = None
    if args.rerank:
        from agents.llm_config import build_llm_client

        llm = build_llm_client()
    hybrid = build_hybrid_retriever(llm_client=llm)
    vector = Retriever(hybrid.supabase_client, None, match_count=args.k, embed_client=hybrid.embed_client)
    # The evaluation measures ranking quality over the whole corpus: no year/country filter.
    unfiltered = replace(SearchFilters(), year_from=None, year_to=None)

    methods = {
        "vector": lambda c: vector.retrieve(c["query"]),
        "hybrid": lambda c: hybrid.search(c["query"], k=args.k, filters=unfiltered,
                                          keywords=c.get("keywords"), rerank=False),
    }
    if args.rerank:
        methods["hybrid+rerank"] = lambda c: hybrid.search(c["query"], k=args.k, filters=unfiltered,
                                                           keywords=c.get("keywords"), rerank=True)

    cases = load_cases()
    report: dict = {"k": args.k, "date": date.today().isoformat(), "methods": {}}
    for name, search in methods.items():
        rows, started = [], time.monotonic()
        for case in cases:
            results = search(case)
            row = {"id": case["id"], **retrieval_metrics(results, case["relevant"], args.k)}
            row["top"] = [r.content[:100] for r in results[: args.k]]
            rows.append(row)
        report["methods"][name] = {
            "mean": average([{k: v for k, v in r.items() if k not in {"id", "top"}} for r in rows]),
            "seconds_per_query": round((time.monotonic() - started) / len(cases), 2),
            "cases": rows,
        }

    out = HERE / "results" / f"retrieval_{report['date']}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nRetrieval quality on {len(cases)} cases, k={args.k}\n")
    print("| method | precision@k | hit@k | MRR | doc diversity | statistics share | s/query |")
    print("|---|---|---|---|---|---|---|")
    for name, data in report["methods"].items():
        m = data["mean"]
        print(f"| {name} | {m['precision']:.2f} | {m['hit']:.2f} | {m['rr']:.2f} | "
              f"{m['diversity']:.2f} | {m['statistics_share']:.2f} | {data['seconds_per_query']} |")
    print("\nPer case precision@k:")
    print("| case | " + " | ".join(report["methods"]) + " |")
    print("|---|" + "---|" * len(report["methods"]))
    for i, case in enumerate(cases):
        cells = " | ".join(f"{data['cases'][i]['precision']:.2f}" for data in report["methods"].values())
        print(f"| {case['id']} | {cells} |")
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
