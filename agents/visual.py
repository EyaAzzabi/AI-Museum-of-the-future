from __future__ import annotations

from pathlib import Path
from typing import Any

from agents.base_agent import BaseAgent, InsightObject


class VisualAgent(BaseAgent):
    def __init__(self, openai_client: Any, prompt_path: str | Path | None = None):
        prompt_root = Path(__file__).resolve().parents[1] / "prompts"
        super().__init__(openai_client, prompt_path or prompt_root / "visual.md")

    def run(self, chunks: list[Any]) -> InsightObject:
        system_prompt = "You are the visual agent for a museum exhibition project."
        user_prompt = self._render_prompt(chunks, "visual", system_prompt)
        payload = self._call_llm(system_prompt, user_prompt)

        findings = payload.get("key_findings") or ["Visual mood and aesthetics informed the curation."]
        input_ids = [cid for chunk in chunks if (cid := getattr(chunk, "chunk_id", "") or getattr(chunk, "document_id", ""))]
        # Drop artifact IDs the model invented; fall back to the first input chunk
        artifacts = [str(a) for a in payload.get("selected_artifacts") or [] if str(a) in input_ids] or input_ids[:1]
        return InsightObject(
            agent="visual",
            perspective=str(payload.get("perspective", "Visual and aesthetic framing of the era.")),
            key_findings=[str(item) for item in findings],
            selected_artifacts=[str(item) for item in artifacts if str(item)],
        )
