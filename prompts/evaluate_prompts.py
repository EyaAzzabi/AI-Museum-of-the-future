from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class EvalRecord:
    agent: str
    prompt_version: str
    model: str
    input_tokens: int
    schema_valid: bool
    fail_reason: str | None
    raw_excerpt: str | None


def _load_prompt(agent: str) -> str:
    prompt_file = Path(__file__).resolve().parent / f"{agent}.md"
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found for agent '{agent}'.")
    return prompt_file.read_text(encoding="utf-8")


def evaluate_all(openai_client: Any, test_cases: list[dict]) -> list[EvalRecord]:
    records: list[EvalRecord] = []
    for case in test_cases:
        agent = str(case.get("agent", "unknown"))
        chunks = case.get("chunks", [])
        chunks_text = "\n".join(str(getattr(chunk, "content", chunk)) for chunk in chunks)
        prompt_text = _load_prompt(agent)
        rendered = prompt_text.replace("{chunks}", chunks_text).replace("{system}", "Curate the present for the future.")
        rendered = rendered.replace("{agent}", agent)

        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": "Evaluate prompt compliance."},
                    {"role": "user", "content": rendered},
                ],
            )
            content = response.choices[0].message.content
            payload = json.loads(content)
            schema_valid = isinstance(payload, dict)
            fail_reason = None if schema_valid else "Response was not a JSON object."
            raw_excerpt = (content[:200] if content else None)
        except Exception as exc:  # pragma: no cover - defensive behavior
            payload = {}
            schema_valid = False
            fail_reason = str(exc)
            raw_excerpt = str(exc)[:200]

        version = "unknown"
        if "## v" in prompt_text:
            version_line = prompt_text.splitlines()[0]
            version = version_line.replace("## ", "").strip()

        records.append(
            EvalRecord(
                agent=agent,
                prompt_version=version,
                model="gpt-4o-mini",
                input_tokens=max(0, len(chunks_text.split())),
                schema_valid=schema_valid,
                fail_reason=fail_reason,
                raw_excerpt=raw_excerpt,
            )
        )
    return records
