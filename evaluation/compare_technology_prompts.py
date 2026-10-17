"""Before/after comparison of the Technology prompt (Tasnim): an archived version vs the current one.

    python -m evaluation.compare_technology_prompts --rag --runs 3        # v4 vs current, Supabase evidence
    python -m evaluation.compare_technology_prompts --before v2 --runs 3  # v2 vs current, live-run evidence

Fixed input, so only the prompt changes: by default every chunk cited by the five
specialists in the live run of 2026-10-14 (the evidence the demo uses); with --rag,
the agent's own Supabase search, run once and given to both versions. The agent code
is the same for both versions (typed evidence lines, figure and citation guardrails);
v2 simply has no {coverage} placeholder.

Scored per version:
  findings_returned / findings_kept       before / after the code guardrails
  dropped_by_figure_guardrail             findings with a figure not in their sources
  domains_cited                           technology domains of the cited chunks
  overstatement_markers                   findings containing a marker of an observed failure
                                          (OVERSTATEMENT below; a proxy, read the findings)
  unlabelled_readings                     fact sentences ending with ", indicating / reflecting /
                                          showing / highlighting ..." (v3 failure)
  unmeasured_outcomes                     returned interpretations stating an outcome no source
                                          measures (UNMEASURED_OUTCOME; v4 failure)
  over_budget                             findings beyond the 5 the prompt allows
  perspective_markers                     OVERSTATEMENT markers in the perspective
  interpretation_labelled                 findings starting with "Interpretation:"

Writes evaluation/prompt_iterations/technology_results_<date-time>_<before>_vs_<current>[_rag].json
(one file per run, never overwritten). findings_kept includes the code finding budget (5 max);
over_budget measures the model before it.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent / "prompt_iterations"
ARCHIVED = {v: HERE / "prompts" / f"technology_{v}.md" for v in ("v2", "v3", "v4")}
CURRENT = "v5"

# Words that appeared in the observed failures (v2 and v3 live runs) and that no cited source contains.
OVERSTATEMENT = {
    "possibility read as fact (source: 'can')": r"\ballowed\b|\benabled\b",
    "one expert read as several": r"\bexperts\b",
    "one item read as a trend": r"\bdiscourse\b|\bextended to\b|\bwidespread\b|\bglobal trend\b",
    "term added (source: 'vaccine')": r"\bmrna\b",
    "term added (source: 'renewable energy')": r"\bsolar and wind\b|\bwind and solar\b",
    "guessed name (source: ليجوريا, Liguria)": r"\b(?!liguria\b)l[eiy][gj]\w*ria\b",
    "title read as an event (v3, v4)": r"\baccess to social media (?:was|were|is) (?:being )?(?:responsibly )?regulated"
                                       r"|\bregulators (?:announced|introduced|promoted)\b",
}
# Outcomes no source of the Supabase evidence measures, stated by v4 interpretations.
UNMEASURED_OUTCOME = re.compile(
    r"\b(mortality|saving lives|saved lives|lower(?:ed)? (?:electricity )?(?:costs|prices)|employment|emissions"
    r"|transformed (?:public health|daily life)|directly altered|tangible improvements)\b", re.IGNORECASE)
UNLABELLED_READING = re.compile(r",\s*(indicating|reflecting|showing|highlighting|signall?ing|suggesting)\b", re.IGNORECASE)
MAX_FINDINGS = 5   # TechnologyAgent.max_findings; over_budget measures the model, before the code limit


def score(insight, raw: dict, recorder, by_id: dict) -> dict:
    from agents.technology_tools import DOMAIN_LABELS, classify_domain

    markers = {label: [f for f in insight.key_findings if re.search(rx, f, re.IGNORECASE)]
               for label, rx in OVERSTATEMENT.items()}
    facts = [f for f in insight.key_findings if not f.startswith("Interpretation:")]
    guardrails = recorder.events_of("guardrail")
    figure_drops = [e for e in guardrails if e.get("rule") != "finding_budget"]
    budget = [e for e in guardrails if e.get("rule") == "finding_budget"]
    return {
        "findings_returned": len(raw.get("key_findings") or []),
        "findings_kept": len(insight.key_findings),
        "dropped_by_figure_guardrail": len(figure_drops),
        "dropped_by_budget": [f for e in budget for f in e["dropped"]],
        "domains_cited": sorted({DOMAIN_LABELS[classify_domain(by_id[c])] for c in insight.selected_artifacts}),
        "overstatement_markers": sum(len(v) for v in markers.values()),
        "overstatement_detail": {k: v for k, v in markers.items() if v},
        "unlabelled_readings": sum(bool(UNLABELLED_READING.search(f)) for f in facts),
        "unmeasured_outcomes": [f for f in raw.get("key_findings") or []
                                if isinstance(f, str) and f.startswith("Interpretation:") and UNMEASURED_OUTCOME.search(f)],
        "over_budget": max(0, len(raw.get("key_findings") or []) - MAX_FINDINGS),
        "perspective_markers": [label for label, rx in OVERSTATEMENT.items()
                                if re.search(rx, insight.perspective or "", re.IGNORECASE)],
        "interpretation_labelled": sum(f.startswith("Interpretation:") for f in insight.key_findings),
        "perspective": insight.perspective,
        "findings": insight.key_findings,
        "returned_findings": raw.get("key_findings") or [],
        "dropped_findings": [e["finding"] for e in figure_drops],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--before", choices=sorted(ARCHIVED), default="v4", help="archived version to compare")
    parser.add_argument("--runs", type=int, default=1, help="runs per version")
    parser.add_argument("--only", choices=("before", "current"), help="run one version (e.g. rerun failed calls)")
    parser.add_argument("--pause", type=float, default=30.0, help="seconds between LLM calls (free tier)")
    parser.add_argument("--rag", action="store_true", help="evidence from the agent's own Supabase search (once)")
    parser.add_argument("--country", default="Tunisia", help='with --rag: country filter ("" for none)')
    args = parser.parse_args()
    load_dotenv()

    from agents.llm_config import build_llm_client, get_model
    from agents.run_log import RunRecorder
    from agents.technology import TechnologyAgent
    from demo_technology import load_live_run_evidence

    llm = build_llm_client()
    if args.rag:
        from rag.vector_store.hybrid_retriever import SearchFilters, build_hybrid_retriever
        searcher = TechnologyAgent(llm)
        searcher.retriever = build_hybrid_retriever(filters=SearchFilters(country=args.country or None))
        chunks = searcher.gather_evidence([])
    else:
        chunks = load_live_run_evidence()
    by_id = {c.chunk_id: c for c in chunks}
    suffix = "_rag" if args.rag else ""
    out = HERE / f"technology_results_{datetime.now():%Y-%m-%d-%H%M}_{args.before}_vs_{CURRENT}{suffix}.json"
    report = {"date": date.today().isoformat(), "model": get_model(), "evidence_items": len(chunks),
              "evidence": "supabase" if args.rag else "live_run_2026-10-14",
              "evidence_ids": list(by_id), "runs": {}}
    calls = 0
    versions = {"before": (args.before, ARCHIVED[args.before]), "current": (CURRENT, None)}
    for key, (label, path) in versions.items():
        if args.only and key != args.only:
            continue
        report["runs"][label] = []
        for _ in range(args.runs):
            if calls:
                time.sleep(args.pause)
            calls += 1
            agent = TechnologyAgent(llm, prompt_path=path) if path else TechnologyAgent(llm)
            agent.prompt_evidence = len(chunks)   # same evidence for both versions, nothing cut
            agent.recorder = RunRecorder()
            try:
                insight = agent.run(chunks)
            except ValueError as exc:   # e.g. a free-tier token limit: keep the other runs
                report["runs"][label].append({"error": str(exc)[:300]})
                continue
            raw = (agent.recorder.events_of("llm_call") or [{}])[-1].get("response") or {}
            report["runs"][label].append(score(insight, raw, agent.recorder, by_id))
            out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("| version | run | returned | kept | over budget | figure drops | markers | unlabelled readings "
          "| unmeasured outcomes | perspective markers | domains cited |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for label, runs in report["runs"].items():
        for i, r in enumerate(runs, 1):
            if "error" in r:
                print(f"| {label} | {i} | error: {r['error'][:60]} | | | | | | | | |")
            else:
                print(f"| {label} | {i} | {r['findings_returned']} | {r['findings_kept']} | {r['over_budget']} | "
                      f"{r['dropped_by_figure_guardrail']} | {r['overstatement_markers']} | {r['unlabelled_readings']} | "
                      f"{len(r['unmeasured_outcomes'])} | {len(r['perspective_markers'])} | {', '.join(r['domains_cited'])} |")
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
