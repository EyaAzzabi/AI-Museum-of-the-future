"""Specialists must see chunk IDs in their prompt and may only cite those IDs."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from agents.historian import HistorianAgent
from agents.technology import TechnologyAgent
from agents.visual import VisualAgent
from rag.vector_store.retriever import RetrievalResult

CHUNKS = [
    RetrievalResult(chunk_id="tn-1", document_id="d1", content="Parliament suspended in 2021.", metadata={}, similarity=0.9),
    RetrievalResult(chunk_id="tn-2", document_id="d2", content="Startup Act and digital growth.", metadata={}, similarity=0.8),
]


@pytest.mark.parametrize("AgentClass", [HistorianAgent, TechnologyAgent, VisualAgent])
def test_prompt_shows_chunk_ids(AgentClass) -> None:
    prompt = AgentClass(openai_client=None)._render_prompt(CHUNKS, "x", "system")
    assert "[tn-1] Parliament suspended in 2021." in prompt
    assert "[tn-2]" in prompt


ALL_AGENTS = [HistorianAgent, TechnologyAgent, VisualAgent]


@pytest.mark.parametrize("AgentClass", ALL_AGENTS)
def test_invented_artifact_ids_are_dropped(AgentClass) -> None:
    payload = {
        "perspective": "p",
        "key_findings": ["Digital growth [tn-2]."],
        "selected_artifacts": ["tn-2", "Startup Act 2018", "poster of the festival"],
    }
    agent = AgentClass(openai_client=None)
    with patch.object(agent, "_call_llm", return_value=payload):
        result = agent.run(CHUNKS)
    assert result.selected_artifacts == ["tn-2"]
    assert result.evidence["tn-2"]["content"] == "Startup Act and digital growth."


@pytest.mark.parametrize("AgentClass", ALL_AGENTS)
@pytest.mark.parametrize("finding", ["Uncited claim.", "Claim [made-up].", "Claim [tn-1] and [made-up]."])
def test_findings_need_only_valid_citations_else_abstain(AgentClass, finding) -> None:
    payload = {"perspective": "p", "key_findings": [finding], "selected_artifacts": ["tn-1"]}
    agent = AgentClass(openai_client=None)
    with patch.object(agent, "_call_llm", return_value=payload):
        result = agent.run(CHUNKS)
    assert result.key_findings == [] and result.selected_artifacts == []


@pytest.mark.parametrize("AgentClass", ALL_AGENTS)
def test_cited_ids_become_selected_artifacts(AgentClass) -> None:
    payload = {"perspective": "p", "key_findings": ["Both events [tn-1, tn-2].", "Dropped."], "selected_artifacts": []}
    agent = AgentClass(openai_client=None)
    with patch.object(agent, "_call_llm", return_value=payload):
        result = agent.run(CHUNKS)
    assert result.key_findings == ["Both events [tn-1, tn-2]."]
    assert result.selected_artifacts == ["tn-1", "tn-2"]
