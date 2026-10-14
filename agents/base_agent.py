from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agents.llm_config import get_model


@dataclass
class InsightObject:
    agent: str
    perspective: str
    key_findings: list[str]
    selected_artifacts: list[str]


import time

class BaseAgent(ABC):
    model_env_var = "LLM_MODEL"

    def __init__(self, openai_client: Any, prompt_path: str | Path):
        self.openai_client = openai_client
        self.prompt_path = Path(prompt_path)

    @property
    def model(self) -> str:
        return get_model(self.model_env_var)

    @abstractmethod
    def run(self, chunks: Any) -> InsightObject:
        raise NotImplementedError

    def _call_llm(self, system: str, user: str) -> dict:
        if self.openai_client is None:
            raise ValueError("openai_client is required for LLM calls.")

        models_to_try = [self.model]
        if "gemini" in self.model.lower():
            for alt in ["gemini-flash-lite-latest", "gemini-3.1-flash-lite", "gemini-flash-latest"]:
                if alt not in models_to_try:
                    models_to_try.append(alt)

        response = None
        last_exc = None
        for m in models_to_try:
            for attempt in range(3):
                try:
                    response = self.openai_client.chat.completions.create(
                        model=m,
                        response_format={"type": "json_object"},
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                    )
                    last_exc = None
                    break
                except Exception as exc:
                    last_exc = exc
                    err_msg = str(exc)
                    if any(code in err_msg for code in ["503", "429", "high demand", "UNAVAILABLE", "quota", "json_validate_failed"]):
                        time.sleep(1.0 * (attempt + 1))
                        continue
                    break
            if last_exc is None and response is not None:
                break

        if last_exc is not None:
            raise ValueError(f"LLM call failed: {last_exc}") from last_exc

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

    @staticmethod
    def _format_chunk(chunk: Any) -> str:
        """Prefix each chunk with its ID so the model can cite it in selected_artifacts."""
        content = getattr(chunk, "content", str(chunk))
        chunk_id = getattr(chunk, "chunk_id", "") or getattr(chunk, "document_id", "")
        return f"[{chunk_id}] {content}" if chunk_id else content

    def _render_prompt(self, chunks: Any, agent_name: str, system_prompt: str) -> str:
        template = self._load_prompt_template()
        chunk_text = "\n".join(
            self._format_chunk(chunk) for chunk in chunks
        ) if isinstance(chunks, list) else str(chunks)
        render = template.replace("{chunks}", chunk_text).replace("{agent}", agent_name).replace("{system}", system_prompt)
        return render
