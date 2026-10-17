"""Offline tests for multimodal/store_vision.py (document metadata + chunk Vision: line)."""
from __future__ import annotations

from types import SimpleNamespace

from multimodal.analyze_image import VisualDescription
from multimodal.store_vision import merge_vision_into_content, store_vision_for_chunk, vision_metadata


def test_merge_vision_replaces_previous_line():
    text = "Protest in Mexico City\nVision: old text"
    out = merge_vision_into_content(text, "Shirtless men on a road")
    assert out.count("Vision:") == 1
    assert "Shirtless men on a road" in out
    assert "old text" not in out


def test_vision_metadata_fields():
    result = VisualDescription(
        objects=["flag"],
        scene="street",
        description="A crowd with flags.",
        tags=["protest"],
        caption_mismatch=True,
        caption_mismatch_note="title mismatch",
    )
    meta = vision_metadata(result)
    assert meta["vision_description"] == "A crowd with flags."
    assert meta["vision_objects"] == ["flag"]
    assert meta["vision_caption_mismatch"] is True
    assert "vision_at" in meta


class _FakeQuery:
    def __init__(self, db, table):
        self.db, self.table, self.action, self.payload = db, table, "select", None

    def select(self, *_a):
        self.action = "select"
        return self

    def update(self, payload):
        self.action = "update"
        self.payload = payload
        return self

    def eq(self, *_a):
        return self

    def limit(self, _n):
        return self

    def execute(self):
        row = self.db[self.table]
        if self.action == "update" and self.payload:
            if "metadata" in self.payload:
                row["metadata"] = self.payload["metadata"]
            if "content" in self.payload:
                row["content"] = self.payload["content"]
        return SimpleNamespace(data=[dict(row)])


class _FakeSupabase:
    def __init__(self):
        self.db = {
            "documents": {"id": "doc-1", "metadata": {"image_url": "https://img/a.jpg"}},
            "chunks": {"id": "c1", "content": "Protest in Mexico City"},
        }

    def table(self, name):
        return _FakeQuery(self.db, name)


def test_store_vision_updates_document_and_chunk():
    client = _FakeSupabase()
    result = VisualDescription(
        description="Shirtless men in swim trunks; no protest.",
        objects=["men"],
        scene="road",
        tags=["street"],
        caption_mismatch=True,
        caption_mismatch_note="Caption says protest",
    )
    assert store_vision_for_chunk(client, chunk_id="c1", document_id="doc-1", result=result) is True
    assert "swim trunks" in client.db["documents"]["metadata"]["vision_description"]
    assert client.db["chunks"]["content"].startswith("Protest in Mexico City")
    assert "Vision: Shirtless men" in client.db["chunks"]["content"]


def test_store_vision_skips_unavailable():
    client = _FakeSupabase()
    before = dict(client.db["documents"]["metadata"])
    assert store_vision_for_chunk(
        client,
        chunk_id="c1",
        document_id="doc-1",
        result=VisualDescription(description="Image unavailable."),
    ) is False
    assert client.db["documents"]["metadata"] == before
