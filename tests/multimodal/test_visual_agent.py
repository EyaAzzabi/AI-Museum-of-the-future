"""Visual agent: records vision descriptions and reuses stored/cached text."""
from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

from agents.visual import VisualAgent
from multimodal.analyze_image import VisualDescription, save_cache
from rag.vector_store.retriever import RetrievalResult


@pytest.fixture
def agent():
    return VisualAgent(openai_client=object(), max_images=2)


@pytest.fixture
def vision_module(tmp_path, monkeypatch):
    module = importlib.import_module("multimodal.analyze_image")
    monkeypatch.setattr(module, "CACHE_DIR", tmp_path)
    return module


def test_visual_agent_records_descriptions(agent, vision_module, monkeypatch):
    recorded = []

    def analyze(url, openai_client=None, caption=None, **_kw):
        return VisualDescription(description=f"seen {url}", objects=["x"], scene="s", tags=["t"])

    monkeypatch.setattr(vision_module, "analyze_image", analyze)
    agent.recorder = SimpleNamespace(record=lambda kind, **data: recorded.append((kind, data)))
    items = [
        RetrievalResult(chunk_id="a", document_id="d1", content="photo", metadata={"image_url": "https://img/a.jpg"}),
        RetrievalResult(chunk_id="b", document_id="d2", content="text", metadata={}),
    ]
    enriched = agent.describe_images(items)
    assert enriched[0].content.endswith("vision: seen https://img/a.jpg")
    assert recorded == [
        ("images", {"agent": "visual", "described": ["a"], "descriptions": {"a": "seen https://img/a.jpg"}})
    ]


def test_visual_agent_reuses_metadata_vision_without_llm(agent, vision_module, monkeypatch):
    called = []

    def boom(*_a, **_k):
        called.append(1)
        raise AssertionError("analyze_image must not be called")

    monkeypatch.setattr(vision_module, "analyze_image", boom)
    agent.recorder = SimpleNamespace(record=lambda kind, **data: None)
    items = [
        RetrievalResult(
            chunk_id="a",
            document_id="d1",
            content="caption",
            metadata={"image_url": "https://img/a.jpg", "vision_description": "Already seen on the road."},
        )
    ]
    enriched = agent.describe_images(items)
    assert called == []
    assert "vision: Already seen on the road." in enriched[0].content


def test_visual_agent_reuses_disk_cache(agent, vision_module, tmp_path, monkeypatch):
    save_cache(
        "https://img/a.jpg",
        VisualDescription(description="From cache: mural on a wall."),
        tmp_path,
    )
    monkeypatch.setattr(
        vision_module,
        "analyze_image",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("no LLM")),
    )
    agent.recorder = SimpleNamespace(record=lambda kind, **data: None)
    items = [
        RetrievalResult(
            chunk_id="a",
            document_id="d1",
            content="mural",
            metadata={"image_url": "https://img/a.jpg"},
        )
    ]
    enriched = agent.describe_images(items)
    assert "From cache: mural on a wall." in enriched[0].content
