"""Technology agent: domain taxonomy, balanced evidence, typed evidence lines, figure guardrail."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from agents.run_log import RunRecorder
from agents.technology import TechnologyAgent
from agents.technology_tools import (
    classify_domain,
    coverage_summary,
    diversify,
    evidence_kind,
    ungrounded_numbers,
)
from rag.vector_store.retriever import RetrievalResult


def _chunk(cid: str, content: str, source: str = "gdelt", category: str = "news", year: int = 2026,
           title: str = "") -> RetrievalResult:
    return RetrievalResult(chunk_id=cid, document_id=f"doc-{cid}", content=content,
                           metadata={"source": source, "category": category, "year": year, "title": title})


# Texts from the live run of 2026-10-14.
FIGMA = _chunk("figma-1", "We conducted a randomized controlled trial with 50 product designers and 50 product "
               "managers to evaluate prospective time savings from leveraging Figma Make with large language models.",
               source="arxiv", category="science", title="Does AI Save Time on Product Design?")
GENETIC = _chunk("gen-1", "خبير في الأمن السيبراني : يمكن للذكاء الاصطناعي تصميم تسلسلات جينية جديدة")
VACCINE = _chunk("vac-1", "U.S. drugmaker Moderna says trials have shown its vaccine is nearly 95 percent effective.",
                 source="internet_archive", category="history", year=2020)
SOLAR = _chunk("sol-1", "Tunisia inaugurates a new solar power plant to cut electricity imports.")
SPACE = _chunk("spa-1", "First Tunisian satellite launched into orbit.")
POLITICS = _chunk("pol-1", "Parliament votes on the new budget law.")


def _llm(payload: dict):
    client = MagicMock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))]
    )
    return client


def _prompt_sent(client) -> str:
    return client.chat.completions.create.call_args.kwargs["messages"][1]["content"]


# ── Tools ────────────────────────────────────────────────────────────────────

def test_domains_cover_english_and_arabic_sources():
    assert classify_domain(FIGMA) == "ai_computing"
    assert classify_domain(GENETIC) == "ai_computing"   # AI, cyber and genetics tie: first domain wins
    assert classify_domain(VACCINE) == "health_biotech"
    assert classify_domain(SOLAR) == "energy_climate"
    assert classify_domain(SPACE) == "space"
    assert classify_domain(POLITICS) == "other"


def test_french_tunisian_press_is_classified():
    crisis = _chunk("e6c", "Tunisie : cinq ans après les mesures dexception de Saïed , une grave crise électrique")
    assert classify_domain(crisis) == "energy_climate"
    assert classify_domain(_chunk("num", "La transformation numérique des services publics.")) == "digital_connectivity"
    social = _chunk("ar", "وزارة الدولة للإعلام تدعو للاستخدام المسؤول لصفحات التواصل الاجتماعي وتحرّي الدقة")
    assert classify_domain(social) == "digital_connectivity"


def test_terms_match_whole_words_and_plurals():
    assert classify_domain(_chunk("x", "New vaccines approved.")) == "health_biotech"
    assert classify_domain(_chunk("y", "An orbital resort in Marseille.")) == "other"


def test_evidence_kind_reflects_what_a_source_can_prove():
    assert evidence_kind(FIGMA) == "research paper"
    assert evidence_kind(GENETIC) == "news"
    assert evidence_kind(VACCINE) == "archive"


def test_diversify_keeps_minority_domains_when_one_domain_dominates():
    papers = [_chunk(f"ai-{i}", "A large language model benchmark.", source="arxiv", category="science")
              for i in range(8)]
    selected = diversify(papers + [SOLAR, VACCINE, POLITICS], limit=4)
    ids = [c.chunk_id for c in selected]
    assert ids[:3] == ["ai-0", "sol-1", "vac-1"]
    assert "pol-1" in ids   # "other" comes last but is not excluded
    assert len(diversify(papers, limit=5)) == 5


def test_diversify_alternates_source_kinds_inside_a_domain():
    papers = [_chunk(f"ai-{i}", "Machine learning study.", source="arxiv", category="science") for i in range(3)]
    news = _chunk("ai-news", "ChatGPT reaches classrooms.")
    assert [c.chunk_id for c in diversify(papers + [news], limit=2)] == ["ai-0", "ai-news"]


def test_coverage_summary_names_domains_without_evidence():
    summary = coverage_summary([FIGMA, GENETIC, VACCINE])
    assert "- AI & computing: 2 (1 research paper, 1 news)" in summary
    assert "- space: 0 - no evidence" in summary
    assert "outside technology" not in summary
    assert "- outside technology: 1 (1 news)" in coverage_summary([POLITICS])


def test_coverage_does_not_call_a_domain_absent_when_items_of_other_domains_mention_it():
    # The v4/v5 failure: a cyber-defense paper counted under AI, and "no cybersecurity evidence".
    defense = _chunk("cy", "A formal model of machine learning and artificial intelligence for cybersecurity.",
                     source="arxiv", category="science")
    summary = coverage_summary([defense])
    assert "- AI & computing: 1 (1 research paper)" in summary
    assert "- cybersecurity & privacy: 0 as main domain; also in 1 item counted under AI & computing - not a gap" in summary
    assert "- space: 0 - no evidence" in summary


def test_ungrounded_numbers_catches_computed_and_invented_figures():
    sources = ["2026 Does AI Save Time? A trial with 50 product designers and 50 product managers."]
    assert ungrounded_numbers("A trial with 100 participants [figma-1].", sources) == ["100"]
    assert ungrounded_numbers("A trial with 50 designers in 2026 [figma-1].", sources) == []
    assert ungrounded_numbers("95% effective [vac-1].", ["nearly 95 percent effective"]) == []
    assert ungrounded_numbers("Reached 1,000 users [a].", ["1000 users"]) == []


def test_citation_ids_are_not_read_as_figures():
    assert ungrounded_numbers("A result [71108630-9f1e-4c2a].", ["no numbers here"]) == []


# ── Agent ────────────────────────────────────────────────────────────────────

def test_agent_drops_findings_with_figures_not_in_their_source(tmp_path):
    client = _llm({"perspective": "AI moved into professional workflows.", "key_findings": [
        "A randomized trial with 100 participants tested prompt-to-design tools [figma-1].",
        "A randomized trial with 50 product designers and 50 product managers tested Figma Make [figma-1].",
        "Moderna reported its vaccine nearly 95 percent effective [vac-1].",
    ]})
    agent = TechnologyAgent(client)
    agent.recorder = RunRecorder(runs_dir=tmp_path)
    result = agent.run([FIGMA, VACCINE])

    assert len(result.key_findings) == 2
    assert not any("100 participants" in f for f in result.key_findings)
    assert agent.recorder.events_of("guardrail")[0]["figures"] == ["100"]


def test_agent_abstains_when_every_finding_has_an_invented_figure():
    agent = TechnologyAgent(_llm({"perspective": "p", "key_findings": ["Adoption reached 80% [figma-1]."]}))
    assert agent.run([FIGMA]).key_findings == []


FACTS = {
    "figma-1": "A randomized trial with 50 product designers and 50 product managers tested Figma Make [figma-1].",
    "gen-1": "In 2026 a cybersecurity expert said in the press that AI can design new genetic sequences [gen-1].",
    "vac-1": "Moderna reported its vaccine nearly 95 percent effective [vac-1].",
    "sol-1": "Tunisia inaugurated a new solar power plant [sol-1].",
    "spa-1": "A first Tunisian satellite was launched [spa-1].",
}


def _interpretation(cid: str) -> str:
    return f"Interpretation: this item may indicate a change in daily life [{cid}]."


def test_budget_keeps_facts_first_with_the_domain_variety(tmp_path):
    # The v3 pattern: one interpretation after every fact, 10 findings.
    findings = [f for cid, fact in FACTS.items() for f in (fact, _interpretation(cid))]
    agent = TechnologyAgent(_llm({"perspective": "p", "key_findings": findings}))
    agent.recorder = RunRecorder(runs_dir=tmp_path)
    result = agent.run([FIGMA, GENETIC, VACCINE, SOLAR, SPACE])

    # 4 facts, one per domain (the second AI item goes), and the interpretation of a kept fact.
    assert result.key_findings == [FACTS["figma-1"], _interpretation("figma-1"), FACTS["vac-1"],
                                   FACTS["sol-1"], FACTS["spa-1"]]
    event = agent.recorder.events_of("guardrail")[0]
    assert (event["rule"], event["kept_facts"], event["kept_interpretations"]) == ("finding_budget", 4, 1)
    assert len(event["dropped"]) == 5


def test_budget_keeps_two_interpretations_when_facts_leave_room():
    findings = [FACTS["vac-1"], FACTS["sol-1"], FACTS["spa-1"]] + [_interpretation(c) for c in ("vac-1", "sol-1", "spa-1")]
    result = TechnologyAgent(_llm({"perspective": "p", "key_findings": findings})).run([VACCINE, SOLAR, SPACE])
    assert result.key_findings == findings[:5]


def test_budget_keeps_up_to_five_facts_when_there_is_no_interpretation():
    findings = list(FACTS.values()) + ["Another solar plant opened [sol-1]."]
    result = TechnologyAgent(_llm({"perspective": "p", "key_findings": findings})).run(
        [FIGMA, GENETIC, VACCINE, SOLAR, SPACE])
    assert len(result.key_findings) == 5
    assert "Another solar plant opened" not in " ".join(result.key_findings)   # its domain is already in


def test_uncited_findings_do_not_take_a_place_in_the_budget(tmp_path):
    findings = list(FACTS.values()) + ["Interpretation: technology changed everything.", "A claim [unknown-id]."]
    agent = TechnologyAgent(_llm({"perspective": "p", "key_findings": findings}))
    agent.recorder = RunRecorder(runs_dir=tmp_path)
    result = agent.run([FIGMA, GENETIC, VACCINE, SOLAR, SPACE])

    assert result.key_findings == list(FACTS.values())
    assert agent.recorder.events_of("guardrail") == []


def test_budget_runs_after_the_figure_guardrail(tmp_path):
    findings = ["A randomized trial with 100 participants tested prompt-to-design tools [figma-1]."] + list(FACTS.values())
    agent = TechnologyAgent(_llm({"perspective": "p", "key_findings": findings}))
    agent.recorder = RunRecorder(runs_dir=tmp_path)
    result = agent.run([FIGMA, GENETIC, VACCINE, SOLAR, SPACE])

    assert result.key_findings == list(FACTS.values())
    assert [e["rule"] for e in agent.recorder.events_of("guardrail")] == ["ungrounded_figure"]


def test_prompt_shows_typed_evidence_and_coverage_without_changelog():
    client = _llm({"perspective": "p", "key_findings": ["Solar plant opened [sol-1]."]})
    TechnologyAgent(client).run([SOLAR, FIGMA])
    prompt = _prompt_sent(client)

    assert ("[sol-1] (2026 · gdelt/news) Tunisia inaugurates a new solar power plant to cut electricity "
            "imports. <energy & climate tech · news>") in prompt
    assert "Figma Make with large language models. <AI & computing · research paper>" in prompt
    assert "- space: 0 - no evidence" in prompt
    assert "{coverage}" not in prompt and "## v3" not in prompt


class FusingRetriever:
    """Behaves like HybridRetriever.search_many: one ranked list per query, RRF fusion,
    and k results in total (not k per query)."""

    default_filters = None
    config = SimpleNamespace(rerank_agent_searches=False)

    def __init__(self, per_query: dict[str, list]):
        self.per_query = per_query
        self.calls = []

    def search_many(self, queries, k=None, filters=None, keywords=None, rerank_query=None):
        self.calls.append(k)
        scores: dict[str, float] = {}
        by_id = {}
        for query in queries:
            for rank, chunk in enumerate(self.per_query.get(query, [])):
                scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1.0 / (60 + rank + 1)
                by_id[chunk.chunk_id] = chunk
        return [by_id[c] for c in sorted(scores, key=scores.get, reverse=True)][:k]


def test_every_domain_reaches_the_prompt_although_search_many_caps_k_in_total():
    # The digital query returns many results that also rank high in the AI query, as the
    # keyword "digital" did on Supabase; the other domains have few results each.
    texts = {
        "ai_computing": "A large language model study.", "digital_connectivity": "Social media and digital platforms.",
        "cybersecurity": "A ransomware cyberattack.", "energy_climate": "A new solar power plant.",
        "health_biotech": "A vaccine trial.", "space": "A satellite launch.",
    }
    digital = [_chunk(f"dig-{i}", texts["digital_connectivity"]) for i in range(20)]
    per_query = {}
    for query, (domain, text) in zip(TechnologyAgent.search_queries, texts.items()):
        own = [_chunk(f"{domain}-{i}", text) for i in range(3)]
        per_query[query] = digital + own if domain == "digital_connectivity" else digital[:10] + own
    retriever = FusingRetriever(per_query)
    agent = TechnologyAgent(openai_client=None)
    agent.retriever = retriever

    evidence = agent.gather_evidence([])

    assert retriever.calls == [TechnologyAgent.max_evidence]
    assert {classify_domain(e) for e in evidence} == set(texts)
    assert sum(classify_domain(e) == "digital_connectivity" for e in evidence) <= 4


def test_own_search_uses_one_query_per_domain_and_balances_the_pool(tmp_path):
    papers = [_chunk(f"ai-{i}", "Large language model paper.", source="arxiv", category="science")
              for i in range(20)]
    retriever = MagicMock()
    retriever.search_many.return_value = papers + [SOLAR, SPACE]
    retriever.default_filters = None
    retriever.config.rerank_agent_searches = False
    agent = TechnologyAgent(openai_client=None)
    agent.retriever = retriever
    agent.recorder = RunRecorder(runs_dir=tmp_path)

    evidence = agent.gather_evidence([])

    assert len(TechnologyAgent.search_queries) == 6
    assert len(evidence) == TechnologyAgent.prompt_evidence
    assert {"sol-1", "spa-1"} <= {e.chunk_id for e in evidence}
    selection = agent.recorder.events_of("evidence_selection")[0]
    assert selection["pool"] == 22
