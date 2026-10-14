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


@pytest.mark.parametrize("AgentClass", [TechnologyAgent, VisualAgent])
def test_invented_artifact_ids_are_dropped(AgentClass) -> None:
    payload = {
        "perspective": "p",
        "key_findings": ["f"],
        "selected_artifacts": ["tn-2", "Startup Act 2018", "poster of the festival"],
    }
    agent = AgentClass(openai_client=None)
    with patch.object(agent, "_call_llm", return_value=payload):
        assert agent.run(CHUNKS).selected_artifacts == ["tn-2"]


@pytest.mark.parametrize("AgentClass", [TechnologyAgent, VisualAgent])
def test_only_invented_ids_fall_back_to_first_chunk(AgentClass) -> None:
    payload = {"perspective": "p", "key_findings": ["f"], "selected_artifacts": ["made-up"]}
    agent = AgentClass(openai_client=None)
    with patch.object(agent, "_call_llm", return_value=payload):
        assert agent.run(CHUNKS).selected_artifacts == ["tn-1"]
