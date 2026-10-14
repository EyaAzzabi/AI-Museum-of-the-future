"""Fact-check the curator's narratives against the evidence they cite.

Each section narrative cites [chunk_id]s; the fact-checker receives the text
behind those IDs and returns, per section, whether every factual statement is
supported and which claims are not. The pipeline sends unsupported claims back
to the curator once (CuratorAgent.run(..., feedback=...)) and stores the final
verdicts in ExhibitionSynthesis.fact_check.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents.base_agent import BaseAgent, citations_in


class FactCheckAgent(BaseAgent):
    name = "fact_checker"
    system_prompt = (
        "You are a museum fact-checker. For each exhibition section you compare every factual "
        "statement with the evidence texts it cites, and you flag statements the evidence does not "
        "support. Interpretation clearly framed as interpretation is acceptable. Return JSON only."
    )

    def __init__(self, openai_client: Any, prompt_path: str | Path | None = None):
        prompt_root = Path(__file__).resolve().parents[1] / "prompts"
        super().__init__(openai_client, prompt_path or prompt_root / "fact_checker.md")

    def check(self, sections: list, evidence: dict[str, dict]) -> list[dict]:
        """Return one verdict per section: {"section", "title", "supported", "unsupported_claims"}."""
        if not sections:
            return []
        quoted = json.dumps([
            {
                "section": i,
                "title": section.title,
                "narrative": section.narrative,
                "cited_evidence": {
                    cid: (evidence.get(cid) or {}).get("content", "")[:600]
                    for cid in dict.fromkeys(citations_in(section.narrative) + list(section.artifacts))
                },
            }
            for i, section in enumerate(sections)
        ], ensure_ascii=False)
        payload = self._call_llm(self.system_prompt, self._render_prompt(quoted, self.name, self.system_prompt))
        verdicts = self._validate(payload, sections)
        self._record("fact_check", verdicts=verdicts)
        return verdicts

    @staticmethod
    def _validate(payload: Any, sections: list) -> list[dict]:
        by_index = {}
        for item in (payload.get("sections") if isinstance(payload, dict) else None) or []:
            if not isinstance(item, dict):
                continue
            try:
                index = int(item.get("section"))
            except (TypeError, ValueError):
                continue
            if not 0 <= index < len(sections):
                continue
            claims = [c.strip() for c in item.get("unsupported_claims") or [] if isinstance(c, str) and c.strip()]
            by_index[index] = {
                "section": index,
                "title": sections[index].title,
                "supported": bool(item.get("supported")) and not claims,
                "unsupported_claims": claims,
            }
        # A section the checker did not return is reported as unchecked, not as supported.
        return [
            by_index.get(i, {"section": i, "title": s.title, "supported": None, "unsupported_claims": []})
            for i, s in enumerate(sections)
        ]


def feedback_for(verdicts: list[dict]) -> str:
    """Curator feedback listing the unsupported claims, or "" when everything checked out."""
    problems = [v for v in verdicts if v.get("unsupported_claims")]
    if not problems:
        return ""
    lines = ["A fact-check of your previous exhibition found claims its cited evidence does not support.",
             "Rewrite the exhibition without them (keep or replace the sections), citing only what the evidence states:"]
    for v in problems:
        for claim in v["unsupported_claims"]:
            lines.append(f'- Section {v["section"] + 1} "{v["title"]}": {claim}')
    return "\n".join(lines)
