"""Before/after comparison of the fact-checker, reviewer and curator prompts.

    python -m evaluation.compare_prompt_versions               # all three (8 LLM calls)
    python -m evaluation.compare_prompt_versions --only fact_checker

Inputs are fixed, so only the prompt changes between "before" and "after":
evaluation/prompt_iterations/live_run_2026-10-14.json holds the specialists'
insights, the v1 peer review and the curator v5 exhibition of a live run, and
prompt_iterations/prompts/ holds the previous prompt versions.

- fact-checker v1 vs v2 on the v5 exhibition, scored against the 10 annotated
  statements in prompt_iterations/annotations.json;
- reviewer v1 vs v2 on the insights: agreements backed by a chunk that two of
  the named agents cite, vs. agreements on a shared theme only;
- curator v5 vs v6 on the same insights and review, each exhibition then
  checked by fact-checker v2 (unsupported statements, sections supported).

Results go to prompt_iterations/results_<date>.json. Calls are spaced out
(--pause, default 65 s) for free-tier tokens-per-minute limits. Use the same
LLM_MODEL as the fixture (qwen/qwen3.8-27b) to reproduce the observed run.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from agents.base_agent import InsightObject, citations_in
from agents.curator import CuratorAgent, SectionObject
from agents.fact_checker import FactCheckAgent
from agents.reviewer import PeerReviewAgent
from agents.shared_context import SharedContext, compute_cross_references, evidence_of

HERE = Path(__file__).resolve().parent / "prompt_iterations"
OLD = HERE / "prompts"


class FactCheckV1(FactCheckAgent):
    """v1 as it ran: v1 prompt, evidence text only (no provenance)."""

    def check(self, sections, evidence):
        quoted = json.dumps([
            {"section": i, "title": s.title, "narrative": s.narrative,
             "cited_evidence": {cid: (evidence.get(cid) or {}).get("content", "")[:600]
                                for cid in dict.fromkeys(citations_in(s.narrative) + list(s.artifacts))}}
            for i, s in enumerate(sections)
        ], ensure_ascii=False)
        payload = self._call_llm(self.system_prompt, self._render_prompt(quoted, self.name, self.system_prompt))
        return self._validate(payload, sections)


def score_fact_check(verdicts: list[dict], annotations: list[dict]) -> dict:
    rows = []
    for a in annotations:
        claims = next((v["unsupported_claims"] for v in verdicts if v["section"] == a["section"]), [])
        flagged = any(m.lower() in c.lower() for c in claims for m in a["match"])
        rows.append({"id": a["id"], "should_flag": a["should_flag"], "flagged": flagged,
                     "correct": flagged == a["should_flag"]})
    return {
        "correct": sum(r["correct"] for r in rows),
        "of": len(rows),
        "missed_errors": [r["id"] for r in rows if r["should_flag"] and not r["flagged"]],
        "false_alarms": [r["id"] for r in rows if not r["should_flag"] and r["flagged"]],
        "total_flags": sum(len(v["unsupported_claims"]) for v in verdicts),
        "rows": rows,
    }


def score_review(review: dict, insights: dict[str, InsightObject]) -> dict:
    shared, theme_only = [], []
    for agreement in review.get("agreements", []):
        citing = [sum(a in insights[agent].selected_artifacts for agent in agreement["agents"])
                  for a in agreement.get("artifacts", [])]
        (shared if any(c >= 2 for c in citing) else theme_only).append(agreement["point"])
    return {"agreements_shared_evidence": shared, "agreements_theme_only": theme_only,
            "tensions": len(review.get("tensions", [])), "weak_findings": len(review.get("weak_findings", []))}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", choices=["fact_checker", "reviewer", "curator"])
    parser.add_argument("--pause", type=float, default=65.0, help="seconds between LLM calls")
    args = parser.parse_args()
    load_dotenv()
    from agents.llm_config import build_llm_client, get_model

    llm = build_llm_client()
    fixture = json.loads((HERE / "live_run_2026-10-14.json").read_text(encoding="utf-8"))
    annotations = json.loads((HERE / "annotations.json").read_text(encoding="utf-8"))["statements"]
    insights = {n: InsightObject(**{k: d[k] for k in ("agent", "perspective", "key_findings", "selected_artifacts")},
                                 evidence=d["evidence"]) for n, d in fixture["insights"].items()}
    evidence = evidence_of(insights)
    v5_sections = [SectionObject(**s) for s in fixture["exhibition_v5"]["sections"]]
    out = HERE / f"results_{date.today().isoformat()}.json"
    # Parts run separately (--only) accumulate in the same file; each part is saved as soon as it ends.
    report: dict = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    report.update({"date": date.today().isoformat(), "fixture_model": fixture["model"]})
    calls = 0

    def save(part: str, data: dict) -> None:
        report[part] = {"model": get_model(), **data}
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    def pause():
        nonlocal calls
        if calls:
            time.sleep(args.pause)
        calls += 1

    if args.only in (None, "fact_checker"):
        old = FactCheckV1(llm, prompt_path=OLD / "fact_checker_v1.md")
        new = FactCheckAgent(llm)
        pause(); before = old.check(v5_sections, evidence)
        pause(); after = new.check(v5_sections, evidence)
        save("fact_checker", {
            "observed_v1_in_live_run": score_fact_check(fixture["fact_check_v1_observed"], annotations),
            "v1": score_fact_check(before, annotations), "v2": score_fact_check(after, annotations),
            "v1_verdicts": before, "v2_verdicts": after,
        })

    if args.only in (None, "reviewer"):
        pause(); before = PeerReviewAgent(llm, prompt_path=OLD / "reviewer_v1.md").review(insights)
        pause(); after = PeerReviewAgent(llm).review(insights)
        save("reviewer", {
            "observed_v1_in_live_run": score_review(fixture["review_v1"], insights),
            "v1": score_review(before, insights), "v2": score_review(after, insights),
            "v1_review": before, "v2_review": after,
        })

    if args.only in (None, "curator"):
        context = SharedContext(insights=insights, cross_references=compute_cross_references(insights),
                                review=fixture["review_v1"])
        checker = FactCheckAgent(llm)
        results = {}
        for label, path in (("v5", OLD / "curator_v5.md"), ("v6", None)):
            try:
                pause(); exhibition = (CuratorAgent(llm, prompt_path=path) if path else CuratorAgent(llm)).run(context)
                pause(); verdicts = checker.check(exhibition.sections, evidence)
            except ValueError as exc:  # e.g. a free-tier token limit: record it, keep the other version
                results[label] = {"error": str(exc)[:300]}
                save("curator", results)
                continue
            results[label] = {
                "sections": len(exhibition.sections),
                "sections_supported": sum(1 for v in verdicts if v["supported"]),
                "unsupported_statements": sum(len(v["unsupported_claims"]) for v in verdicts),
                "exhibition": {"title": exhibition.exhibition_title,
                               "sections": [{"title": s.title, "narrative": s.narrative} for s in exhibition.sections]},
                "verdicts": verdicts,
            }
            save("curator", results)

    for key in ("fact_checker", "reviewer"):
        if key in report:
            print(key, {k: {kk: vv for kk, vv in v.items() if kk != "rows"} for k, v in report[key].items()
                        if k.startswith(("v1", "v2", "observed")) and not k.endswith(("verdicts", "review"))})
    if "curator" in report:
        print("curator", {k: {kk: v.get(kk) for kk in ("sections", "sections_supported", "unsupported_statements", "error")}
                          for k, v in report["curator"].items() if isinstance(v, dict) and k != "model"})
    print(f"Saved to {out}")


if __name__ == "__main__":
    main()
