"""
Tests — Sociologist Agent
==========================
Author  : EyaRachdi
Branch  : EyaRachdi_sociologistAgent

Test coverage:
    1. Unit tests  — tools (no LLM, no network)
    2. Integration tests — agent workflow with mock LLM
    3. Evaluation tests  — output quality checks
    4. Live test         — real LLM call (skipped if no API key)

Run all tests:
    pytest tests/test_sociologist.py -v

Run only unit tests (no API key needed):
    pytest tests/test_sociologist.py -v -m "not live"

Run live test (requires OPENAI_API_KEY):
    pytest tests/test_sociologist.py -v -m live
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Project root on path ──────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agents.base_agent import InsightObject
from agents.sociologist import MIN_CONFIDENCE, MIN_FINDINGS, SociologistAgent
from agents.sociologist_tools import (
    SOCIAL_THEME_KEYWORDS,
    build_evidence_bundle,
    compute_theme_coverage,
    extract_dates,
    filter_by_source,
    filter_by_theme,
    format_chunks_for_prompt,
    score_evidence_relevance,
)


# ══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_chunks():
    """Realistic Tunisia 2020-2026 chunks for testing."""
    chunks = []
    data = [
        {
            "chunk_id": "c1", "document_id": "d1",
            "content": "Tunisia's unemployment rate reached 18% in 2022, with youth unemployment exceeding 40% in some regions. The economic crisis following COVID-19 deepened inequality between urban Tunis and rural areas.",
            "metadata": {"source": "worldbank", "category": "economy"},
            "similarity": 0.91,
        },
        {
            "chunk_id": "c2", "document_id": "d2",
            "content": "President Kais Saied suspended parliament in July 2021, concentrating executive power and triggering widespread debate about Tunisia's democratic trajectory and constitutional rights.",
            "metadata": {"source": "wikipedia", "category": "politics"},
            "similarity": 0.88,
        },
        {
            "chunk_id": "c3", "document_id": "d3",
            "content": "Tunisian women's rights organizations reported increased domestic violence during COVID-19 lockdowns in 2020. NGOs documented a 30% rise in reported cases during the first confinement period.",
            "metadata": {"source": "gdelt", "category": "news"},
            "similarity": 0.85,
        },
        {
            "chunk_id": "c4", "document_id": "d4",
            "content": "Irregular migration from Tunisia to Europe surged between 2020-2023, with thousands of young Tunisians attempting the dangerous Mediterranean crossing. The phenomenon reflects deep social despair among youth.",
            "metadata": {"source": "gdelt", "category": "news"},
            "similarity": 0.83,
        },
        {
            "chunk_id": "c5", "document_id": "d5",
            "content": "Social media usage in Tunisia grew 45% between 2020-2024, with TikTok becoming the primary platform for youth political expression and cultural exchange. Facebook remains dominant for news consumption.",
            "metadata": {"source": "youtube", "category": "culture"},
            "similarity": 0.79,
        },
        {
            "chunk_id": "c6", "document_id": "d6",
            "content": "Le festival de Carthage 2022 a rassemblé plus de 100,000 spectateurs malgré la crise économique, démontrant la résistance culturelle tunisienne et l'importance des arts comme espace de liberté sociale.",
            "metadata": {"source": "wikimedia", "category": "culture"},
            "similarity": 0.75,
        },
    ]
    for d in data:
        chunk = MagicMock()
        chunk.chunk_id    = d["chunk_id"]
        chunk.document_id = d["document_id"]
        chunk.content     = d["content"]
        chunk.metadata    = d["metadata"]
        chunk.similarity  = d["similarity"]
        chunks.append(chunk)
    return chunks


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client that returns a valid sociologist response."""
    client = MagicMock()
    mock_response_data = {
        "agent": "sociologist",
        "analyst": "Dr. Amira — Sociologist, AI Museum of the Future",
        "era": "Tunisia 2020-2026",
        "perspective": (
            "Tunisia's 2020-2026 period was defined by a dual crisis: democratic backsliding "
            "under Saied's constitutional coup and deepening economic inequality that drove "
            "mass youth emigration. Future historians will recognize this era as the moment "
            "Tunisia's post-revolutionary promise collided with structural social exhaustion."
        ),
        "themes_detected": [
            "politics_civic", "economy_inequality", "migration_diaspora",
            "gender_women", "digital_social_media"
        ],
        "key_findings": [
            "The 2021 constitutional crisis revealed Tunisia's democratic fatigue: a population exhausted by political instability chose authoritarian stability over participatory governance [c2].",
            "Youth unemployment exceeding 40% in rural areas created a generation with no economic future in Tunisia, making irregular migration a rational — if deadly — choice [c1, c4].",
            "COVID-19 lockdowns exposed and amplified pre-existing gender inequalities, with domestic violence rising 30% and women's economic participation declining sharply [c3].",
            "Social media transformed from a tool of the 2011 revolution into an escape valve for youth frustration, with TikTok replacing street protest as political expression [c1].",
            "The cultural sector (Carthage festival, cinema) maintained surprising vitality despite economic crisis, suggesting culture functioned as social resilience infrastructure [c4].",
        ],
        "selected_artifacts": ["c1", "c2", "c4"],
        "artifact_justification": (
            "These three chunks capture the economic despair (c1), political rupture (c2), "
            "and migration as social response (c4) — the core triangle of Tunisia 2020-2026."
        ),
        "confidence_score": 0.82,
        "evidence_gaps": [
            "Limited data on rural vs urban social dynamics",
            "No direct youth voice data (interviews, surveys)"
        ],
    }

    # Mock chat completion
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps(mock_response_data)
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    client.chat.completions.create.return_value = mock_completion

    return client


