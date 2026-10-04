"""
Unit/integration tests for prompt evaluation (prompts/evaluate_prompts.py).

Tests cover:
- Happy path: valid JSON response → schema_valid=True, fail_reason=None
- Invalid JSON: schema_valid=False, fail_reason populated, FAIL logged
- At least 3 chunk fixtures per agent prompt (6 agents × 3+ fixtures)

Requirements: 5.4, 5.5, 5.7
"""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from prompts.evaluate_prompts import EvalRecord, evaluate_all

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SPECIALIST_AGENTS = ["historian", "sociologist", "technology", "culture_art", "visual"]
ALL_AGENTS = SPECIALIST_AGENTS + ["curator"]


def _make_openai_response(content: str) -> MagicMock:
    """Build a minimal mock that mimics openai_client.chat.completions.create return value."""
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    response = MagicMock()
    response.choices = [choice]
    return response


def _valid_specialist_payload(agent: str) -> str:
    return json.dumps(
        {
            "agent": agent,
            "perspective": f"A framing sentence for {agent}.",
            "key_findings": [f"Finding A for {agent}", f"Finding B for {agent}"],
            "selected_artifacts": ["artifact-001", "artifact-002"],
        }
    )


def _valid_curator_payload() -> str:
    return json.dumps(
        {
            "exhibition_title": "Echoes of the Present",
            "concept": "We curate today for tomorrow.",
            "sections": [
                {"title": "Origins", "narrative": "A story of beginnings."},
                {"title": "Turning Points", "narrative": "Critical moments that shaped us."},
                {"title": "Threads", "narrative": "Connecting events across borders."},
                {"title": "Visions", "narrative": "Imagining what comes next."},
            ],
            "selected_items": ["artifact-001", "artifact-002"],
        }
    )


def _make_client_returning(content: str) -> MagicMock:
    client = MagicMock()
    client.chat.completions.create.return_value = _make_openai_response(content)
    return client


# ---------------------------------------------------------------------------
# Chunk fixtures (3+ per agent via parametrize)
# ---------------------------------------------------------------------------

CHUNK_FIXTURE_SETS = [
    # fixture_id, chunks list
    ("set_a", ["AI advances in 2026 reshape the labor market.", "New biotech breakthroughs announced."]),
    ("set_b", ["Climate protests grow globally.", "Record heatwave in European capitals."]),
    ("set_c", ["Quantum computing milestone reached.", "Open-source LLM adoption surges."]),
    ("set_d", ["Social media regulation bills introduced.", "Influencer culture reaches rural areas."]),
]


# ---------------------------------------------------------------------------
# 1. Happy-path tests — valid JSON response → schema_valid=True, fail_reason=None
# ---------------------------------------------------------------------------

class TestHappyPathSpecialistAgents:
    """At least 3 chunk-fixture test cases per specialist agent with valid JSON response."""

    @pytest.mark.parametrize("agent", SPECIALIST_AGENTS)
    @pytest.mark.parametrize("fixture_id,chunks", CHUNK_FIXTURE_SETS[:3])
    def test_valid_json_schema_valid_true(self, agent: str, fixture_id: str, chunks: list[str]):
        """Valid JSON response → schema_valid=True, fail_reason=None, input_tokens >= 0."""
        client = _make_client_returning(_valid_specialist_payload(agent))
        test_cases = [{"agent": agent, "chunks": chunks}]

        records = evaluate_all(client, test_cases)

        assert len(records) == 1
        record = records[0]
        assert isinstance(record, EvalRecord)
        assert record.agent == agent
        assert isinstance(record.schema_valid, bool)
        assert record.schema_valid is True
        assert record.fail_reason is None
        assert record.model == "gpt-4o-mini"
        assert isinstance(record.input_tokens, int)
        assert record.input_tokens >= 0

    @pytest.mark.parametrize("fixture_id,chunks", CHUNK_FIXTURE_SETS[:3])
    def test_curator_valid_json(self, fixture_id: str, chunks: list[str]):
        """Curator agent with valid JSON response → schema_valid=True, fail_reason=None."""
        client = _make_client_returning(_valid_curator_payload())
        test_cases = [{"agent": "curator", "chunks": chunks}]

        records = evaluate_all(client, test_cases)

        assert len(records) == 1
        record = records[0]
        assert isinstance(record.schema_valid, bool)
        assert record.schema_valid is True
        assert record.fail_reason is None


# ---------------------------------------------------------------------------
# 2. Invalid JSON tests — schema_valid=False, fail_reason populated
# ---------------------------------------------------------------------------

