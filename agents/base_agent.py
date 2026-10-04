from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class InsightObject:
    agent: str
    perspective: str
    key_findings: list[str]
    selected_artifacts: list[str]


class BaseAgent(ABC):
    def __init__(self, openai_client: Any, prompt_path: str | Path):
        self.openai_client = openai_client
        self.prompt_path = Path(prompt_path)

    @abstractmethod
    def run(self, chunks: Any) -> InsightObject:
        raise NotImplementedError

    def _call_llm(self, system: str, user: str) -> dict:
        if self.openai_client is None:
            raise ValueError("openai_client is required for LLM calls.")

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except Exception as exc:  # pragma: no cover - bridge for tests
            raise ValueError(f"LLM call failed: {exc}") from exc

        if isinstance(response, dict):
            payload = response
        else:
            payload = getattr(response, "model_dump", lambda: response.__dict__)()
            if not isinstance(payload, dict):
                payload = getattr(response, "data", None)

        if hasattr(response, "choices") and response.choices:
            content = response.choices[0].message.content
            if content is None:
                raise ValueError("LLM returned empty content.")
            try:
                parsed = json.loads(content)
            except TypeError:
                parsed = content
            if isinstance(parsed, dict):
                return parsed
            raise ValueError("LLM response was not a JSON object.")

        if isinstance(payload, dict):
            return payload

        raise ValueError("Malformed LLM response.")

    def _load_prompt_template(self) -> str:
        if not self.prompt_path.exists():
            return ""
        return self.prompt_path.read_text(encoding="utf-8")

    def _render_prompt(self, chunks: Any, agent_name: str, system_prompt: str) -> str:
        template = self._load_prompt_template()
        chunk_text = "\n".join(
            getattr(chunk, "content", str(chunk)) for chunk in chunks
        ) if isinstance(chunks, list) else str(chunks)
        render = template.replace("{chunks}", chunk_text).replace("{agent}", agent_name).replace("{system}", system_prompt)
        return render