@pytest.fixture
def agent(mock_openai_client):
    """SociologistAgent with mock client, no retriever."""
    return SociologistAgent(openai_client=mock_openai_client, retriever=None)


# ══════════════════════════════════════════════════════════════════════════════
# 1. UNIT TESTS — Tools (no LLM, no network)
# ══════════════════════════════════════════════════════════════════════════════

class TestSociologistTools:

    def test_social_theme_keywords_coverage(self):
        """All 10 social themes must have keywords defined."""
        expected_themes = {
            "politics_civic", "economy_inequality", "gender_women",
            "youth_education", "migration_diaspora", "culture_identity",
            "religion_secularism", "environment_urban", "health_wellbeing",
            "digital_social_media",
        }
        assert expected_themes == set(SOCIAL_THEME_KEYWORDS.keys())
        for theme, keywords in SOCIAL_THEME_KEYWORDS.items():
            assert len(keywords) >= 5, f"Theme '{theme}' has fewer than 5 keywords"

    def test_filter_by_theme_economy(self, sample_chunks):
        """filter_by_theme should keep chunks matching economy keywords."""
        filtered = filter_by_theme(sample_chunks, "economy_inequality")
        assert len(filtered) >= 1
        for chunk in filtered:
            content = chunk.content.lower()
            keywords = [kw.lower() for kw in SOCIAL_THEME_KEYWORDS["economy_inequality"]]
            assert any(kw in content for kw in keywords), \
                f"Chunk not relevant to economy: {chunk.content[:50]}"

    def test_filter_by_theme_migration(self, sample_chunks):
        """filter_by_theme should detect migration-related chunks."""
        filtered = filter_by_theme(sample_chunks, "migration_diaspora")
        assert len(filtered) >= 1

    def test_filter_by_source(self, sample_chunks):
        """filter_by_source should return only chunks from specified sources."""
        filtered = filter_by_source(sample_chunks, ["gdelt"])
        for chunk in filtered:
            assert chunk.metadata["source"] == "gdelt"

    def test_filter_by_source_multiple(self, sample_chunks):
        """filter_by_source should work with multiple sources."""
        filtered = filter_by_source(sample_chunks, ["gdelt", "wikipedia"])
        sources = {c.metadata["source"] for c in filtered}
        assert sources.issubset({"gdelt", "wikipedia"})

    def test_compute_theme_coverage(self, sample_chunks):
        """compute_theme_coverage should return a non-empty dict."""
        coverage = compute_theme_coverage(sample_chunks)
        assert isinstance(coverage, dict)
        assert len(coverage) > 0
        # Economy and politics should be covered
        assert "economy_inequality" in coverage or "politics_civic" in coverage

    def test_extract_dates(self, sample_chunks):
        """extract_dates should find years in the 2020-2026 range."""
        start, end = extract_dates(sample_chunks)
        assert start != "" or end != "", "Should find at least one date"
        if start and end:
            assert start <= end

    def test_format_chunks_for_prompt(self, sample_chunks):
        """format_chunks_for_prompt should return non-empty string within char limit."""
        formatted = format_chunks_for_prompt(sample_chunks, max_total_chars=5000)
        assert isinstance(formatted, str)
        assert len(formatted) > 0
        assert len(formatted) <= 5100  # small buffer for headers
        # Should contain source info
        assert "Source:" in formatted

    def test_format_chunks_empty(self):
        """format_chunks_for_prompt with empty list should return fallback message."""
        result = format_chunks_for_prompt([])
        assert "No evidence" in result

    def test_score_evidence_relevance(self, sample_chunks):
        """score_evidence_relevance should return sorted (chunk, score) tuples."""
        themes = ["economy_inequality", "politics_civic", "migration_diaspora"]
        scored = score_evidence_relevance(sample_chunks, themes)
        assert len(scored) == len(sample_chunks)
        # Should be sorted descending
        scores = [s for _, s in scored]
        assert scores == sorted(scores, reverse=True)
        # All scores should be 0-1
        for _, score in scored:
            assert 0.0 <= score <= 1.0


