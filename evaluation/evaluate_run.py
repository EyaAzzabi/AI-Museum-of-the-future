"""Score a saved exhibition run (runs/<run_id>/run.json).

    python -m evaluation.evaluate_run runs/20261014-101500-ab12cd          # metrics from the log
    python -m evaluation.evaluate_run runs/20261014-101500-ab12cd --judge  # + LLM faithfulness judge
    python -m evaluation.evaluate_run --latest --judge

Metrics: coverage (perspectives present), abstentions and errors, findings kept
vs. dropped for missing citations, review agreements/tensions, fact-check
support, LLM calls and timings. With --judge, an LLM checks every specialist
finding against the text of the chunks it cites (one call per specialist) and
reports the share of supported findings ("faithfulness").
Results are written next to the run as evaluation.json.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from agents.base_agent import BaseAgent, citations_in
from agents.run_log import DEFAULT_RUNS_DIR, load_run
from evaluation.metrics import SPECIALISTS, run_metrics

JUDGE_SYSTEM = (
    "You are a strict evaluator. For each finding you decide whether the evidence texts it cites "
    "support it: supported means the evidence states it or directly implies it. Return JSON only."
)
JUDGE_PROMPT = """Findings (JSON), each with the evidence texts it cites:
{chunks}

Return JSON only: {"verdicts": [{"finding": 0, "supported": true, "reason": "short reason"}]}"""


class FaithfulnessJudge(BaseAgent):
    name = "judge"

    def __init__(self, openai_client: Any):
        super().__init__(openai_client, prompt_path=Path("unused"))

    def _load_prompt_template(self) -> str:
        return JUDGE_PROMPT

    def judge(self, insight: dict) -> list[dict]:
        evidence = insight.get("evidence") or {}
        items = [
            {"finding": i, "text": f,
             "evidence": {cid: (evidence.get(cid) or {}).get("content", "")[:600] for cid in citations_in(f)}}
            for i, f in enumerate(insight.get("key_findings") or [])
        ]
        if not items:
            return []
        payload = self._call_llm(JUDGE_SYSTEM, self._render_prompt(json.dumps(items, ensure_ascii=False), "judge", ""))
        verdicts = {}
        for v in payload.get("verdicts") or []:
            try:
                index = int(v.get("finding"))
            except (TypeError, ValueError, AttributeError):
                continue
            if 0 <= index < len(items):
                verdicts[index] = {"finding": items[index]["text"], "supported": bool(v.get("supported")),
                                   "reason": str(v.get("reason") or "")}
        return [verdicts[i] for i in sorted(verdicts)]


def evaluate(run: dict, judge: FaithfulnessJudge | None = None) -> dict:
    report = run_metrics(run)
    if judge is not None:
        insights = {e["agent"]: e["insight"] for e in run.get("events", []) if e["kind"] == "insight"}
        per_agent = {}
        for agent in SPECIALISTS:
            if agent in insights:
                verdicts = judge.judge(insights[agent])
                per_agent[agent] = {
                    "supported": sum(v["supported"] for v in verdicts),
                    "judged": len(verdicts),
                    "unsupported": [v for v in verdicts if not v["supported"]],
                }
        judged = sum(a["judged"] for a in per_agent.values())
        report["faithfulness"] = (sum(a["supported"] for a in per_agent.values()) / judged) if judged else None
        report["faithfulness_by_agent"] = per_agent
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run", nargs="?", help="run folder or run.json")
    parser.add_argument("--latest", action="store_true", help="use the most recent run in runs/")
    parser.add_argument("--judge", action="store_true", help="LLM faithfulness judge (one call per specialist)")
    args = parser.parse_args()
    load_dotenv()

    if args.latest or not args.run:
        runs = sorted(p for p in DEFAULT_RUNS_DIR.glob("*/run.json"))
        if not runs:
            raise SystemExit("No saved runs in runs/. Run `python run_exhibition.py` first.")
        path = runs[-1].parent
    else:
        path = Path(args.run)
        path = path.parent if path.is_file() else path

    judge = None
    if args.judge:
        from agents.llm_config import build_llm_client

        judge = FaithfulnessJudge(build_llm_client())
    report = evaluate(load_run(path), judge)
    (path / "evaluation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nRun {path.name}")
    for key in ("coverage", "perspectives_missing", "abstained", "errors", "findings", "findings_dropped_uncited",
                "citation_survival", "avg_citations_per_finding", "own_search_results_per_agent", "sections",
                "review_agreements", "review_tensions", "review_weak_findings", "fact_check_supported",
                "fact_check_unsupported_claims", "faithfulness", "llm_calls", "llm_calls_cached", "llm_errors",
                "timings_s"):
        if key in report:
            value = report[key]
            print(f"  {key:32s} {round(value, 3) if isinstance(value, float) else value}")
    print(f"\nSaved to {path / 'evaluation.json'}")


if __name__ == "__main__":
    main()