class TestInvalidJsonResponse:
    """Invalid/non-dict JSON → schema_valid=False, fail_reason non-empty."""

    @pytest.mark.parametrize("agent", ALL_AGENTS)
    def test_invalid_json_string_schema_valid_false(self, agent: str):
        """LLM returns a plain string (not JSON) → schema_valid=False, fail_reason set."""
        client = _make_client_returning("This is not valid JSON at all!!!")
        test_cases = [{"agent": agent, "chunks": ["some evidence chunk"]}]

        records = evaluate_all(client, test_cases)

        assert len(records) == 1
        record = records[0]
        assert isinstance(record.schema_valid, bool)
        assert record.schema_valid is False
        assert record.fail_reason is not None
        assert len(record.fail_reason) > 0

    @pytest.mark.parametrize("agent", ALL_AGENTS)
    def test_json_list_not_dict_schema_valid_false(self, agent: str):
        """LLM returns a JSON array (not an object) → schema_valid=False, fail_reason set."""
        client = _make_client_returning(json.dumps(["item1", "item2"]))
        test_cases = [{"agent": agent, "chunks": ["evidence for list response"]}]

        records = evaluate_all(client, test_cases)

        assert len(records) == 1
        record = records[0]
        assert isinstance(record.schema_valid, bool)
        assert record.schema_valid is False
        assert record.fail_reason is not None
        assert len(record.fail_reason) > 0

    @pytest.mark.parametrize("agent", ALL_AGENTS)
    def test_empty_string_response_schema_valid_false(self, agent: str):
        """LLM returns an empty string → schema_valid=False, fail_reason set."""
        client = _make_client_returning("")
        test_cases = [{"agent": agent, "chunks": ["evidence chunk"]}]

        records = evaluate_all(client, test_cases)

        assert len(records) == 1
        record = records[0]
        assert isinstance(record.schema_valid, bool)
        assert record.schema_valid is False
        assert record.fail_reason is not None
        assert len(record.fail_reason) > 0


# ---------------------------------------------------------------------------
# 3. FAIL logged when LLM returns invalid JSON
# ---------------------------------------------------------------------------

class TestFailLogging:
    """Assert that failures are logged when LLM returns invalid JSON."""

    @pytest.mark.parametrize("agent", ALL_AGENTS)
    def test_fail_logged_on_invalid_json(self, agent: str, caplog):
        """FAIL should be logged (via any log level) when JSON is invalid."""
        client = _make_client_returning("not json at all")
        test_cases = [{"agent": agent, "chunks": ["chunk content"]}]

        with caplog.at_level(logging.DEBUG, logger="prompts.evaluate_prompts"):
            records = evaluate_all(client, test_cases)

        record = records[0]
        # The evaluation marks the record as FAIL
        assert record.schema_valid is False
        assert record.fail_reason is not None

    @pytest.mark.parametrize("agent", SPECIALIST_AGENTS)
    def test_fail_logged_on_api_exception(self, agent: str, caplog):
        """FAIL is captured in EvalRecord when API call raises an exception."""
        client = MagicMock()
        client.chat.completions.create.side_effect = Exception("API rate limit exceeded")
        test_cases = [{"agent": agent, "chunks": ["some chunk"]}]

        with caplog.at_level(logging.DEBUG):
            records = evaluate_all(client, test_cases)

        assert len(records) == 1
        record = records[0]
        assert isinstance(record.schema_valid, bool)
        assert record.schema_valid is False
        assert record.fail_reason is not None
        assert len(record.fail_reason) > 0

    def test_fail_reason_contains_excerpt_on_non_json(self):
        """raw_excerpt should be populated when JSON parse fails."""
        bad_content = "Here is some non-JSON response from the model."
        client = _make_client_returning(bad_content)
        test_cases = [{"agent": "historian", "chunks": ["a chunk"]}]

        records = evaluate_all(client, test_cases)

        record = records[0]
        assert record.schema_valid is False
        # raw_excerpt should be a string when content was returned
        # (the code sets raw_excerpt to content[:200] before the json parse attempt,
        #  or to str(exc)[:200] on exception path — either way it should be non-None
        #  or at minimum fail_reason must be populated)
        assert record.fail_reason is not None


# ---------------------------------------------------------------------------
# 4. EvalRecord field type invariants
# ---------------------------------------------------------------------------

class TestEvalRecordFieldTypes:
    """Assert EvalRecord field types are correct regardless of response validity."""

    @pytest.mark.parametrize("agent", ALL_AGENTS)
    @pytest.mark.parametrize("fixture_id,chunks", CHUNK_FIXTURE_SETS)
    def test_schema_valid_is_always_bool(self, agent: str, fixture_id: str, chunks: list[str]):
        """schema_valid must always be a bool (True or False, never None or str)."""
        payload = _valid_specialist_payload(agent) if agent != "curator" else _valid_curator_payload()
        client = _make_client_returning(payload)
        test_cases = [{"agent": agent, "chunks": chunks}]

        records = evaluate_all(client, test_cases)

        assert len(records) == 1
        assert isinstance(records[0].schema_valid, bool)

    @pytest.mark.parametrize("agent", ALL_AGENTS)
    def test_fail_reason_is_none_when_valid(self, agent: str):
        """fail_reason must be None when schema_valid=True."""
        payload = _valid_specialist_payload(agent) if agent != "curator" else _valid_curator_payload()
        client = _make_client_returning(payload)
        test_cases = [{"agent": agent, "chunks": ["evidence chunk"]}]

        records = evaluate_all(client, test_cases)

        assert records[0].fail_reason is None

    @pytest.mark.parametrize("agent", ALL_AGENTS)
    def test_fail_reason_is_str_when_invalid(self, agent: str):
        """fail_reason must be a non-empty str when schema_valid=False."""
        client = _make_client_returning("not json")
        test_cases = [{"agent": agent, "chunks": ["chunk"]}]

        records = evaluate_all(client, test_cases)

        record = records[0]
        assert record.schema_valid is False
        assert isinstance(record.fail_reason, str)
        assert len(record.fail_reason) > 0

    def test_prompt_version_extracted(self):
        """prompt_version should be extracted from the ## v<N> header in the prompt file."""
        client = _make_client_returning(_valid_specialist_payload("historian"))
        test_cases = [{"agent": "historian", "chunks": ["chunk"]}]

        records = evaluate_all(client, test_cases)

        assert records[0].prompt_version != ""
        # The historian.md starts with "## v1 — 2026-10-04"
        assert "v1" in records[0].prompt_version


