from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from agents.base_agent import InsightObject
from agents.historian import HistorianAgent
from rag.vector_store.retriever import RetrievalResult


@pytest.fixture
def sample_chunks() -> list[RetrievalResult]:
    return [
        RetrievalResult(
            chunk_id="hist-001",
            document_id="doc-001",
            content="The global treaty on artificial intelligence safety was signed in Paris by 85 nations in 2026.",
            metadata={"source": "gdelt", "category": "news"},
            similarity=0.95,
        ),
        RetrievalResult(
            chunk_id="hist-002",
            document_id="doc-002",
            content="Urban reforestation programs expanded across Mediterranean cities to combat climate heatwaves.",
            metadata={"source": "wikipedia", "category": "history"},
            similarity=0.89,
        ),
    ]


def test_historian_agent_strips_changelog_header_from_prompt():
    """Verify that version changelog headers (before '---') are stripped before LLM dispatch."""
    agent = HistorianAgent(openai_client=None)
    mock_payload = {
        "agent": "historian",
        "perspective": "A 22nd-century perspective on early AI regulation.",
        "key_findings": ["Milestone treaty signed."],
        "selected_artifacts": ["hist-001"],
    }

    with patch.object(agent, "_call_llm", return_value=mock_payload) as mock_llm:
        chunks = [
            RetrievalResult(
                chunk_id="hist-001",
                document_id="doc-001",
                content="Treaty signed.",
                metadata={},
                similarity=0.9,
            )
        ]
        agent.run(chunks)

        mock_llm.assert_called_once()
        _, user_content = mock_llm.call_args[0]
        # The version header must not be present in the user prompt sent to LLM
        assert "## v3 —" not in user_content
        assert "## v2 —" not in user_content
        assert "## v1 —" not in user_content
        # The actual prompt body instructions must be present
        assert "Socio-Historical Agent" in user_content


def test_historian_agent_output_structure(sample_chunks):
    """Verify that HistorianAgent returns a well-structured, cited InsightObject."""
    agent = HistorianAgent(openai_client=None)
    mock_payload = {
        "agent": "historian",
        "perspective": "The 2020s marked a pivotal epoch of technological convergence and environmental response.",
        "key_findings": [
            "Key Event: Historic multilateral AI governance accord established [hist-001].",
            "Historical Significance: Cities adapted to climate heatwaves [hist-002].",
            "Century-Scale Impact: Foundations for 22nd-century human-machine coexistence [hist-001].",
        ],
        "selected_artifacts": ["hist-001", "hist-002"],
    }

    with patch.object(agent, "_call_llm", return_value=mock_payload):
        insight = agent.run(sample_chunks)

    assert isinstance(insight, InsightObject)
    assert insight.agent == "historian"
    assert "2020s marked a pivotal epoch" in insight.perspective
    assert len(insight.key_findings) == 3
    assert insight.selected_artifacts == ["hist-001", "hist-002"]
    assert set(insight.evidence) == {"hist-001", "hist-002"}


def test_historian_agent_filters_hallucinated_artifacts(sample_chunks):
    """Strict grounding test: Hallucinated artifact IDs must be purged from selected_artifacts."""
    agent = HistorianAgent(openai_client=None)
    mock_payload = {
        "agent": "historian",
        "perspective": "Historical overview.",
        "key_findings": ["Significant shift [hist-002]."],
        # 'invented-chunk-999' is not in sample_chunks
        "selected_artifacts": ["invented-chunk-999", "hist-002"],
    }

    with patch.object(agent, "_call_llm", return_value=mock_payload):
        insight = agent.run(sample_chunks)

    # Only 'hist-002' is grounded in sample_chunks; 'invented-chunk-999' must be dropped
    assert "invented-chunk-999" not in insight.selected_artifacts
    assert insight.selected_artifacts == ["hist-002"]


def test_historian_agent_abstains_when_findings_cite_invented_ids(sample_chunks):
    """Findings resting on invented sources are dropped; with none left the agent abstains."""
    agent = HistorianAgent(openai_client=None)
    mock_payload = {
        "agent": "historian",
        "perspective": "Historical overview.",
        "key_findings": ["Significant shift [ghost-id-1]."],
        "selected_artifacts": ["ghost-id-1", "ghost-id-2"],
    }

    with patch.object(agent, "_call_llm", return_value=mock_payload):
        insight = agent.run(sample_chunks)

    assert insight.key_findings == [] and insight.selected_artifacts == []


def test_historian_agent_handles_empty_or_missing_llm_fields(sample_chunks):
    """An empty LLM payload makes the agent abstain instead of inventing default findings."""
    agent = HistorianAgent(openai_client=None)
    with patch.object(agent, "_call_llm", return_value={}):
        insight = agent.run(sample_chunks)

    assert insight.agent == "historian"
    assert insight.perspective == ""
    assert insight.key_findings == []
    assert insight.selected_artifacts == []


def test_historian_agent_propagates_llm_errors(sample_chunks):
    """When LLM call fails, the exception must propagate to let the pipeline handle resilience."""
    agent = HistorianAgent(openai_client=None)
    with patch.object(agent, "_call_llm", side_effect=ValueError("LLM call failed")):
        with pytest.raises(ValueError, match="LLM call failed"):
            agent.run(sample_chunks)
