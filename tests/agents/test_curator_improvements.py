from __future__ import annotations

from unittest.mock import patch

import pytest

from agents.base_agent import InsightObject
from agents.curator import MAX_ATTEMPTS, CuratorAgent, CuratorValidationError
from agents.shared_context import SharedContext


def _payload(n: int = 4, items=None, section_artifacts=None) -> dict:
    return {
        "exhibition_title": "T",
        "concept": "C",
        "sections": [
            {"title": f"S{i}", "narrative": "N [a1].", "artifacts": section_artifacts or []}
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
    assert llm.call_count == MAX_ATTEMPTS


def test_invented_artifacts_are_dropped_and_fall_back_to_cross_refs():
    curator = CuratorAgent(openai_client=None)
    with patch.object(curator, "_call_llm", return_value=_payload(items=["ghost"], section_artifacts=["ghost", "a2"])):
        result = curator.run(_ctx())
    assert result.selected_items == ["a1"]
    assert result.sections[0].artifacts == ["a2", "a1"]  # listed + cited in the narrative


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


def _with_narratives(*narratives) -> dict:
    payload = _payload()
    for section, text in zip(payload["sections"], narratives):
        section["narrative"] = text
    return payload


def test_narrative_citing_unknown_ids_is_sent_back():
    curator = CuratorAgent(openai_client=None)
    bad = _with_narratives("Claim [ghost].")
    with patch.object(curator, "_call_llm", side_effect=[bad, _payload()]) as llm:
        result = curator.run(_ctx())
    assert "unknown: ghost" in llm.call_args_list[1].args[1]
    assert result.sections[0].narrative == "N [a1]."


def test_uncited_narrative_is_sent_back_and_cited_ids_become_section_artifacts():
    curator = CuratorAgent(openai_client=None)
    with patch.object(curator, "_call_llm", side_effect=[_with_narratives("No source."), _with_narratives("Both [a1, a2].")]):
        result = curator.run(_ctx())
    assert result.sections[0].artifacts == ["a1", "a2"]


def test_evidence_review_and_feedback_reach_the_model():
    ctx = _ctx()
    ctx.insights["historian"].evidence = {"a1": {"content": "Text behind a1", "year": 2021}}
    ctx.review = {"tensions": [{"agents": ["historian", "visual"], "issue": "disagree"}]}
    curator = CuratorAgent(openai_client=None)
    with patch.object(curator, "_call_llm", return_value=_payload()) as llm:
        result = curator.run(ctx, feedback="FACT-CHECK: fix section 1")
    prompt = llm.call_args.args[1]
    assert "Text behind a1" in prompt and '"tensions"' in prompt and "FACT-CHECK: fix section 1" in prompt
    assert result.review == ctx.review