# ══════════════════════════════════════════════════════════════════════════════
# 2. INTEGRATION TESTS — Agent workflow with mock LLM
# ══════════════════════════════════════════════════════════════════════════════

class TestSociologistAgent:

    def test_agent_initialization(self, agent):
        """Agent should initialize with correct tools available."""
        assert agent._tools_available["theme_filtering"] is True
        assert agent._tools_available["evidence_scoring"] is True
        assert agent._tools_available["self_validation"] is True
        assert agent._tools_available["rag_retrieval"] is False  # no retriever

    def test_run_returns_insight_object(self, agent, sample_chunks):
        """run() should return an InsightObject."""
        result = agent.run(sample_chunks)
        assert isinstance(result, InsightObject)
        assert result.agent == "sociologist"

    def test_insight_has_perspective(self, agent, sample_chunks):
        """InsightObject must have a non-empty perspective."""
        result = agent.run(sample_chunks)
        assert result.perspective
        assert len(result.perspective) > 20

    def test_insight_has_findings(self, agent, sample_chunks):
        """InsightObject must have at least MIN_FINDINGS findings."""
        result = agent.run(sample_chunks)
        assert len(result.key_findings) >= MIN_FINDINGS
        for finding in result.key_findings:
            assert isinstance(finding, str)
            assert len(finding) > 0

    def test_insight_has_artifacts(self, agent, sample_chunks):
        """InsightObject should have selected_artifacts."""
        result = agent.run(sample_chunks)
        assert isinstance(result.selected_artifacts, list)

    def test_run_with_empty_chunks(self, agent):
        """With no evidence the agent abstains without calling the LLM."""
        result = agent.run([])
        assert isinstance(result, InsightObject)
        assert result.agent == "sociologist"
        assert result.key_findings == []
        agent.openai_client.chat.completions.create.assert_not_called()

    def test_run_with_no_llm_client(self, sample_chunks):
        """Agent with no LLM client raises so the pipeline marks the perspective missing."""
        agent_no_llm = SociologistAgent(openai_client=None, retriever=None)
        with patch("time.sleep"):
            with pytest.raises(ValueError):
                agent_no_llm.run(sample_chunks)

    def test_system_prompt_contains_chain_of_thought(self, agent, sample_chunks):
        """System prompt should include CoT steps."""
        system_prompt = agent._build_system_prompt(sample_chunks)
        assert "STEP 1" in system_prompt
        assert "STEP 2" in system_prompt
        assert "STEP 3" in system_prompt

    def test_system_prompt_contains_role(self, agent, sample_chunks):
        """System prompt should contain Dr. Amira persona."""
        system_prompt = agent._build_system_prompt(sample_chunks)
        assert "Dr. Amira" in system_prompt

    def test_user_prompt_contains_evidence(self, agent, sample_chunks):
        """User prompt should contain formatted evidence chunks."""
        user_prompt = agent._build_user_prompt(sample_chunks)
        assert "Source:" in user_prompt or "Evidence" in user_prompt

    def test_validate_and_fix_missing_keys(self, agent, sample_chunks):
        """_validate_and_fix should add missing keys."""
        incomplete = {"perspective": "Some perspective"}
        fixed = agent._validate_and_fix(incomplete, sample_chunks)
        for key in ["agent", "key_findings", "selected_artifacts", "confidence_score"]:
            assert key in fixed

    def test_validate_does_not_pad_findings(self, agent, sample_chunks):
        """_validate_and_fix keeps short output instead of inventing placeholder findings."""
        payload = {
            "agent": "sociologist",
            "perspective": "Test",
            "key_findings": ["Only one finding"],
            "selected_artifacts": [],
            "themes_detected": [],
            "confidence_score": 0.5,
        }
        fixed = agent._validate_and_fix(payload, sample_chunks)
        assert fixed["key_findings"] == ["Only one finding"]

    def test_validate_clamps_confidence(self, agent, sample_chunks):
        """_validate_and_fix should clamp confidence_score to [0, 1]."""
        payload = {
            "agent": "sociologist",
            "perspective": "Test",
            "key_findings": ["f1", "f2", "f3"],
            "selected_artifacts": [],
            "themes_detected": [],
            "confidence_score": 150.0,  # invalid
        }
        fixed = agent._validate_and_fix(payload, sample_chunks)
        assert 0.0 <= fixed["confidence_score"] <= 1.0

    def test_llm_retry_on_failure(self, sample_chunks):
        """Agent should retry LLM call on failure."""
        client = MagicMock()
        # First 2 calls fail, 3rd succeeds
        valid_response = {
            "agent": "sociologist",
            "perspective": "Test perspective for Tunisia.",
            "key_findings": ["Finding 1", "Finding 2", "Finding 3"],
            "selected_artifacts": ["c1"],
            "themes_detected": ["politics_civic"],
            "confidence_score": 0.7,
        }
        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps(valid_response)
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]

        client.chat.completions.create.side_effect = [
            Exception("API timeout"),
            Exception("Rate limit"),
            mock_completion,
        ]
        agent = SociologistAgent(openai_client=client, retriever=None)
        with patch("time.sleep"):
            result = agent.run(sample_chunks)
        assert isinstance(result, InsightObject)
        assert client.chat.completions.create.call_count == 3


