"""Technology agent around the agent: HTTP bridge for n8n, demo loader, evaluation helpers."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from agents.technology import TechnologyAgent
from rag.vector_store.retriever import RetrievalResult


def _llm(payload: dict):
    client = MagicMock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))]
    )
    return client


SOLAR = {"chunk_id": "sol-1", "content": "Tunisia opens a solar power plant.",
         "metadata": {"source": "gdelt", "category": "news", "year": 2026}}


@pytest.fixture
def make_client():
    from serve_technology import create_app

    def build(payload: dict, retriever=None):
        retrievers = []

        def retriever_factory(country, year_from, year_to):
            retrievers.append((country, year_from, year_to))
            return retriever

        app = create_app(agent_factory=TechnologyAgent, client_factory=lambda: _llm(payload),
                         retriever_factory=retriever_factory)
        app.config["TESTING"] = True
        return app.test_client(), retrievers

    return build


# ── serve_technology.py ──────────────────────────────────────────────────────

def test_health(make_client):
    client, _ = make_client({})
    assert client.get("/health").get_json() == {"status": "ok", "agent": "technology"}


def test_analyze_with_shared_chunks_only(make_client, monkeypatch):
    monkeypatch.delenv("TECHNOLOGY_API_TOKEN", raising=False)
    client, retrievers = make_client({"perspective": "Energy.", "key_findings": [
        "A solar plant opened in 2026 [sol-1].", "It produces 500 MW [sol-1]."]})
    body = client.post("/api/technology", json={"chunks": [SOLAR], "use_rag": False}).get_json()

    assert body["status"] == "ok"
    assert body["insight"]["key_findings"] == ["A solar plant opened in 2026 [sol-1]."]
    assert body["dropped_findings"][0]["figures"] == ["500"]
    assert "- energy & climate tech: 1 (1 news)" in body["coverage"]
    assert retrievers == []


def test_api_reports_findings_dropped_by_the_budget(make_client, monkeypatch):
    monkeypatch.delenv("TECHNOLOGY_API_TOKEN", raising=False)
    findings = [f"Solar fact {i} [sol-1]." for i in range(6)] + [
        f"Interpretation: reading {i} [sol-1]." for i in range(3)]
    client, _ = make_client({"perspective": "Energy.", "key_findings": findings})
    body = client.post("/api/technology", json={"chunks": [SOLAR], "use_rag": False}).get_json()

    assert len(body["insight"]["key_findings"]) == 5
    assert sum(f.startswith("Interpretation:") for f in body["insight"]["key_findings"]) == 1
    assert [d["rule"] for d in body["dropped_findings"]] == ["finding_budget"] * 4


def test_analyze_uses_own_search_with_the_requested_filters(make_client, monkeypatch):
    monkeypatch.delenv("TECHNOLOGY_API_TOKEN", raising=False)
    retriever = MagicMock()
    retriever.search_many.return_value = [RetrievalResult(chunk_id="sat-1", document_id="d",
                                                          content="A satellite was launched.")]
    retriever.default_filters = None
    retriever.config.rerank_agent_searches = False
    client, retrievers = make_client({"perspective": "p", "key_findings": ["A launch [sat-1]."]}, retriever)
    body = client.post("/api/technology", json={"country": None, "year_from": 2021}).get_json()

    assert retrievers == [(None, 2021, 2026)]
    assert body["insight"]["selected_artifacts"] == ["sat-1"]


@pytest.mark.parametrize("payload, message", [
    ([], "A JSON object is required."),
    ({"use_rag": False}, "Send chunks or set use_rag to true."),
    ({"chunks": [{"content": "no id"}]}, "each chunk needs a chunk_id and a content string."),
    ({"year_from": "2020"}, "year_from must be a year or null."),
    ({"use_rag": "yes"}, "use_rag must be a boolean."),
])
def test_analyze_rejects_invalid_requests(make_client, monkeypatch, payload, message):
    monkeypatch.delenv("TECHNOLOGY_API_TOKEN", raising=False)
    client, _ = make_client({})
    response = client.post("/api/technology", json=payload)
    assert response.status_code == 400
    assert response.get_json()["error"] == message


def test_analyze_requires_the_token_when_configured(make_client, monkeypatch):
    monkeypatch.setenv("TECHNOLOGY_API_TOKEN", "secret")
    client, _ = make_client({})
    assert client.post("/api/technology", json={"chunks": [SOLAR]}).status_code == 401


def test_provider_errors_are_reported_without_details(monkeypatch):
    from serve_technology import create_app

    monkeypatch.delenv("TECHNOLOGY_API_TOKEN", raising=False)

    def broken_client():
        raise RuntimeError("secret key gsk_123 rejected")

    app = create_app(agent_factory=TechnologyAgent, client_factory=broken_client)
    response = app.test_client().post("/api/technology", json={"chunks": [SOLAR], "use_rag": False})
    assert response.status_code == 502
    assert "gsk_" not in response.get_data(as_text=True)


# ── demo_technology.py and evaluation helpers ────────────────────────────────

def test_demo_loads_every_chunk_cited_in_the_live_run_once():
    from demo_technology import load_live_run_evidence

    chunks = load_live_run_evidence()
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids)) == 21
    assert all(c.content for c in chunks)


def test_selection_stats_measures_balance():
    from evaluation.evaluate_technology_retrieval import selection_stats

    paper = RetrievalResult(chunk_id="a", document_id="a", content="A machine learning benchmark.",
                            metadata={"source": "arxiv", "category": "science"})
    solar = RetrievalResult(chunk_id="b", document_id="b", content="Solar plant.",
                            metadata={"category": "news", "in_scope": False})
    other = RetrievalResult(chunk_id="c", document_id="c", content="Budget vote.", metadata={})
    stats = selection_stats([paper, paper, solar, other])
    assert stats == {"items": 4, "domains_covered": 2, "largest_domain_share": 0.5, "research_share": 0.5,
                     "not_technology_share": 0.25, "in_scope_share": 0.75}
    assert selection_stats([])["items"] == 0


def test_technology_cases_follow_the_agent_queries():
    from evaluation.evaluate_technology_retrieval import load_cases
    from agents.technology_tools import TECH_DOMAINS

    cases = load_cases()
    assert len(cases) == len(TechnologyAgent.search_queries)
    assert [c["domain"] for c in cases] == list(TECH_DOMAINS)


def test_overstatement_markers_flag_the_observed_v2_failures():
    from agents.run_log import RunRecorder
    from agents.base_agent import InsightObject
    from evaluation.compare_technology_prompts import score

    from demo_technology import LIVE_RUN

    live = json.loads(LIVE_RUN.read_text(encoding="utf-8"))
    observed = live["insights"]["technology"]
    insight = InsightObject("technology", observed["perspective"], observed["key_findings"],
                            observed["selected_artifacts"])
    by_id = {cid: RetrievalResult(chunk_id=cid, document_id=cid, content=e["content"], metadata=e)
             for cid, e in observed["evidence"].items()}
    result = score(insight, {"key_findings": observed["key_findings"]}, RunRecorder(), by_id)
    assert set(result["overstatement_detail"]) == {
        "possibility read as fact (source: 'can')", "one expert read as several",
        "one item read as a trend", "term added (source: 'vaccine')"}
    assert result["domains_cited"] == ["AI & computing", "health & biotech"]


V3_RENEWABLE = ("News from 2026 highlighted Leguria's efforts to boost renewable energy production, reflecting "
                "ongoing investments in solar and wind power [831de05c]")
V3_TITLE = ("In 2026 news reported that access to social media was being responsibly regulated, indicating new "
            "governance over digital communication [77fd4d4d]")
V4_RENEWABLE = "In 2026 a news headline reported that the region of Liguria was increasing its renewable energy production [831de05c]"
V4_TITLE = 'In 2026 a news article titled "Responsibly regulated access to social media" was reported [77fd4d4d]'


def _score(findings, perspective=""):
    from agents.base_agent import InsightObject
    from agents.run_log import RunRecorder
    from evaluation.compare_technology_prompts import score

    by_id = {cid: RetrievalResult(chunk_id=cid, document_id=cid, content="headline", metadata={"category": "news"})
             for cid in ("831de05c", "77fd4d4d")}
    insight = InsightObject("technology", perspective, findings, list(by_id))
    return score(insight, {"key_findings": findings}, RunRecorder(), by_id)


def test_v3_failure_markers_flag_v3_findings_and_not_v4_findings():
    v3 = _score([V3_RENEWABLE, V3_TITLE] * 3, perspective="Lijoria expanded solar and wind power.")
    assert set(v3["overstatement_detail"]) == {
        "term added (source: 'renewable energy')", "guessed name (source: ليجوريا, Liguria)",
        "title read as an event (v3, v4)"}
    assert v3["unlabelled_readings"] == 6
    assert v3["over_budget"] == 1
    assert len(v3["perspective_markers"]) == 2

    v4 = _score([V4_RENEWABLE, V4_TITLE], perspective="Liguria increased its renewable energy production.")
    assert (v4["overstatement_markers"], v4["unlabelled_readings"], v4["over_budget"], v4["perspective_markers"]) \
        == (0, 0, 0, [])


def test_unmeasured_outcome_marker_flags_v4_interpretations_and_not_hedged_ones():
    v4 = "Interpretation: the high efficacy dramatically reduced COVID-19 mortality and transformed daily life [831de05c]."
    hedged = ("Interpretation: a vaccine reported as nearly 95 percent effective may suggest how fast biomedical "
              "research could answer a pandemic [831de05c].")
    assert _score([V4_RENEWABLE, v4])["unmeasured_outcomes"] == [v4]
    assert _score([V4_RENEWABLE, hedged])["unmeasured_outcomes"] == []
