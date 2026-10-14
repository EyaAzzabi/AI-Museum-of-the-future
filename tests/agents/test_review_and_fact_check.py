"""Peer review, fact-check and the pipeline flow around them (offline)."""
from __future__ import annotations

import json
import re
from types import SimpleNamespace
from unittest.mock import patch

from agents.base_agent import InsightObject
from agents.curator import SectionObject
from agents.fact_checker import FactCheckAgent, feedback_for
from agents.pipeline import run_pipeline
from agents.reviewer import PeerReviewAgent
from agents.run_log import RunRecorder, load_run
from rag.vector_store.retriever import RetrievalResult


def _insight(name, findings, ids):
    return InsightObject(name, f"{name} view", findings, ids, {i: {"content": f"text of {i}"} for i in ids})


INSIGHTS = {
    "historian": _insight("historian", ["Parliament suspended [c1]."], ["c1"]),
    "sociologist": _insight("sociologist", ["Youth left [c2].", "Unrest grew [c1]."], ["c1", "c2"]),
    "visual": InsightObject("visual", "", [], []),
}


def test_review_keeps_only_real_agents_findings_and_ids():
    payload = {
        "agreements": [{"agents": ["historian", "sociologist"], "point": "2021 rupture", "artifacts": ["c1", "ghost"]}],
        "tensions": [
            {"agents": ["historian", "visual"], "issue": "visual abstained"},     # visual has no findings
            {"agents": ["sociologist", "historian"], "issue": "cause vs. effect", "artifacts": ["c2"]},
        ],
        "weak_findings": [{"agent": "sociologist", "finding": 1, "reason": "c1 says nothing about unrest"},
                          {"agent": "sociologist", "finding": 9, "reason": "no such finding"}],
    }
    reviewer = PeerReviewAgent(None)
    with patch.object(reviewer, "_call_llm", return_value=payload) as llm:
        review = reviewer.review(INSIGHTS)
    assert "text of c2" in llm.call_args.args[1]
    assert review["agreements"] == [{"agents": ["historian", "sociologist"], "point": "2021 rupture", "artifacts": ["c1"]}]
    assert [t["issue"] for t in review["tensions"]] == ["cause vs. effect"]
    assert review["weak_findings"] == [{"agent": "sociologist", "finding": 1, "text": "Unrest grew [c1].",
                                        "reason": "c1 says nothing about unrest"}]


def test_review_needs_two_perspectives():
    reviewer = PeerReviewAgent(None)
    with patch.object(reviewer, "_call_llm") as llm:
        assert reviewer.review({"historian": INSIGHTS["historian"]})["agreements"] == []
    llm.assert_not_called()


def test_fact_check_validates_verdicts_and_builds_feedback():
    sections = [SectionObject("A", "Fact [c1].", ["c1"]), SectionObject("B", "Claim [c2].", ["c2"]),
                SectionObject("C", "Other [c1].", ["c1"])]
    payload = {"sections": [
        {"section": 0, "supported": True, "unsupported_claims": []},
        {"section": 1, "supported": True, "unsupported_claims": ["Claim"]},   # claims override "supported"
        {"section": 7, "supported": True},
    ]}
    checker = FactCheckAgent(None)
    with patch.object(checker, "_call_llm", return_value=payload) as llm:
        verdicts = checker.check(sections, {"c1": {"content": "text one"}, "c2": {"content": "text two"}})
    assert "text two" in llm.call_args.args[1]
    assert [v["supported"] for v in verdicts] == [True, False, None]   # section C unchecked
    feedback = feedback_for(verdicts)
    assert 'Section 2 "B": Claim' in feedback and "Section 1" not in feedback
    assert feedback_for(verdicts[:1]) == ""


class ScriptedLLM:
    """Answers each agent by its system prompt; records the order of calls."""

    def __init__(self):
        self.calls = []
        self.curator_calls = 0
        self.checks = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, model, messages, **_):
        system, user = messages[0]["content"], messages[1]["content"]
        ids = sorted(set(re.findall(r"\[(c\d)\]", user))) or ["c1"]
        if "peer reviewer" in system:
            kind, body = "review", {"agreements": [], "tensions": [], "weak_findings": []}
        elif "fact-checker" in system:
            self.checks += 1
            bad = ["The festival drew a million visitors"] if self.checks == 1 else []
            kind, body = "fact_check", {"sections": [{"section": i, "supported": not (bad and i == 0),
                                                      "unsupported_claims": bad if i == 0 else []} for i in range(4)]}
        elif "chief curator" in system:
            self.curator_calls += 1
            kind = "curator"
            body = {"exhibition_title": f"T{self.curator_calls}", "concept": "C",
                    "sections": [{"title": f"S{i}", "narrative": f"N [{ids[0]}].", "artifacts": []} for i in range(4)],
                    "selected_items": ids}
        else:
            kind, body = "specialist", {"perspective": "p", "key_findings": [f"Finding [{ids[0]}]."], "selected_artifacts": ids}
        self.calls.append(kind)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(body)))])


CHUNKS = [RetrievalResult(f"c{i}", f"d{i}", f"Tunisia evidence {i}", {"country": "Tunisia"}) for i in (1, 2)]


def test_pipeline_reviews_fact_checks_rewrites_and_saves_the_run(tmp_path):
    llm = ScriptedLLM()
    recorder = RunRecorder(runs_dir=tmp_path, run_id="r1")
    result = run_pipeline(CHUNKS, llm, recorder=recorder)

    assert llm.calls.count("specialist") == 5
    assert llm.calls[5:] == ["review", "curator", "fact_check", "curator", "fact_check"]
    assert result.exhibition_title == "T2"                    # the rewrite replaced the first version
    assert all(v["supported"] for v in result.fact_check)
    assert "million visitors" in json.dumps(load_run(tmp_path / "r1")["events"])  # feedback is in the run log

    run = load_run(tmp_path / "r1")
    kinds = {e["kind"] for e in run["events"]}
    assert {"evidence", "llm_call", "insight", "review", "exhibition", "fact_check", "result"} <= kinds
    assert set(run["timings"]) >= {"specialists", "review", "curator", "fact_check", "total"}


def test_pipeline_can_skip_review_and_fact_check():
    llm = ScriptedLLM()
    run_pipeline(CHUNKS, llm, review=False, fact_check=False)
    assert "review" not in llm.calls and "fact_check" not in llm.calls
