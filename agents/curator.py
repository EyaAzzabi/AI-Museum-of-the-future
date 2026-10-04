from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agents.base_agent import BaseAgent, InsightObject
from agents.shared_context import SharedContext


@dataclass
class SectionObject:
    title: str
    narrative: str


@dataclass
class ExhibitionSynthesis:
    exhibition_title: str
    concept: str
    sections: list[SectionObject] = field(default_factory=list)
    selected_items: list[str] = field(default_factory=list)


class CuratorAgent(BaseAgent):
    def __init__(self, openai_client: Any, prompt_path: str | Path | None = None):
        prompt_root = Path(__file__).resolve().parents[1] / "prompts"
        super().__init__(openai_client, prompt_path or prompt_root / "curator.md")

    def run(self, shared_context: SharedContext) -> ExhibitionSynthesis:
        system_prompt = "You are curating a museum exhibition for the present age."
        quoted_insights = json.dumps({
            name: {
                "agent": insight.agent,
                "perspective": insight.perspective,
                "key_findings": insight.key_findings,
                "selected_artifacts": insight.selected_artifacts,
            }
            for name, insight in (shared_context.insights or {}).items()
        }, ensure_ascii=False)
        user_prompt = self._render_prompt(quoted_insights, "curator", system_prompt)
        payload = self._call_llm(system_prompt, user_prompt)

        if not isinstance(payload, dict):
            raise ValueError("Curator response was not a JSON object.")

        sections = payload.get("sections", [])
        normalized_sections = []
        for section in sections:
            if isinstance(section, dict):
                normalized_sections.append(
                    SectionObject(
                        title=str(section.get("title", "")).strip(),
                        narrative=str(section.get("narrative", "")).strip(),
                    )
                )

        selected_items = payload.get("selected_items") or shared_context.cross_references or []
        result = ExhibitionSynthesis(
            exhibition_title=str(payload.get("exhibition_title", "")).strip(),
            concept=str(payload.get("concept", "")).strip(),
            sections=normalized_sections,
            selected_items=[str(item) for item in selected_items],
        )

        if len(result.sections) < 4 or len(result.sections) > 6:
            raise ValueError("Curator output must include 4–6 sections.")
        if not result.exhibition_title or not result.concept:
            raise ValueError("Curator output is missing required fields.")
        return result
