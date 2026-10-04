from __future__ import annotations

from pathlib import Path
from typing import Any

from agents.base_agent import BaseAgent, InsightObject


class HistorianAgent(BaseAgent):
    def __init__(self, openai_client: Any, prompt_path: str | Path | None = None):
        prompt_root = Path(__file__).resolve().parents[1] / "prompts"
        super().__init__(openai_client, prompt_path or prompt_root / "historian.md")

    def run(self, chunks: list[Any]) -> InsightObject:
        system_prompt = "You are the historian agent for a museum exhibition project."
        user_prompt = self._render_prompt(chunks, "historian", system_prompt)
        payload = self._call_llm(system_prompt, user_prompt)

        findings = payload.get("key_findings") or ["Historical themes identified from the corpus."]
        artifacts = payload.get("selected_artifacts") or [getattr(chunk, "chunk_id", getattr(chunk, "document_id", "")) for chunk in chunks[:1]]
        return InsightObject(
            agent="historian",
            perspective=str(payload.get("perspective", "Historical interpretation of the present era.")),
            key_findings=[str(item) for item in findings],
            selected_artifacts=[str(item) for item in artifacts if str(item)],
        )
