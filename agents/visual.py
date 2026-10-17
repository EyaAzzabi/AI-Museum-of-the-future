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
        """Run the vision model on the first ``max_images`` evidence items that have an image.

        Prefers an existing ``vision_description`` on metadata or a disk cache hit before
        calling the model. Saves descriptions on the ``images`` run event and, when a
        Supabase client is available on the retriever, into document/chunk rows (C3).
        """
        from multimodal.analyze_image import analyze_image, load_cache, summarize_for_evidence
        from multimodal.store_vision import store_vision_for_chunk

        with_image = [i for i, e in enumerate(evidence) if (e.metadata or {}).get("image_url")][: self.max_images]
        if not with_image:
            return evidence

        supabase = getattr(getattr(self, "retriever", None), "supabase_client", None)

        def describe(index: int) -> tuple[int, str, Any]:
            item = evidence[index]
            meta = item.metadata or {}
            existing = (meta.get("vision_description") or "").strip()
            if existing and existing != "Image unavailable.":
                return index, existing[:500], None

            url = meta["image_url"]
            cached = load_cache(url)
            if cached is not None:
                text = summarize_for_evidence(cached)
                return index, text, cached if text else None

            if self.openai_client is None:
                return index, "", None
            try:
                caption = meta.get("title") or (item.content or "").split("\n")[0][:200]
                result = analyze_image(url, openai_client=self.openai_client, caption=caption)
                text = summarize_for_evidence(result)
                return index, text, result if text else None
            except Exception as exc:  # noqa: BLE001 - a missing image never blocks the agent
                logger.warning("[visual] image analysis failed: %s", exc)
                return index, "", None

        enriched = list(evidence)
        descriptions: dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=max(1, len(with_image))) as pool:
            for index, text, result in pool.map(describe, with_image):
                if not text:
                    continue
                item = enriched[index]
                descriptions[item.chunk_id] = text
                meta = dict(item.metadata or {})
                meta["vision_description"] = text
                if result is not None:
                    meta.setdefault("vision_objects", list(getattr(result, "objects", None) or []))
                    meta.setdefault("vision_tags", list(getattr(result, "tags", None) or []))
                    meta.setdefault("vision_scene", getattr(result, "scene", None) or "")
                    if getattr(result, "caption_mismatch", False):
                        meta["vision_caption_mismatch"] = True
                        meta["vision_caption_mismatch_note"] = getattr(result, "caption_mismatch_note", "") or ""
                enriched[index] = replace(item, content=f"{item.content}\nvision: {text}", metadata=meta)
                if supabase is not None and result is not None and item.document_id:
                    try:
                        store_vision_for_chunk(
                            supabase,
                            chunk_id=item.chunk_id,
                            document_id=item.document_id,
                            result=result,
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("[visual] store_vision skipped: %s", exc)

        self._record(
            "images",
            described=[evidence[i].chunk_id for i in with_image],
            descriptions=descriptions,
        )
        return enriched
