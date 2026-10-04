from __future__ import annotations

from pathlib import Path
from typing import Any

from agents.base_agent import BaseAgent, InsightObject


class SociologistAgent(BaseAgent):
    def __init__(self, openai_client: Any, prompt_path: str | Path | None = None):
        prompt_root = Path(__file__).resolve().parents[1] / "prompts"
        super().__init__(openai_client, prompt_path or prompt_root / "sociologist.md")

    def run(self, chunks: list[Any]) -> InsightObject:
        system_prompt = "You are the sociologist agent for a museum exhibition project."
        user_prompt = self._render_prompt(chunks, "sociologist", system_prompt)
        payload = self._call_llm(system_prompt, user_prompt)

        findings = payload.get("key_findings") or ["Social patterns described in the corpus."]
        artifacts = payload.get("selected_artifacts") or [getattr(chunk, "chunk_id", getattr(chunk, "document_id", "")) for chunk in chunks[:1]]
        return InsightObject(
            agent="sociologist",
            perspective=str(payload.get("perspective", "Social life and human behaviour in context.")),
            key_findings=[str(item) for item in findings],
            selected_artifacts=[str(item) for item in artifacts if str(item)],
        )
