from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from agents.base_agent import BaseAgent, InsightObject

logger = logging.getLogger(__name__)

HISTORIAN_SYSTEM_PROMPT = (
    "You are the Socio-Historical Agent for the AI Museum of the Future. "
    "You examine contemporary records from the perspective of an archivist and historian "
    "living 100 years in the future (the 22nd century). "
    "Your mission is to identify pivotal contemporary events, contextualize their historical "
    "significance, and evaluate their long-term century-scale impact. "
    "Ground all findings strictly in the provided evidence and select only valid artifact IDs. "
    "IMPÉRATIF : Rédigez l'intégralité de vos réponses, analyses et conclusions en FRANÇAIS soigné et percutant."
)


def _get_chunk_identifier(chunk: Any) -> str:
    """Extract a canonical identifier from a chunk object or dict."""
    if hasattr(chunk, "chunk_id") and chunk.chunk_id:
        return str(chunk.chunk_id)
    if hasattr(chunk, "document_id") and chunk.document_id:
        return str(chunk.document_id)
    if isinstance(chunk, dict):
        cid = chunk.get("chunk_id") or chunk.get("document_id") or chunk.get("id")
        if cid:
            return str(cid)
    return ""


class HistorianAgent(BaseAgent):
    """Socio-Historical specialist agent for the AI Museum of the Future.

    Examines contemporary evidence through a 100-year retrospective lens to uncover:
      - Key events and societal turning points
      - Deep historical significance and context
      - Century-scale legacy and long-term societal transformation
    """

    def __init__(self, openai_client: Any, prompt_path: str | Path | None = None):
        prompt_root = Path(__file__).resolve().parents[1] / "prompts"
        super().__init__(openai_client, prompt_path or prompt_root / "historian.md")

    def _load_prompt_template(self) -> str:
        """Strip version documentation header before the first `---` divider."""
        template = super()._load_prompt_template()
        _, sep, body = template.partition("\n---\n")
        return body.lstrip() if sep else template

    def run(self, chunks: list[Any]) -> InsightObject:
        """Analyze evidence chunks and return a socio-historical InsightObject."""
        # 1. Collect valid input chunk IDs for strict anti-hallucination grounding
        valid_chunk_ids: list[str] = [
            cid for chunk in chunks if (cid := _get_chunk_identifier(chunk))
        ]
        valid_chunk_id_set = set(valid_chunk_ids)

        # 2. Render prompt and invoke LLM
        user_prompt = self._render_prompt(chunks, "historian", HISTORIAN_SYSTEM_PROMPT)
        payload = self._call_llm(HISTORIAN_SYSTEM_PROMPT, user_prompt)

        # 3. Extract and sanitize perspective
        raw_perspective = payload.get("perspective")
        if raw_perspective and str(raw_perspective).strip():
            perspective = str(raw_perspective).strip()
        else:
            perspective = "Historical interpretation of contemporary events and their century-scale trajectory."

        # 4. Extract and sanitize key findings
        raw_findings = payload.get("key_findings")
        if isinstance(raw_findings, list) and raw_findings:
            key_findings = [str(item).strip() for item in raw_findings if str(item).strip()]
        else:
            key_findings = [
                "Key contemporary milestones and turning points identified in the evidence.",
                "Historical significance contextualizing 21st-century societal transformations.",
                "Projected century-scale impact and legacy as viewed 100 years from now.",
            ]

        # 5. Extract, validate, and ground selected artifacts
        raw_artifacts = payload.get("selected_artifacts") or []
        if isinstance(raw_artifacts, list):
            # Only retain artifacts that genuinely exist in the input chunks
            grounded_artifacts = [
                str(item).strip()
                for item in raw_artifacts
                if str(item).strip() and str(item).strip() in valid_chunk_id_set
            ]
        else:
            grounded_artifacts = []

        # If LLM failed to select valid artifacts, fall back to top available chunk IDs
        if not grounded_artifacts and valid_chunk_ids:
            grounded_artifacts = valid_chunk_ids[: min(3, len(valid_chunk_ids))]

        return InsightObject(
            agent="historian",
            perspective=perspective,
            key_findings=key_findings,
            selected_artifacts=grounded_artifacts,
        )
