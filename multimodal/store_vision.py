"""Persist vision analysis on documents/chunks already in Supabase (C3).

Only updates rows the pipeline actually analyzed — never a full re-ingest.
Writes ``vision_*`` fields into ``documents.metadata`` and appends a ``Vision:``
line to the related chunk content so hybrid/full-text search can find what the
pixels show even when the caption is wrong.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from multimodal.analyze_image import VisualDescription, summarize_for_evidence

logger = logging.getLogger(__name__)

VISION_PREFIX = "Vision: "


def vision_metadata(result: VisualDescription) -> dict[str, Any]:
    return {
        "vision_description": result.description,
        "vision_objects": list(result.objects or []),
        "vision_tags": list(result.tags or []),
        "vision_scene": result.scene or "",
        "vision_caption_mismatch": bool(result.caption_mismatch),
        "vision_caption_mismatch_note": result.caption_mismatch_note or "",
        "vision_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def merge_vision_into_content(content: str, summary: str) -> str:
    """Replace or append a single ``Vision:`` line; leave other text intact."""
    summary = (summary or "").strip()
    if not summary:
        return content
    line = VISION_PREFIX + summary
    text = content or ""
    lines = text.splitlines()
    kept = [ln for ln in lines if not ln.startswith(VISION_PREFIX) and not ln.startswith("vision: ")]
    if kept and kept[-1].strip():
        return "\n".join(kept + [line])
    return (text.rstrip() + "\n" + line).strip() if text.strip() else line


def store_vision_for_chunk(
    supabase_client: Any,
    *,
    chunk_id: str,
    document_id: str,
    result: VisualDescription,
) -> bool:
    """Update one document's metadata and its chunk content. Returns True on success."""
    if not chunk_id or not document_id or result.description == "Image unavailable.":
        return False
    summary = summarize_for_evidence(result)
    if not summary:
        return False

    try:
        docs = (
            supabase_client.table("documents")
            .select("id,metadata")
            .eq("id", document_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not docs:
            return False
        meta = dict(docs[0].get("metadata") or {})
        meta.update(vision_metadata(result))
        supabase_client.table("documents").update({"metadata": meta}).eq("id", document_id).execute()

        chunks = (
            supabase_client.table("chunks")
            .select("id,content")
            .eq("id", chunk_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if chunks:
            new_content = merge_vision_into_content(str(chunks[0].get("content") or ""), summary)
            if new_content != chunks[0].get("content"):
                supabase_client.table("chunks").update({"content": new_content}).eq("id", chunk_id).execute()
        return True
    except Exception as exc:  # noqa: BLE001 - vision persistence must never break the agent
        logger.warning("store_vision failed for chunk %s: %s", chunk_id, exc)
        return False