# ══════════════════════════════════════════════════════════════════════════════
# 3. EVALUATION TESTS — Output quality
# ══════════════════════════════════════════════════════════════════════════════

class TestSociologistOutputQuality:

    def test_perspective_tunisia_context(self, agent, sample_chunks):
        """Perspective should mention Tunisia or relevant context."""
        result = agent.run(sample_chunks)
        perspective_lower = result.perspective.lower()
        # Should reference Tunisia or relevant social concept
        has_context = any(word in perspective_lower for word in [
            "tunisia", "tunisian", "tunisie", "society", "social", "2020", "2026"
        ])
        assert has_context, f"Perspective lacks Tunisia context: {result.perspective}"

    def test_findings_are_specific(self, agent, sample_chunks):
        """Findings should be specific (more than 10 words each)."""
        result = agent.run(sample_chunks)
        for finding in result.key_findings:
            word_count = len(finding.split())
            assert word_count >= 8, f"Finding too short ({word_count} words): {finding}"

    def test_perspective_has_no_metadata_tags(self, agent, sample_chunks):
        """Perspective is exhibition text: no [Themes:...] / [Evidence:...] tags."""
        result = agent.run(sample_chunks)
        assert "[Themes:" not in result.perspective
        assert "[Evidence:" not in result.perspective

    def test_confidence_score_logged(self, agent, sample_chunks, caplog):
        """Agent logs themes, evidence count and confidence instead."""
        with caplog.at_level("INFO", logger="agents.sociologist"):
            agent.run(sample_chunks)
        assert "confidence=82%" in caplog.text

    def test_no_duplicate_findings(self, agent, sample_chunks):
        """Findings should not be exact duplicates."""
        result = agent.run(sample_chunks)
        findings_lower = [f.lower().strip() for f in result.key_findings]
        assert len(findings_lower) == len(set(findings_lower)), \
            "Duplicate findings detected"

    def test_prompt_template_loaded(self, agent):
        """Prompt template should load from prompts/sociologist.md."""
        template = agent._load_prompt_template()
        assert len(template) > 100, "Prompt template is too short or not loaded"
        assert "sociologist" in template.lower()