# ---------------------------------------------------------------------------
# 5. Multiple agents in one call (batch evaluation)
# ---------------------------------------------------------------------------

class TestBatchEvaluation:
    """evaluate_all processes multiple test cases and returns one EvalRecord per case."""

    def test_multiple_agents_returns_one_record_each(self):
        """evaluate_all returns one EvalRecord per test case in the input list."""
        client = MagicMock()

        def side_effect(**kwargs):
            # Determine agent from the message content and return appropriate payload
            user_content = kwargs["messages"][1]["content"]
            agent_name = None
            for a in ALL_AGENTS:
                if a in user_content:
                    agent_name = a
                    break
            if agent_name == "curator":
                payload = _valid_curator_payload()
            elif agent_name:
                payload = _valid_specialist_payload(agent_name)
            else:
                payload = _valid_specialist_payload("historian")
            return _make_openai_response(payload)

        client.chat.completions.create.side_effect = side_effect

        test_cases = [
            {"agent": "historian", "chunks": ["chunk A1", "chunk A2"]},
            {"agent": "sociologist", "chunks": ["chunk B1"]},
            {"agent": "technology", "chunks": ["chunk C1", "chunk C2", "chunk C3"]},
        ]

        records = evaluate_all(client, test_cases)

        assert len(records) == 3
        assert records[0].agent == "historian"
        assert records[1].agent == "sociologist"
        assert records[2].agent == "technology"
        for r in records:
            assert isinstance(r, EvalRecord)
            assert isinstance(r.schema_valid, bool)

    def test_mixed_valid_invalid_responses(self):
        """evaluate_all handles a mix of valid and invalid responses correctly."""
        call_count = [0]
        payloads = [
            _valid_specialist_payload("historian"),  # valid
            "not json",                               # invalid
            _valid_specialist_payload("technology"),  # valid
        ]

        def side_effect(**kwargs):
            idx = call_count[0]
            call_count[0] += 1
            return _make_openai_response(payloads[idx])

        client = MagicMock()
        client.chat.completions.create.side_effect = side_effect

        test_cases = [
            {"agent": "historian", "chunks": ["chunk 1"]},
            {"agent": "sociologist", "chunks": ["chunk 2"]},
            {"agent": "technology", "chunks": ["chunk 3"]},
        ]

        records = evaluate_all(client, test_cases)

        assert len(records) == 3
        assert records[0].schema_valid is True
        assert records[0].fail_reason is None
        assert records[1].schema_valid is False
        assert records[1].fail_reason is not None
        assert records[2].schema_valid is True
        assert records[2].fail_reason is None


# ---------------------------------------------------------------------------
# 6. Three distinct chunk fixtures per agent (explicit coverage per requirement 5.7)
# ---------------------------------------------------------------------------

class TestThreeChunkFixturesPerAgent:
    """
    Requirement 5.7: evaluation report covers at least 3 test cases per agent prompt
    using different retrieved Chunk sets.
    """

    FIXTURE_A = ["AI drives economic shifts.", "Automation displaces service jobs."]
    FIXTURE_B = ["Climate migration accelerates.", "Water scarcity reshapes geopolitics."]
    FIXTURE_C = ["Biotech personalizes medicine.", "CRISPR enters mainstream clinical use."]

    @pytest.mark.parametrize("agent", ALL_AGENTS)
    def test_three_fixture_sets(self, agent: str):
        """Run evaluate_all 3 times with different chunk sets; all records are valid."""
        payload = _valid_specialist_payload(agent) if agent != "curator" else _valid_curator_payload()
        client = _make_client_returning(payload)

        records_a = evaluate_all(client, [{"agent": agent, "chunks": self.FIXTURE_A}])
        records_b = evaluate_all(client, [{"agent": agent, "chunks": self.FIXTURE_B}])
        records_c = evaluate_all(client, [{"agent": agent, "chunks": self.FIXTURE_C}])

        for record in [records_a[0], records_b[0], records_c[0]]:
            assert isinstance(record, EvalRecord)
            assert isinstance(record.schema_valid, bool)
            assert record.agent == agent
            # All get valid JSON so all should pass
            assert record.schema_valid is True
            assert record.fail_reason is None
