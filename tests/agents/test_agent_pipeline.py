# Feature: museum-week2-pipeline, Property 10: SharedContext cross-references correctness

"""
Property-based tests for the SharedContext component.

**Property 10: SharedContext cross-references correctness**
Validates: Requirements 4.7

For any collection of InsightObject instances, compute_cross_references must
return exactly the artifact IDs that appear in the `selected_artifacts` of two
or more distinct agents — no more, no fewer, and with no duplicates.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from agents.base_agent import InsightObject
from agents.shared_context import compute_cross_references

# ─────────────────────────────────────────────────────────────────────────────
# Strategies
# ─────────────────────────────────────────────────────────────────────────────

# A fixed pool of artifact IDs so that some naturally appear across agents.
ARTIFACT_POOL = [f"artifact_{i}" for i in range(10)]

# Agent name pool to ensure agents are distinctly named.
AGENT_POOL = [f"agent_{i}" for i in range(8)]


@st.composite
def insight_object_strategy(draw: st.DrawFn) -> InsightObject:
    """Generate an InsightObject with artifact IDs drawn from ARTIFACT_POOL.

    Drawing from a shared pool means different InsightObjects will often
    share artifact IDs, which exercises the cross-reference detection logic.
    """
    agent_name = draw(st.sampled_from(AGENT_POOL))
    perspective = draw(st.text(min_size=1, max_size=80))
    key_findings = draw(
        st.lists(st.text(min_size=1, max_size=100), min_size=0, max_size=5)
    )
    # Each agent cites 0-4 artifacts from the shared pool
    selected_artifacts = draw(
        st.lists(
            st.sampled_from(ARTIFACT_POOL),
            min_size=0,
            max_size=4,
            unique=True,
        )
    )
    return InsightObject(
        agent=agent_name,
        perspective=perspective,
        key_findings=key_findings,
        selected_artifacts=selected_artifacts,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Property 10: SharedContext cross-references correctness
# Validates: Requirements 4.7
# ─────────────────────────────────────────────────────────────────────────────


@given(st.lists(insight_object_strategy(), min_size=0, max_size=8))
@settings(max_examples=100)
def test_cross_references_correctness(insights_list: list[InsightObject]) -> None:
    """**Validates: Requirements 4.7**

    For any collection of InsightObjects, compute_cross_references must return
    exactly the artifact IDs that appear in the selected_artifacts of two or
    more distinct agents:

    - Every ID in the result must appear in >= 2 distinct agents' selected_artifacts
    - Every ID that appears in >= 2 distinct agents' selected_artifacts must be
      in the result
    - The result must contain no duplicates
    """
    # Build a uniquely-keyed insights dict (use index as key when agents share names)
    insights: dict[str, InsightObject] = {}
    for idx, insight in enumerate(insights_list):
        # Use index to ensure uniqueness so each InsightObject is treated as a
        # separate agent entry, consistent with the per-agent keying intent.
        key = f"{insight.agent}_{idx}"
        insights[key] = InsightObject(
            agent=insight.agent,
            perspective=insight.perspective,
            key_findings=insight.key_findings,
            selected_artifacts=insight.selected_artifacts,
        )

    result = compute_cross_references(insights)

    # ── Reference implementation: compute expected cross-references ──────────
    # Count how many distinct agents (keys) cite each artifact.
    agent_sets: dict[str, set[str]] = {}
    for agent_key, insight in insights.items():
        for artifact in insight.selected_artifacts:
            if artifact not in agent_sets:
                agent_sets[artifact] = set()
            agent_sets[artifact].add(agent_key)

    expected = {
        artifact for artifact, agents in agent_sets.items() if len(agents) >= 2
    }

    # ── Assertion 1: no duplicates in result ─────────────────────────────────
    assert len(result) == len(set(result)), (
        f"compute_cross_references returned duplicates: {result}"
    )

    # ── Assertion 2: result is a subset of expected (no false positives) ─────
    result_set = set(result)
    extra = result_set - expected
    assert not extra, (
        f"compute_cross_references returned IDs NOT cited by >= 2 agents: {extra}"
    )

    # ── Assertion 3: expected is a subset of result (no false negatives) ─────
    missing = expected - result_set
    assert not missing, (
        f"compute_cross_references missed IDs cited by >= 2 agents: {missing}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Feature: museum-week2-pipeline, Property 9: Specialist agent output structure
# and grounding
# Validates: Requirements 4.2, 4.5
# ─────────────────────────────────────────────────────────────────────────────

"""
Task 8.6 — Property 9: Specialist agent output structure and grounding
Task 8.7 — Unit tests for specialist agents