# ══════════════════════════════════════════════════════════════════════════════
# 4. LIVE TEST — Real LLM call (requires OPENAI_API_KEY)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.live
class TestSociologistLive:

    @pytest.fixture
    def live_agent(self):
        """Real agent with the configured LLM provider — skipped if no API key."""
        if not (os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY")):
            pytest.skip("LLM_API_KEY not set — skipping live test")
        from agents.llm_config import build_llm_client
        return SociologistAgent(openai_client=build_llm_client(), retriever=None)

    def test_live_run_returns_valid_insight(self, live_agent, sample_chunks):
        """Real LLM call should return valid InsightObject with quality output."""
        result = live_agent.run(sample_chunks)

        assert isinstance(result, InsightObject)
        assert result.agent == "sociologist"
        assert len(result.perspective) > 50
        assert len(result.key_findings) >= MIN_FINDINGS

        print("\n" + "="*60)
        print("LIVE TEST RESULT")
        print("="*60)
        print(f"Perspective: {result.perspective[:200]}...")
        print(f"\nFindings ({len(result.key_findings)}):")
        for i, f in enumerate(result.key_findings, 1):
            print(f"  {i}. {f[:100]}...")
        print(f"\nArtifacts: {result.selected_artifacts}")
        print("="*60)


def test_pipeline_passes_retriever_to_every_agent():
    """run_pipeline(retriever=...) lets every agent search; the sociologist through HyDE."""
    from agents.pipeline import _build_specialist_agents

    retriever = MagicMock()
    agents = _build_specialist_agents(openai_client=None, retriever=retriever)
    assert all(agent.retriever is retriever for agent in agents.values())

    sociologist = agents["sociologist"]
    with patch.object(sociologist, "_retrieve_evidence", return_value=MagicMock(chunks=[])):
        sociologist.search_own_evidence()
    assert sociologist._hyde_retriever.retriever is retriever


def test_hyde_empty_hypothetical_doc_falls_back_to_query():
    """Reasoning models can return empty content; HyDE must still search."""
    from rag.hyde_retriever import HyDERetriever

    empty = MagicMock()
    empty.choices = [MagicMock()]
    empty.choices[0].message.content = ""
    llm = MagicMock()
    llm.chat.completions.create.return_value = empty
    retriever = MagicMock()
    retriever.retrieve.side_effect = lambda query, rerank=False: [MagicMock(chunk_id="x")] if query.strip() else []

    hyde = HyDERetriever(retriever=retriever, llm_client=llm, top_k=5)
    assert hyde.generate_hypothetical_doc("gender_women", "Tunisia women") == "Tunisia women"
    assert len(hyde.retrieve_with_hyde("gender_women", "Tunisia women")) == 1


def test_hyde_documents_are_cached_and_themes_run_in_parallel(tmp_path, monkeypatch):
    """A hypothetical document is generated once per (model, theme, query), then read from disk."""
    from rag.hyde_retriever import HyDERetriever

    monkeypatch.setenv("HYDE_CACHE_DIR", str(tmp_path))
    doc = MagicMock()
    doc.choices = [MagicMock()]
    doc.choices[0].message.content = "Hypothetical passage about Tunisian youth."
    llm = MagicMock()
    llm.chat.completions.create.return_value = doc
    retriever = MagicMock()
    retriever.retrieve.return_value = [MagicMock(chunk_id="x")]

    hyde = HyDERetriever(retriever=retriever, llm_client=llm, top_k=5)
    themes = ["politics_civic", "gender_women", "youth_education"]
    first = hyde.retrieve_all_themes(themes)
    second = hyde.retrieve_all_themes(themes)

    assert [r.theme for r in first] == themes            # order kept despite parallel execution
    assert llm.chat.completions.create.call_count == 3   # second run answered from the cache
    assert second[0].hypothetical_document == "Hypothetical passage about Tunisian youth."
