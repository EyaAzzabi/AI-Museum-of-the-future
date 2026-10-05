from __future__ import annotations

import base64
import os
from dataclasses import dataclass, field
from typing import Any

import requests
from openai import OpenAI


@dataclass
class VisualDescription:
    objects: list[str] = field(default_factory=list)
    scene: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    clip_embedding: list[float] | None = None


def analyze_image(source: str, openai_client: Any = None) -> VisualDescription:
    """Analyze an image from a URL or file path and return a structured description."""
    default_result = VisualDescription(
        objects=[],
        scene="",
        description="Image unavailable.",
        tags=[],
        clip_embedding=None,
    )

    try:
        if source.startswith("http://") or source.startswith("https://"):
            response = requests.get(source, timeout=10)
            if response.status_code != 200:
                return default_result
            payload = response.content
        else:
            with open(source, "rb") as fh:
                payload = fh.read()
    except (requests.RequestException, FileNotFoundError, OSError, ValueError):
        return default_result

    try:
        encoded = base64.b64encode(payload).decode("utf-8")
        if openai_client is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                return default_result
            openai_client = OpenAI(api_key=api_key)

        completion = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Describe the image in a short structured way: objects, scene, description, and thematic tags.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
                        },
                    ],
                }
            ],
        )
        content = completion.choices[0].message.content or ""
        if not content:
            return default_result

        label_text = content.strip()

        def _extract_after(text: str, marker: str) -> str:
            """Return text after the first case-insensitive occurrence of `marker`, or ''."""
            lower = text.lower()
            idx = lower.find(marker)
            if idx == -1:
                return ""
            return text[idx + len(marker):]

        # The model doesn't reliably use a flat "label: value" format (it often
        # replies with Markdown headers like "### Objects" instead) — these
        # extractions are best-effort and must never raise, since losing a
        # perfectly good description to a parsing hiccup is worse than a
        # slightly rougher objects/tags/scene split.
        objects = []
        after_objects = _extract_after(label_text, "objects")
        if after_objects:
            after_objects = after_objects.lstrip(":#* \n")
            objects = [p.strip(" -*\n") for p in after_objects.split("\n\n")[0].replace(";", "\n").split("\n") if p.strip(" -*\n")][:10]

        tags = []
        after_tags = _extract_after(label_text, "tags")
        if after_tags:
            after_tags = after_tags.lstrip(":#* \n")
            tags = [p.strip(" -*\n") for p in after_tags.replace("\n", ",").split(",") if p.strip(" -*\n")][:10]

        scene = ""
        after_scene = _extract_after(label_text, "scene")
        if after_scene:
            after_scene = after_scene.lstrip(":#* \n")
            scene = after_scene.split("\n\n")[0].split("\n")[0].strip(" -*")

        description = label_text or "Image unavailable."

        embedding = None
        try:
            embedding_response = openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=description,
            )
            embedding = embedding_response.data[0].embedding
        except Exception:
            embedding = None

        return VisualDescription(
            objects=objects or [],
            scene=scene or "",
            description=description,
            tags=tags or [],
            clip_embedding=embedding,
        )
    except Exception:
        return default_result
