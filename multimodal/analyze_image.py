"""Analyze an image (URL or local path) with a vision LLM and return a structured description.

Downloads send a descriptive User-Agent (Wikimedia answers 403 without one). Results are
cached under ``multimodal/cache/`` keyed by URL/path hash so the same image is not paid
for twice. The vision model is asked for JSON; label-style replies still parse as a fallback.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import mimetypes
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import requests

from agents.llm_config import build_llm_client, get_vision_model
from rag.vector_store.local_embeddings import EMBEDDING_MODEL, build_embedding_client

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "AIMuseumOfFuture/1.0 (academic project, Esprit 5DS; contact: ai-museum@example.com)",
}
CACHE_DIR = Path(__file__).resolve().parent / "cache"
VISION_PROMPT = (
    "Describe this image for a museum knowledge base. Reply with JSON only, no markdown:\n"
    '{"objects": ["..."], "scene": "...", "description": "one short paragraph of what is visible", '
    '"tags": ["..."], "caption_mismatch": false, "caption_mismatch_note": ""}\n'
    "If a caption was provided and the image clearly does not match it, set caption_mismatch true "
    "and explain briefly in caption_mismatch_note. Otherwise leave them false and empty."
)
UNAVAILABLE = "Image unavailable."


@dataclass
class VisualDescription:
    objects: list[str] = field(default_factory=list)
    scene: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    clip_embedding: list[float] | None = None
    caption_mismatch: bool = False
    caption_mismatch_note: str = ""


def _unavailable() -> VisualDescription:
    return VisualDescription(description=UNAVAILABLE)


def cache_key(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def cache_path(source: str, cache_dir: Path | None = None) -> Path:
    return (cache_dir or CACHE_DIR) / f"{cache_key(source)}.json"


def load_cache(source: str, cache_dir: Path | None = None) -> VisualDescription | None:
    path = cache_path(source, cache_dir)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not data.get("description"):
        return None
    return VisualDescription(
        objects=list(data.get("objects") or []),
        scene=str(data.get("scene") or ""),
        description=str(data["description"]),
        tags=list(data.get("tags") or []),
        clip_embedding=data.get("clip_embedding"),
        caption_mismatch=bool(data.get("caption_mismatch")),
        caption_mismatch_note=str(data.get("caption_mismatch_note") or ""),
    )


def save_cache(source: str, result: VisualDescription, cache_dir: Path | None = None) -> None:
    if result.description == UNAVAILABLE:
        return
    folder = cache_dir or CACHE_DIR
    try:
        folder.mkdir(parents=True, exist_ok=True)
        payload = asdict(result)
        cache_path(source, folder).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        logger.warning("vision cache write failed: %s", exc)


def _guess_mime(source: str, payload: bytes, content_type: str | None = None) -> str:
    if isinstance(content_type, str) and content_type.startswith("image/"):
        return content_type.split(";")[0].strip()
    guessed, _ = mimetypes.guess_type(source.split("?")[0])
    if guessed and guessed.startswith("image/"):
        return guessed
    if payload.startswith(b"\x89PNG"):
        return "image/png"
    if payload.startswith(b"GIF8"):
        return "image/gif"
    if payload.startswith(b"RIFF") and b"WEBP" in payload[:16]:
        return "image/webp"
    return "image/jpeg"


def _download(source: str) -> tuple[bytes, str] | None:
    try:
        if source.startswith("http://") or source.startswith("https://"):
            response = requests.get(source, timeout=15, headers=HEADERS)
            if response.status_code != 200 or not response.content:
                return None
            headers = getattr(response, "headers", None) or {}
            content_type = headers.get("content-type") if hasattr(headers, "get") else None
            return response.content, _guess_mime(source, response.content, content_type)
        path = Path(source)
        payload = path.read_bytes()
        if not payload:
            return None
        return payload, _guess_mime(source, payload)
    except (requests.RequestException, FileNotFoundError, OSError, ValueError):
        return None


def _extract_after(text: str, marker: str) -> str:
    lower = text.lower()
    idx = lower.find(marker)
    if idx == -1:
        return ""
    return text[idx + len(marker):]


def _parse_label_list(block: str) -> list[str]:
    stop = re.search(r"\n\s*(objects|scene|description|tags)\s*[:#*]", block, re.IGNORECASE)
    first = block[: stop.start()] if stop else block.split("\n\n")[0]
    parts = re.split(r"[\n;,]", first)
    return [p.strip(" -*\n:") for p in parts if p.strip(" -*\n:")][:10]


def parse_vision_text(label_text: str) -> VisualDescription:
    """Parse a vision-model reply (JSON preferred, label/Markdown fallback)."""
    text = (label_text or "").strip()
    if not text:
        return _unavailable()

    json_blob = text
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        json_blob = fenced.group(1)
    else:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            json_blob = text[start : end + 1]

    try:
        data = json.loads(json_blob)
        if isinstance(data, dict) and (data.get("description") or data.get("scene") or data.get("objects")):
            objects = data.get("objects") or []
            tags = data.get("tags") or []
            return VisualDescription(
                objects=[str(o).strip() for o in objects if str(o).strip()][:10] if isinstance(objects, list) else [],
                scene=str(data.get("scene") or "").strip(),
                description=str(data.get("description") or text).strip(),
                tags=[str(t).strip() for t in tags if str(t).strip()][:10] if isinstance(tags, list) else [],
                caption_mismatch=bool(data.get("caption_mismatch")),
                caption_mismatch_note=str(data.get("caption_mismatch_note") or "").strip(),
            )
    except (ValueError, TypeError):
        pass

    objects: list[str] = []
    after_objects = _extract_after(text, "objects")
    if after_objects:
        objects = _parse_label_list(after_objects.lstrip(":#* \n"))

    tags: list[str] = []
    after_tags = _extract_after(text, "tags")
    if after_tags:
        tags = _parse_label_list(after_tags.lstrip(":#* \n"))

    scene = ""
    after_scene = _extract_after(text, "scene")
    if after_scene:
        scene = after_scene.lstrip(":#* \n").split("\n\n")[0].split("\n")[0].strip(" -*")

    description = text
    after_desc = _extract_after(text, "description")
    if after_desc:
        description = after_desc.lstrip(":#* \n").split("\n\n")[0].strip(" -*") or text

    return VisualDescription(
        objects=objects,
        scene=scene,
        description=description or UNAVAILABLE,
        tags=tags,
    )


def summarize_for_evidence(result: VisualDescription, limit: int = 500) -> str:
    """One line suitable for ``vision:`` evidence and FTS enrichment."""
    description = str(getattr(result, "description", "") or "").strip()
    if not description or description == UNAVAILABLE:
        return ""
    parts = [description]
    if getattr(result, "caption_mismatch", False) and getattr(result, "caption_mismatch_note", ""):
        parts.append(f"(caption mismatch: {str(result.caption_mismatch_note).strip()})")
    return " ".join(parts)[:limit]


def analyze_image(
    source: str,
    openai_client: Any = None,
    embed_client: Any = None,
    *,
    caption: str | None = None,
    cache_dir: Path | None = None,
    use_cache: bool = True,
) -> VisualDescription:
    """Analyze an image from a URL or file path and return a structured description.

    ``openai_client`` is any OpenAI-compatible vision-capable chat client (Groq by default).
    ``caption`` is optional context for caption-vs-image mismatch detection.
    """
    if use_cache:
        cached = load_cache(source, cache_dir)
        if cached is not None:
            return cached

    downloaded = _download(source)
    if downloaded is None:
        return _unavailable()
    payload, mime = downloaded

    try:
        encoded = base64.b64encode(payload).decode("utf-8")
        if openai_client is None:
            try:
                openai_client = build_llm_client()
            except ValueError:
                return _unavailable()

        user_text = VISION_PROMPT
        if caption:
            user_text += f"\nCaption/title provided with the image: {caption[:300]}"

        completion = openai_client.chat.completions.create(
            model=get_vision_model(),
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}},
                    ],
                }
            ],
        )
        content = completion.choices[0].message.content or ""
        if not content:
            return _unavailable()

        result = parse_vision_text(content.strip())
        if result.description == UNAVAILABLE:
            return result

        embedding = None
        try:
            embedding_response = (embed_client or build_embedding_client()).embeddings.create(
                model=EMBEDDING_MODEL,
                input=result.description,
            )
            embedding = embedding_response.data[0].embedding
        except Exception:  # noqa: BLE001 - embedding is optional enrichment
            embedding = None

        result.clip_embedding = embedding
        if use_cache:
            save_cache(source, result, cache_dir)
        return result
    except Exception:  # noqa: BLE001 - a missing image never blocks the pipeline
        return _unavailable()
