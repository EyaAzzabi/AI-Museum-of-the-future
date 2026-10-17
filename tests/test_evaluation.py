"""Evaluation metrics and the run scorer (offline)."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

from evaluation.evaluate_retrieval import load_cases
from evaluation.evaluate_run import FaithfulnessJudge, evaluate
from evaluation.metrics import matches_terms, retrieval_metrics, run_metrics
from rag.vector_store.retriever import RetrievalResult


def test_term_matching_is_whole_word_and_accent_insensitive():
    groups = [["tunisia", "tunisie"], ["election", "élection"]]
    assert matches_terms("Tunisie : une grave crise électorale après l'élection", groups)
    assert not matches_terms("Tunisian election", [["tunisia"]])   # whole word only
    assert not matches_terms("Tunisia economy", groups)            # every group must match


def test_retrieval_metrics():
    results = [
        RetrievalResult("a", "d1", "Population, total for Tunisia in 2021", {"category": "statistics"}),
        RetrievalResult("b", "d2", "Tunisia election crisis", {}),
        RetrievalResult("c", "d2", "Unrelated", {}),
    ]
    m = retrieval_metrics(results, [["tunisia"], ["election"]], k=3)
    assert m["precision"] == 1 / 3 and m["hit"] == 1.0 and m["rr"] == 0.5
    assert m["diversity"] == 2 / 3 and m["statistics_share"] == 1 / 3


def test_cases_file_is_valid():
    cases = load_cases()
    assert len(cases) >= 15
    assert all(c["query"] and c["relevant"] and all(c["relevant"]) for c in cases)
    assert len({c["id"] for c in cases}) == len(cases)


RUN = {
    "timings": {"total": 80.0},
    "events": [
        {"kind": "evidence", "agent": "historian", "own_search": 8},
        {"kind": "insight", "agent": "historian", "dropped_findings": 1,
         "insight": {"key_findings": ["A [c1].", "B [c1, c2]."], "evidence": {"c1": {"content": "text one"}, "c2": {"content": "two"}}}},
        {"kind": "abstain", "agent": "visual", "reason": "no finding cites the evidence"},
        {"kind": "agent_error", "agent": "sociologist", "error": "timeout"},
        {"kind": "llm_call", "agent": "historian", "cached": True},
        {"kind": "llm_call", "agent": "curator", "error": "429"},
        {"kind": "result", "exhibition": {
            "sections": [{}, {}, {}, {}],
            "review": {"agreements": [1], "tensions": [1, 2], "weak_findings": []},
            "fact_check": [{"supported": True}, {"supported": False, "unsupported_claims": ["x"]},
                           {"supported": True}, {"supported": None}],
        }},
    ],
}


def test_run_metrics():
    m = run_metrics(RUN)
    assert m["coverage"] == 0.2 and m["perspectives_present"] == ["historian"]
    assert m["abstained"] == ["visual"] and m["errors"] == ["sociologist"]
    assert m["findings"] == 2 and m["findings_dropped_uncited"] == 1
    assert m["avg_citations_per_finding"] == 1.0
    assert m["fact_check_supported"] == 2 / 3 and m["fact_check_unsupported_claims"] == 1
    assert (m["review_agreements"], m["review_tensions"]) == (1, 2)
    assert (m["llm_calls"], m["llm_calls_cached"], m["llm_errors"]) == (2, 1, 1)


def test_judge_scores_faithfulness():
    reply = {"verdicts": [{"finding": 0, "supported": True}, {"finding": 1, "supported": False, "reason": "c2 differs"}]}
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=lambda **_: SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(reply)))])
    )))
    judge = FaithfulnessJudge(client)
    with patch.object(judge, "_call_llm", wraps=judge._call_llm) as call:
        report = evaluate(RUN, judge)
    assert '"text one"' in call.call_args.args[1]   # the judge sees the cited evidence
    assert report["faithfulness"] == 0.5
    assert report["faithfulness_by_agent"]["historian"]["unsupported"][0]["reason"] == "c2 differs"