**Property 9: Specialist agent output structure and grounding**
Validates: Requirements 4.2, 4.5

For any non-empty list of RetrievalResult-like chunks passed to any specialist
agent (Historian, Sociologist, Technology, CultureArt, Visual), the returned
InsightObject SHALL have non-empty `agent`, `perspective`, `key_findings`, and
`selected_artifacts` fields, where `key_findings` is a non-empty list and every
entry in `selected_artifacts` appears in the IDs or URLs of the input chunk list.
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from agents.historian import HistorianAgent
from agents.sociologist import SociologistAgent
from agents.technology import TechnologyAgent
from agents.culture_art import CultureArtAgent
from agents.visual import VisualAgent
from rag.vector_store.retriever import RetrievalResult


# ─────────────────────────────────────────────────────────────────────────────
# Strategies
# ─────────────────────────────────────────────────────────────────────────────

@st.composite
def retrieval_result_strategy(draw: st.DrawFn) -> RetrievalResult:
    """Generate a RetrievalResult with realistic field values."""
    chunk_id = draw(st.text(min_size=1, max_size=40, alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),
        whitelist_characters="-_",
    )))
    document_id = draw(st.text(min_size=1, max_size=40, alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),
        whitelist_characters="-_",
    )))
    content = draw(st.text(min_size=1, max_size=200))
    similarity = draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
    return RetrievalResult(
        chunk_id=chunk_id,
        document_id=document_id,
        content=content,
        metadata={},
        similarity=similarity,
    )


# Ordered list of (AgentClass, agent_name) for parametrisation
SPECIALIST_AGENTS = [
    (HistorianAgent, "historian"),
    (SociologistAgent, "sociologist"),
    (TechnologyAgent, "technology"),
    (CultureArtAgent, "culture_art"),
    (VisualAgent, "visual"),
]


