from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import Any

from agents.base_agent import BaseAgent, InsightObject

logger = logging.getLogger(__name__)


class VisualAgent(BaseAgent):
    """Visual culture specialist: looks at the images behind the evidence, not only their captions."""

    name = "visual"
    focus = "Images, visual symbols and aesthetics that would show a future visitor what 2020-2026 looked like"
    system_prompt = (
        "You are the Visual Culture specialist of the AI Museum of the Future. "
        "You choose images and visual records that make the era tangible, and explain what they show. "
        "An evidence item may include a 'vision:' description produced by a vision model from the actual image; "
        "you may describe what that description reports, never colours or details it does not mention. "
        "Use only the supplied evidence. Return JSON only."
    )
    search_queries = (
        "photograph of protest demonstration crowd",
        "street art mural city life",
        "museum exhibition artwork painting",
        "landscape climate drought environment photograph",
    )
    search_categories = ("image",)

    def __init__(self, openai_client: Any, prompt_path: str | Path | None = None, max_images: int | None = None):
        prompt_root = Path(__file__).resolve().parents[1] / "prompts"
        super().__init__(openai_client, prompt_path or prompt_root / "visual.md")
        self.max_images = max_images if max_images is not None else int(os.getenv("VISUAL_MAX_IMAGES", "3"))

    def run(self, chunks: Any) -> InsightObject:
        evidence = self.gather_evidence(chunks)
        if not evidence:
            return self.abstain("no evidence")
        evidence = self.describe_images(evidence)
        user_prompt = self._render_prompt(evidence, self.name, self.system_prompt)
        payload = self._call_llm(self.system_prompt, user_prompt)
        return self.finalize(payload, evidence)

    def describe_images(self, evidence: list) -> list:
        """Run the vision model on the first ``max_images`` evidence items that have an image."""
        with_image = [i for i, e in enumerate(evidence) if (e.metadata or {}).get("image_url")][: self.max_images]
        if not with_image or self.openai_client is None:
            return evidence
        from multimodal.analyze_image import analyze_image

        def describe(index: int) -> tuple[int, str]:
            try:
                result = analyze_image(evidence[index].metadata["image_url"], openai_client=self.openai_client)
                text = (result.description or "").strip()
                return index, "" if text == "Image unavailable." else text
            except Exception as exc:  # noqa: BLE001 - a missing image never blocks the agent
                logger.warning("[visual] image analysis failed: %s", exc)
                return index, ""

        enriched = list(evidence)
        with ThreadPoolExecutor(max_workers=len(with_image)) as pool:
            for index, description in pool.map(describe, with_image):
                if description:
                    item = enriched[index]
                    enriched[index] = replace(item, content=f"{item.content}\nvision: {description[:500]}")
        self._record("images", described=[evidence[i].chunk_id for i in with_image])
        return enriched
