"""Science & Technology agent (Tasnim).

Same shared design as every specialist (agents/base_agent.py), plus three
technology-specific steps, each a fix for a failure seen in the live run of
2026-10-14 (see agents/TECHNOLOGY_README.md):

  1. Retrieval by domain   one search query per technology domain, a larger
                           candidate pool, then a domain-balanced selection
                           (agents/technology_tools.diversify): the evidence was
                           almost only arXiv AI papers.
  2. Typed evidence        each line says its domain and its kind (research
                           paper / news / archive), and the prompt gets a
                           coverage table: a research abstract was reported as
                           adoption, a single headline as a trend.
  3. Figure guardrail      a finding whose figures are not in the sources it
                           cites is dropped before the shared citation check.
  4. Finding budget        at most 5 findings, at most 2 of them interpretations:
                           the prompt asks for it but the model exceeded it in
                           2 of 3 runs with prompt v4; facts first, kept domain
                           by domain, interpretations resting on kept facts first.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from agents.base_agent import BaseAgent, InsightObject, as_result, resolve_citations
from agents.technology_tools import (
    DOMAIN_LABELS,
    classify_domain,
    coverage_summary,
    diversify,
    evidence_kind,
    grounding_text,
    ungrounded_numbers,
)

logger = logging.getLogger(__name__)


class TechnologyAgent(BaseAgent):
    """Science & technology specialist: innovations, digital life and their effect on society."""

    name = "technology"
    focus = "Technological and scientific change of 2020-2026 and how it reshaped work, society and daily life"
    system_prompt = (
        "You are the Science & Technology curator of the AI Museum of the Future, writing in 2126. "
        "You explain which technologies defined 2020-2026 and what they changed for people, "
        "using only the supplied evidence. You separate what a research paper proposes or measures "
        "from what was actually adopted, and what a source reports from your interpretation. "
        "Return JSON only."
    )
    # One query per domain of agents.technology_tools.TECH_DOMAINS.
    search_queries = (
        "artificial intelligence large language models impact on work and society",
        "internet mobile social media digital services startups adoption",
        "cybersecurity cyberattack data privacy surveillance",
        "renewable energy solar electricity grid climate technology",
        "vaccines biotechnology genetics health technology",
        "space exploration satellite launch scientific breakthrough",
    )
    # Exact terms for the keyword channel; French ones reach the Tunisian press of the corpus.
    search_keywords = (
        "artificial intelligence", "ChatGPT", "startup", "Startup Act", "solar", "digital",
        "cybersecurity", "vaccine", "satellite", "intelligence artificielle", "numérique", "électricité",
    )
    search_exclude_categories = ("statistics", "image")
    # search_many fuses all queries (RRF) and returns k results in total, not k per
    # query: k must be the whole candidate pool, or diversify() has nothing to balance.
    max_evidence = 36       # candidate pool kept by BaseAgent.gather_evidence
    search_k = max_evidence
    prompt_evidence = 14    # items sent to the model after diversify()
    max_findings = 5        # the prompt's budget, enforced in finalize()
    max_interpretations = 2

    def __init__(self, openai_client: Any, prompt_path: str | Path | None = None):
        prompt_root = Path(__file__).resolve().parents[1] / "prompts"
        super().__init__(openai_client, prompt_path or prompt_root / "technology.md")

    # ── Evidence ─────────────────────────────────────────────────────────────

    def gather_evidence(self, chunks: Any) -> list:
        pool = super().gather_evidence(chunks)
        evidence = diversify(pool, self.prompt_evidence)
        self._record("evidence_selection", pool=len(pool), kept=[e.chunk_id for e in evidence],
                     coverage=coverage_summary(evidence))
        return evidence

    @staticmethod
    def format_evidence(chunk: Any) -> str:
        """The shared line "[id] (year · source/category · title) text" followed by "<domain · kind>"."""
        result = as_result(chunk)
        return f"{BaseAgent.format_evidence(result)} <{DOMAIN_LABELS[classify_domain(result)]} · {evidence_kind(result)}>"

    def _render_prompt(self, chunks: Any, agent_name: str, system_prompt: str) -> str:
        prompt = super()._render_prompt(chunks, agent_name, system_prompt)
        coverage = coverage_summary(chunks) if isinstance(chunks, list) else ""
        return prompt.replace("{coverage}", coverage)

    # ── Output validation ────────────────────────────────────────────────────

    def finalize(self, payload: Any, evidence: list) -> InsightObject:
        if isinstance(payload, dict) and isinstance(payload.get("key_findings"), list):
            self._record("analysis", domains_covered=payload.get("domains_covered"),
                         evidence_gaps=payload.get("evidence_gaps"))
            findings = self._drop_ungrounded_figures(payload["key_findings"], evidence)
            payload = {**payload, "key_findings": self._enforce_budget(findings, evidence)}
        return super().finalize(payload, evidence)

    def _enforce_budget(self, findings: list, evidence: list) -> list:
        """Keep at most ``max_findings`` cited findings, at most ``max_interpretations`` of them.

        Only findings that will pass the shared citation check count, so an uncited
        one never takes a place. Facts come first (one place is kept for an
        interpretation when there is one) and are chosen round-robin over the domain
        of their first source; interpretations citing only kept facts come first.
        The model's order is preserved.
        """
        by_id = {e.chunk_id: e for e in (as_result(c) for c in evidence) if e.chunk_id}
        facts, interpretations, seen = [], [], set()
        for i, finding in enumerate(findings):
            text, refs, unknown = resolve_citations(finding.strip(), by_id)
            if not refs or unknown or text in seen:
                continue
            seen.add(text)
            if finding.strip().lower().startswith("interpretation:"):
                interpretations.append((i, refs))
            else:
                facts.append((i, refs))

        reserved = min(len(interpretations), 1)
        n_facts = min(len(facts), self.max_findings - reserved)
        n_interp = min(len(interpretations), self.max_interpretations, self.max_findings - n_facts)
        if n_facts == len(facts) and n_interp == len(interpretations):
            return findings

        by_domain: dict[str, list] = {}
        for item in facts:
            by_domain.setdefault(classify_domain(by_id[item[1][0]]), []).append(item)
        kept_facts: list = []
        while len(kept_facts) < n_facts:
            for queue in by_domain.values():
                if queue and len(kept_facts) < n_facts:
                    kept_facts.append(queue.pop(0))
        fact_refs = {r for _, refs in kept_facts for r in refs}
        interpretations.sort(key=lambda item: not set(item[1]) <= fact_refs)
        kept = {i for i, _ in kept_facts} | {i for i, _ in interpretations[:n_interp]}

        cited = {i for i, _ in facts} | {i for i, _ in interpretations}
        dropped = [findings[i] for i in sorted(cited - kept)]
        logger.info("[technology] %d finding(s) over the budget of %d dropped", len(dropped), self.max_findings)
        self._record("guardrail", rule="finding_budget", dropped=dropped,
                     kept_facts=len(kept_facts), kept_interpretations=n_interp)
        return [f for i, f in enumerate(findings) if i not in cited or i in kept]

    def _drop_ungrounded_figures(self, findings: list, evidence: list) -> list:
        """Drop findings stating a figure that none of their cited sources contains."""
        by_id = {e.chunk_id: e for e in (as_result(c) for c in evidence) if e.chunk_id}
        kept = []
        for finding in findings:
            if not isinstance(finding, str):
                continue
            _, refs, _ = resolve_citations(finding, by_id)
            missing = ungrounded_numbers(finding, [grounding_text(by_id[r]) for r in refs]) if refs else []
            if missing:
                logger.info("[technology] dropped a finding with figures not in its sources: %s", missing)
                self._record("guardrail", rule="ungrounded_figure", finding=finding, figures=missing)
                continue
            kept.append(finding)
        return kept
