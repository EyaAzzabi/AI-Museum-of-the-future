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
        objects = []
        if "objects" in label_text.lower():
            objects = [part.strip() for part in label_text.split("objects:", 1)[1].split(";") if part.strip()][:10]
        tags = []
        if "tags" in label_text.lower():
            _, after = label_text.lower().split("tags:", 1) if "tags:" in label_text.lower() else (None, "")
            tags = [part.strip() for part in after.replace("\n", " ").split(",") if part.strip()][:10]

        description = label_text
        scene = ""
        if "scene" in label_text.lower():
            scene = label_text.split("scene:", 1)[1].split("\n")[0].strip() if "scene:" in label_text.lower() else ""

        description = description or "Image unavailable."
        if description == "":
            description = "Image unavailable."

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
