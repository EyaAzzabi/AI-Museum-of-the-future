from __future__ import annotations

from unittest.mock import patch

import pytest

from agents.base_agent import InsightObject
from agents.curator import CuratorAgent, CuratorValidationError
from agents.shared_context import SharedContext


def _payload(n: int = 4, items=None, section_artifacts=None) -> dict:
    return {
        "exhibition_title": "T",
        "concept": "C",
        "sections": [
            {"title": f"S{i}", "narrative": "N", "artifacts": section_artifacts or []}
            for i in range(n)
        ],
        "selected_items": items if items is not None else ["a1"],
    }


def _ctx() -> SharedContext:
    return SharedContext(
        insights={
            "historian": InsightObject("historian", "p", ["f"], ["a1", "a2"]),
            "visual": InsightObject("visual", "", [], []),
        },
        cross_references=["a1"],
    )


def test_retries_with_feedback_after_bad_section_count():
    curator = CuratorAgent(openai_client=None)
    with patch.object(curator, "_call_llm", side_effect=[_payload(2), _payload(5)]) as llm:
        result = curator.run(_ctx())
    assert len(result.sections) == 5
    assert llm.call_count == 2
    assert "rejected" in llm.call_args_list[1].args[1]


def test_raises_after_exhausting_attempts():
    curator = CuratorAgent(openai_client=None)
    with patch.object(curator, "_call_llm", return_value=_payload(1)) as llm:
        with pytest.raises(CuratorValidationError):
            curator.run(_ctx())
    assert llm.call_count == 2


def test_invented_artifacts_are_dropped_and_fall_back_to_cross_refs():
    curator = CuratorAgent(openai_client=None)
    with patch.object(curator, "_call_llm", return_value=_payload(items=["ghost"], section_artifacts=["ghost", "a2"])):
        result = curator.run(_ctx())
    assert result.selected_items == ["a1"]
    assert result.sections[0].artifacts == ["a2"]


def test_failed_specialists_are_reported_and_told_to_the_model():
    curator = CuratorAgent(openai_client=None)
    with patch.object(curator, "_call_llm", return_value=_payload()) as llm:
        result = curator.run(_ctx())
    assert result.missing_perspectives == ["visual"]
    assert '"unavailable_perspectives": ["visual"]' in llm.call_args.args[1]


def test_changelog_header_is_not_sent_to_the_model():
    curator = CuratorAgent(openai_client=None)
    with patch.object(curator, "_call_llm", return_value=_payload()) as llm:
        curator.run(_ctx())
    assert "## v" not in llm.call_args.args[1]
    assert "Curator agent" in llm.call_args.args[1]
