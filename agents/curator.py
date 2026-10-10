from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agents.base_agent import BaseAgent, InsightObject
from agents.shared_context import SharedContext

MIN_SECTIONS = 4
MAX_SECTIONS = 6
MAX_ATTEMPTS = 2

SYSTEM_PROMPT = (
    "You are the chief curator of a museum of the present age. You write for a general "
    "museum audience: vivid, precise and grounded in the evidence you are given. "
    "You never invent artifacts or facts that are absent from the insights."
)


class CuratorValidationError(ValueError):
    """The curator's output was well-formed JSON but broke a content rule."""


@dataclass
class SectionObject:
    title: str
    narrative: str
    artifacts: list[str] = field(default_factory=list)


@dataclass
class ExhibitionSynthesis:
    exhibition_title: str
    concept: str
    sections: list[SectionObject] = field(default_factory=list)
    selected_items: list[str] = field(default_factory=list)
    missing_perspectives: list[str] = field(default_factory=list)


def _is_empty(insight: Any) -> bool:
    return not (
        isinstance(insight, InsightObject)
        and (insight.perspective or insight.key_findings or insight.selected_artifacts)
    )


class CuratorAgent(BaseAgent):
    model_env_var = "CURATOR_MODEL"

    def __init__(self, openai_client: Any, prompt_path: str | Path | None = None):
        prompt_root = Path(__file__).resolve().parents[1] / "prompts"
        super().__init__(openai_client, prompt_path or prompt_root / "curator.md")

    def _load_prompt_template(self) -> str:
        """Drop the version-history header (everything before the first `---` line)."""
        template = super()._load_prompt_template()
        head, sep, body = template.partition("\n---\n")
        return body.lstrip() if sep else template

    def run(self, shared_context: SharedContext) -> ExhibitionSynthesis:
        insights = shared_context.insights or {}
        missing = sorted(name for name, insight in insights.items() if _is_empty(insight))
        present = {name: insight for name, insight in insights.items() if name not in missing}
        known_artifacts = {a for insight in present.values() for a in insight.selected_artifacts}

        quoted_insights = json.dumps(
            {
                "perspectives": {
                    name: {
                        "agent": insight.agent,
                        "perspective": insight.perspective,
                        "key_findings": insight.key_findings,
                        "selected_artifacts": insight.selected_artifacts,
                    }
                    for name, insight in present.items()
                },
                "cross_references": shared_context.cross_references or [],
                "unavailable_perspectives": missing,
            },
            ensure_ascii=False,
        )
        base_prompt = self._render_prompt(quoted_insights, "curator", SYSTEM_PROMPT)

        feedback = ""
        last_error: CuratorValidationError | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            payload = self._call_llm(SYSTEM_PROMPT, base_prompt + feedback)
            try:
                return self._build_result(payload, shared_context, known_artifacts, missing)
            except CuratorValidationError as exc:
                last_error = exc
                logging.warning("Curator attempt %d/%d rejected: %s", attempt, MAX_ATTEMPTS, exc)
                feedback = (
                    f"\n\nYour previous answer was rejected: {exc}\n"
                    "Return the corrected JSON object only."
                )
        raise last_error  # type: ignore[misc]

    @staticmethod
    def _build_result(
        payload: Any,
        shared_context: SharedContext,
        known_artifacts: set[str],
        missing: list[str],
    ) -> ExhibitionSynthesis:
        if not isinstance(payload, dict):
            raise CuratorValidationError("Curator response was not a JSON object.")

        sections = []
        for section in payload.get("sections") or []:
            if not isinstance(section, dict):
                continue
            artifacts = [str(a) for a in section.get("artifacts") or []]
            if known_artifacts:
                artifacts = [a for a in artifacts if a in known_artifacts]
            sections.append(
                SectionObject(
                    title=str(section.get("title", "")).strip(),
                    narrative=str(section.get("narrative", "")).strip(),
                    artifacts=artifacts,
                )
            )

        if not MIN_SECTIONS <= len(sections) <= MAX_SECTIONS:
            raise CuratorValidationError(
                f"sections must contain {MIN_SECTIONS}-{MAX_SECTIONS} items, got {len(sections)}."
            )
        if any(not s.title or not s.narrative for s in sections):
            raise CuratorValidationError("every section needs a non-empty title and narrative.")

        title = str(payload.get("exhibition_title", "")).strip()
        concept = str(payload.get("concept", "")).strip()
        if not title or not concept:
            raise CuratorValidationError("exhibition_title and concept are required.")

        # Only keep artifacts the specialists actually selected, so the model cannot invent IDs.
        selected = [str(i) for i in payload.get("selected_items") or []]
        if known_artifacts:
            selected = [i for i in selected if i in known_artifacts]
            selected = selected or list(shared_context.cross_references or []) or sorted(known_artifacts)
        else:
            selected = selected or list(shared_context.cross_references or [])

        return ExhibitionSynthesis(
            exhibition_title=title,
            concept=concept,
            sections=sections,
            selected_items=selected,
            missing_perspectives=missing,
        )