def _make_mock_llm_response(chunks: list[RetrievalResult], agent_name: str) -> dict:
    """Return a dict that _call_llm would return; uses chunk IDs as selected_artifacts."""
    return {
        "agent": agent_name,
        "perspective": f"Test perspective for {agent_name}.",
        "key_findings": [f"Finding from {agent_name} agent."],
        "selected_artifacts": [chunk.chunk_id for chunk in chunks],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Property 9 — output structure and grounding
# Validates: Requirements 4.2, 4.5
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("AgentClass,agent_name", SPECIALIST_AGENTS)
@given(chunks=st.lists(retrieval_result_strategy(), min_size=1))
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_specialist_agent_output_structure_and_grounding(
    AgentClass,
    agent_name: str,
    chunks: list[RetrievalResult],
) -> None:
    """**Validates: Requirements 4.2, 4.5**

    For any non-empty list of RetrievalResult chunks, every specialist agent
    must return an InsightObject where:
    - `agent` is non-empty
    - `perspective` is non-empty
    - `key_findings` is a non-empty list
    - every entry in `selected_artifacts` is grounded in the input chunk IDs
    """
    mock_response = _make_mock_llm_response(chunks, agent_name)
    input_ids = {chunk.chunk_id for chunk in chunks}

    agent = AgentClass(openai_client=None)
    with patch.object(agent, "_call_llm", return_value=mock_response):
        result = agent.run(chunks)

    # agent field must be non-empty
    assert result.agent, f"[{agent_name}] InsightObject.agent is empty"

    # perspective must be non-empty
    assert result.perspective and result.perspective.strip(), (
        f"[{agent_name}] InsightObject.perspective is empty"
    )

    # key_findings must be a non-empty list
    assert isinstance(result.key_findings, list), (
        f"[{agent_name}] InsightObject.key_findings is not a list"
    )
    assert len(result.key_findings) >= 1, (
        f"[{agent_name}] InsightObject.key_findings is empty"
    )

    # every selected_artifact must be grounded in the input chunk IDs
    assert isinstance(result.selected_artifacts, list), (
        f"[{agent_name}] InsightObject.selected_artifacts is not a list"
    )
    for artifact in result.selected_artifacts:
        assert artifact in input_ids, (
            f"[{agent_name}] selected_artifact '{artifact}' not found in input chunk IDs: "
            f"{input_ids}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Task 8.7 — Unit tests for specialist agents
# Validates: Requirements 4.2, 4.5
# ─────────────────────────────────────────────────────────────────────────────

# Fixed chunk fixtures for unit tests
SAMPLE_CHUNKS = [
    RetrievalResult(
        chunk_id="chunk-001",
        document_id="doc-001",
        content="The Industrial Revolution transformed society.",
        metadata={"source": "arxiv", "category": "history"},
        similarity=0.92,
    ),
    RetrievalResult(
        chunk_id="chunk-002",
        document_id="doc-001",
        content="Steam engines enabled mass production.",
        metadata={"source": "arxiv", "category": "technology"},
        similarity=0.88,
    ),
]


@pytest.mark.parametrize("AgentClass,agent_name", SPECIALIST_AGENTS)
def test_specialist_agent_returns_populated_insight_object(
    AgentClass, agent_name: str
) -> None:
    """Each specialist agent returns a fully-populated InsightObject when
    _call_llm is mocked to return a valid payload.

    Validates: Requirements 4.2, 4.5
    """
    mock_response = {
        "agent": agent_name,
        "perspective": f"A {agent_name} perspective on the corpus.",
        "key_findings": ["First finding.", "Second finding."],
        "selected_artifacts": ["chunk-001", "chunk-002"],
    }

    agent = AgentClass(openai_client=None)
    with patch.object(agent, "_call_llm", return_value=mock_response):
        result = agent.run(SAMPLE_CHUNKS)

    assert result.agent, f"[{agent_name}] agent field is empty"
    assert result.perspective and result.perspective.strip(), (
        f"[{agent_name}] perspective field is empty"
    )
    assert isinstance(result.key_findings, list) and len(result.key_findings) >= 1, (
        f"[{agent_name}] key_findings must be a non-empty list"
    )
    assert isinstance(result.selected_artifacts, list) and len(result.selected_artifacts) >= 1, (
        f"[{agent_name}] selected_artifacts must be a non-empty list"
    )


@pytest.mark.parametrize("AgentClass,agent_name", SPECIALIST_AGENTS)
def test_specialist_agent_malformed_llm_response_raises(
    AgentClass, agent_name: str
) -> None:
    """When _call_llm raises ValueError (malformed response), the exception
    propagates out of agent.run() so the pipeline (task 9) can catch it.

    Validates: Requirements 4.2, 4.6
    """
    agent = AgentClass(openai_client=None)
    with patch.object(
        agent,
        "_call_llm",
        side_effect=ValueError("LLM response was not a JSON object."),
    ):
        with pytest.raises(ValueError):
            agent.run(SAMPLE_CHUNKS)


@pytest.mark.parametrize("AgentClass,agent_name", SPECIALIST_AGENTS)
def test_specialist_agent_llm_response_with_missing_fields_uses_defaults(
    AgentClass, agent_name: str
) -> None:
    """When _call_llm returns a dict with missing optional fields, the agent
    falls back to sensible defaults and still returns a valid InsightObject.

    Validates: Requirements 4.2
    """
    # Minimal payload — missing key_findings and selected_artifacts
    mock_response: dict = {}

    agent = AgentClass(openai_client=None)
    with patch.object(agent, "_call_llm", return_value=mock_response):
        result = agent.run(SAMPLE_CHUNKS)

    # The agent must not raise; it returns an InsightObject with fallback values
    assert isinstance(result.key_findings, list)
    assert isinstance(result.selected_artifacts, list)


# ─────────────────────────────────────────────────────────────────────────────
# Feature: museum-week2-pipeline, Property 11: Curator synthesis structure
# Validates: Requirements 4.4
# ─────────────────────────────────────────────────────────────────────────────

"""
Task 9.3 — Property 11: Curator synthesis structure

**Property 11: Curator synthesis structure**
Validates: Requirements 4.4

For any SharedContext object (even if some agent slots contain empty
placeholder InsightObjects), the CuratorAgent SHALL return an
ExhibitionSynthesis with non-empty exhibition_title, non-empty concept,
a sections list containing 4–6 items (each with non-empty title and
narrative), and a non-empty selected_items list.
"""

from agents.curator import CuratorAgent, ExhibitionSynthesis, SectionObject
from agents.shared_context import SharedContext
from agents.pipeline import run_pipeline


# ─────────────────────────────────────────────────────────────────────────────
# Strategy: shared_context_strategy
# ─────────────────────────────────────────────────────────────────────────────

SPECIALIST_AGENT_NAMES = ["historian", "sociologist", "technology", "culture_art", "visual"]


@st.composite
def shared_context_strategy(draw: st.DrawFn) -> SharedContext:
    """Generate a SharedContext with a mix of populated and empty InsightObject slots.

    Some slots are genuine populated insights; others are empty placeholders
    (agent="" perspective="" key_findings=[] selected_artifacts=[]) to simulate
    failed specialist agents — as per the pipeline's error-handling design.
    """
    insights: dict[str, InsightObject] = {}

    for agent_name in SPECIALIST_AGENT_NAMES:
        # Randomly decide if this slot is an empty placeholder or populated
        is_placeholder = draw(st.booleans())
        if is_placeholder:
            insights[agent_name] = InsightObject(
                agent="",
                perspective="",
                key_findings=[],
                selected_artifacts=[],
            )
        else:
            perspective = draw(st.text(min_size=1, max_size=100))
            key_findings = draw(
                st.lists(st.text(min_size=1, max_size=80), min_size=1, max_size=5)
            )
            selected_artifacts = draw(
                st.lists(
                    st.sampled_from(ARTIFACT_POOL),
                    min_size=0,
                    max_size=4,
                    unique=True,
                )
            )
            insights[agent_name] = InsightObject(
                agent=agent_name,
                perspective=perspective,
                key_findings=key_findings,
                selected_artifacts=selected_artifacts,
            )

    # cross_references is computed from the insights
    from agents.shared_context import compute_cross_references
    cross_refs = compute_cross_references(insights)

    return SharedContext(insights=insights, cross_references=cross_refs)


def _make_valid_curator_payload(num_sections: int = 4) -> dict:
    """Return a dict matching the ExhibitionSynthesis schema with the given section count."""
    return {
        "exhibition_title": "The Age of Transformation",
        "concept": "A journey through the defining forces of our era.",
        "sections": [
            {
                "title": f"Section {i + 1}: A Critical Lens",
                "narrative": f"This section explores perspective {i + 1} in depth.",
            }
            for i in range(num_sections)
        ],
        "selected_items": ["artifact_0", "artifact_1"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Property 11 — Curator synthesis structure
# Validates: Requirements 4.4
# ─────────────────────────────────────────────────────────────────────────────


@given(shared_context=shared_context_strategy(), num_sections=st.integers(min_value=4, max_value=6))
@settings(max_examples=100)
def test_curator_synthesis_structure(shared_context: SharedContext, num_sections: int) -> None:
    """**Validates: Requirements 4.4**

    For any SharedContext (including ones with empty placeholder insight slots),
    the CuratorAgent returns an ExhibitionSynthesis where:
    - exhibition_title is non-empty
    - concept is non-empty
    - sections is a list with 4–6 items, each with non-empty title and narrative
    - selected_items is non-empty
    """
    payload = _make_valid_curator_payload(num_sections)
    curator = CuratorAgent(openai_client=None)

    with patch.object(curator, "_call_llm", return_value=payload):
        result = curator.run(shared_context)

    # ── exhibition_title must be non-empty ───────────────────────────────────
    assert result.exhibition_title and result.exhibition_title.strip(), (
        "ExhibitionSynthesis.exhibition_title is empty"
    )

    # ── concept must be non-empty ────────────────────────────────────────────
    assert result.concept and result.concept.strip(), (
        "ExhibitionSynthesis.concept is empty"
    )

    # ── sections must be a list with 4–6 items ───────────────────────────────
    assert isinstance(result.sections, list), (
        "ExhibitionSynthesis.sections is not a list"
    )
    assert 4 <= len(result.sections) <= 6, (
        f"ExhibitionSynthesis.sections has {len(result.sections)} items; expected 4–6"
    )

    # ── each section must have non-empty title and narrative ─────────────────
    for idx, section in enumerate(result.sections):
        assert isinstance(section, SectionObject), (
            f"sections[{idx}] is not a SectionObject"
        )
        assert section.title and section.title.strip(), (
            f"sections[{idx}].title is empty"
        )
        assert section.narrative and section.narrative.strip(), (
            f"sections[{idx}].narrative is empty"
        )

    # ── selected_items must be non-empty ─────────────────────────────────────
    assert isinstance(result.selected_items, list) and len(result.selected_items) >= 1, (
        "ExhibitionSynthesis.selected_items is empty"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Task 9.4 — Unit tests for pipeline
# Validates: Requirements 4.6, 4.7, 4.8
# ─────────────────────────────────────────────────────────────────────────────

import time
from unittest.mock import patch, MagicMock


# Fixed dummy chunks for pipeline unit tests
DUMMY_CHUNKS = [
    RetrievalResult(
        chunk_id=f"pipeline-chunk-{i:03d}",
        document_id=f"pipeline-doc-{i:03d}",
        content=f"Dummy pipeline chunk content {i}.",
        metadata={"source": "arxiv", "category": "science"},
        similarity=0.80 - i * 0.01,
    )
    for i in range(5)
]

# A valid ExhibitionSynthesis fixture for pipeline tests
VALID_EXHIBITION = ExhibitionSynthesis(
    exhibition_title="Pipeline Test Exhibition",
    concept="An exhibition produced by the pipeline test suite.",
    sections=[
        SectionObject(title=f"Section {i + 1}", narrative=f"Narrative for section {i + 1}.")
        for i in range(4)
    ],
    selected_items=["pipeline-chunk-000", "pipeline-chunk-001"],
)

# A valid InsightObject fixture for pipeline tests
def _make_insight(agent_name: str, artifacts: list[str] | None = None) -> InsightObject:
    return InsightObject(
        agent=agent_name,
        perspective=f"A {agent_name} perspective.",
        key_findings=[f"{agent_name} finding 1."],
        selected_artifacts=artifacts or [f"pipeline-chunk-000"],
    )


def _patch_all_specialists(specialist_return_fn=None):
    """Return a context manager that patches all 5 specialist agents' run() methods."""
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        from agents.historian import HistorianAgent
        from agents.sociologist import SociologistAgent
        from agents.technology import TechnologyAgent
        from agents.culture_art import CultureArtAgent
        from agents.visual import VisualAgent

        default_fn = specialist_return_fn or (
            lambda name: _make_insight(name)
        )

        with (
            patch.object(HistorianAgent, "run", side_effect=lambda chunks: default_fn("historian")),
            patch.object(SociologistAgent, "run", side_effect=lambda chunks: default_fn("sociologist")),
            patch.object(TechnologyAgent, "run", side_effect=lambda chunks: default_fn("technology")),
            patch.object(CultureArtAgent, "run", side_effect=lambda chunks: default_fn("culture_art")),
            patch.object(VisualAgent, "run", side_effect=lambda chunks: default_fn("visual")),
        ):
            yield

    return _ctx()


def test_run_pipeline_completes_within_120_seconds() -> None:
    """Assert run_pipeline completes under 120 s on dummy chunk data with mock agents.

    Validates: Requirements 4.8
    """
    mock_curator = MagicMock()
    mock_curator.run.return_value = VALID_EXHIBITION

    with _patch_all_specialists():
        with patch("agents.pipeline.CuratorAgent", return_value=mock_curator):
            start = time.time()
            result = run_pipeline(DUMMY_CHUNKS, openai_client=None, timeout_secs=120)
            elapsed = time.time() - start

    assert elapsed < 120, f"run_pipeline took {elapsed:.1f} s — exceeded 120 s limit"
    assert isinstance(result, ExhibitionSynthesis), "run_pipeline did not return ExhibitionSynthesis"
    assert result.exhibition_title, "ExhibitionSynthesis.exhibition_title is empty"


def test_run_pipeline_cross_references_shared_artifacts() -> None:
    """Assert cross_references contains shared artifact IDs when 2+ agents cite the same artifact.

    Validates: Requirements 4.7

    Two agents (historian, sociologist) share 'shared-artifact-X'.
    The remaining three agents cite only their own unique artifact.
    The pipeline's SharedContext.cross_references must contain 'shared-artifact-X'.
    """
    shared_artifact = "shared-artifact-X"
    captured_contexts: list[SharedContext] = []

    def historian_run(_chunks):
        return _make_insight("historian", artifacts=[shared_artifact, "hist-only"])

    def sociologist_run(_chunks):
        return _make_insight("sociologist", artifacts=[shared_artifact, "soc-only"])

    def technology_run(_chunks):
        return _make_insight("technology", artifacts=["tech-only"])

    def culture_art_run(_chunks):
        return _make_insight("culture_art", artifacts=["art-only"])

    def visual_run(_chunks):
        return _make_insight("visual", artifacts=["visual-only"])

    def curator_run_capture(ctx: SharedContext) -> ExhibitionSynthesis:
        captured_contexts.append(ctx)
        return VALID_EXHIBITION

    mock_curator = MagicMock()
    mock_curator.run.side_effect = curator_run_capture

    from agents.historian import HistorianAgent
    from agents.sociologist import SociologistAgent
    from agents.technology import TechnologyAgent
    from agents.culture_art import CultureArtAgent
    from agents.visual import VisualAgent

    with (
        patch.object(HistorianAgent, "run", side_effect=historian_run),
        patch.object(SociologistAgent, "run", side_effect=sociologist_run),
        patch.object(TechnologyAgent, "run", side_effect=technology_run),
        patch.object(CultureArtAgent, "run", side_effect=culture_art_run),
        patch.object(VisualAgent, "run", side_effect=visual_run),
        patch("agents.pipeline.CuratorAgent", return_value=mock_curator),
    ):
        run_pipeline(DUMMY_CHUNKS, openai_client=None, timeout_secs=120)

    assert len(captured_contexts) == 1, "Curator was not called exactly once"
    ctx = captured_contexts[0]
    assert shared_artifact in ctx.cross_references, (
        f"Expected '{shared_artifact}' in cross_references; got {ctx.cross_references}"
    )
    # Unique artifacts should NOT appear in cross_references
    for unique in ("hist-only", "soc-only", "tech-only", "art-only", "visual-only"):
        assert unique not in ctx.cross_references, (
            f"Artifact '{unique}' should not be in cross_references (cited by only 1 agent)"
        )


def test_run_pipeline_resilient_when_one_agent_fails() -> None:
    """Assert pipeline produces a non-empty ExhibitionSynthesis even when 1 specialist fails.

    Validates: Requirements 4.6

    The HistorianAgent raises an exception; the remaining four agents succeed.
    The pipeline must still return a valid ExhibitionSynthesis.
    """
    mock_curator = MagicMock()
    mock_curator.run.return_value = VALID_EXHIBITION

    from agents.historian import HistorianAgent
    from agents.sociologist import SociologistAgent
    from agents.technology import TechnologyAgent
    from agents.culture_art import CultureArtAgent
    from agents.visual import VisualAgent

    with (
        patch.object(HistorianAgent, "run", side_effect=RuntimeError("Historian LLM call failed")),
        patch.object(SociologistAgent, "run", side_effect=lambda c: _make_insight("sociologist")),
        patch.object(TechnologyAgent, "run", side_effect=lambda c: _make_insight("technology")),
        patch.object(CultureArtAgent, "run", side_effect=lambda c: _make_insight("culture_art")),
        patch.object(VisualAgent, "run", side_effect=lambda c: _make_insight("visual")),
        patch("agents.pipeline.CuratorAgent", return_value=mock_curator),
    ):
        result = run_pipeline(DUMMY_CHUNKS, openai_client=None, timeout_secs=120)

    assert isinstance(result, ExhibitionSynthesis), (
        "run_pipeline did not return ExhibitionSynthesis when 1 agent failed"
    )
    assert result.exhibition_title, "ExhibitionSynthesis.exhibition_title is empty"


def test_run_pipeline_resilient_when_two_agents_fail() -> None:
    """Assert pipeline produces a non-empty ExhibitionSynthesis even when 2 specialists fail.

    Validates: Requirements 4.6

    HistorianAgent and SociologistAgent both raise exceptions; the remaining
    three agents succeed.  The pipeline must still return a valid ExhibitionSynthesis.
    """
    mock_curator = MagicMock()
    mock_curator.run.return_value = VALID_EXHIBITION

    from agents.historian import HistorianAgent
    from agents.sociologist import SociologistAgent
    from agents.technology import TechnologyAgent
    from agents.culture_art import CultureArtAgent
    from agents.visual import VisualAgent

    with (
        patch.object(HistorianAgent, "run", side_effect=RuntimeError("Historian failed")),
        patch.object(SociologistAgent, "run", side_effect=ValueError("Sociologist malformed response")),
        patch.object(TechnologyAgent, "run", side_effect=lambda c: _make_insight("technology")),
        patch.object(CultureArtAgent, "run", side_effect=lambda c: _make_insight("culture_art")),
        patch.object(VisualAgent, "run", side_effect=lambda c: _make_insight("visual")),
        patch("agents.pipeline.CuratorAgent", return_value=mock_curator),
    ):
        result = run_pipeline(DUMMY_CHUNKS, openai_client=None, timeout_secs=120)

    assert isinstance(result, ExhibitionSynthesis), (
        "run_pipeline did not return ExhibitionSynthesis when 2 agents failed"
    )
    assert result.exhibition_title, "ExhibitionSynthesis.exhibition_title is empty"
    assert len(result.sections) >= 4, (
        f"ExhibitionSynthesis has {len(result.sections)} sections; expected >= 4"
    )
