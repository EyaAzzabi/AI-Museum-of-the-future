"""
End-to-end smoke tests for the AI Museum pipeline.

Tests:
  1. ingest_processed on a 5-record fixture corpus
  2. Retriever.retrieve against fixture data
  3. run_pipeline with mock agents returns ExhibitionSynthesis within 120 s
  4. analyze_image with a Wikimedia URL

Requirements: 1.7, 3.1, 4.8, 6.1
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from data.ingest import IngestionReport, ingest_processed
from rag.chunking.chunker import ChunkConfig, Chunker, ChunkingStrategy
from rag.vector_store.retriever import RetrievalResult, Retriever
from agents.base_agent import InsightObject
from agents.curator import CuratorAgent, ExhibitionSynthesis, SectionObject
from agents.pipeline import run_pipeline
from agents.shared_context import SharedContext
from multimodal.analyze_image import VisualDescription, analyze_image


# ---------------------------------------------------------------------------
# Helpers — fixture records
# ---------------------------------------------------------------------------

def _make_fixture_records(n: int = 5) -> list[dict]:
    records = []
    for i in range(n):
        records.append({
            "id": str(uuid.uuid4()),
            "source": "fixture",
            "category": "art",
            "title": f"Fixture Record {i}",
            "text": (
                f"This is the body text for fixture record number {i}. "
                "It describes contemporary art in the Arab world with enough words "
                "to produce at least one chunk when the chunker runs."
            ),
            "url": f"https://example.com/fixture/{i}",
            "image_url": None,
            "date": None,
            "lang": "en",
            "tags": [],
            "raw_source": "fixture.json",
            "processed_on": "2026-10-04",
        })
    return records


# ---------------------------------------------------------------------------
# Test 1 — ingest_processed on a 5-record fixture corpus (Req 1.7)
# ---------------------------------------------------------------------------

def test_ingest_processed_fixture_corpus(tmp_path: Path) -> None:
    """ingest_processed on 5-record fixture corpus produces non-zero IngestionReport."""
    # Write fixture file
    fixture_file = tmp_path / "processed_fixture.json"
    records = _make_fixture_records(5)
    fixture_file.write_text(json.dumps(records), encoding="utf-8")

    chunker = Chunker(ChunkConfig(strategy=ChunkingStrategy.FIXED_SIZE, chunk_size=50))

    # Mock Supabase client — upsert_document returns a UUID string,
    # upsert_chunks returns count of items
    mock_sb = MagicMock()

    with (
        patch("data.ingest.upsert_document", return_value=str(uuid.uuid4())),
        patch("data.ingest.upsert_chunks", side_effect=lambda sb, chunks, doc_id: len(chunks)),
    ):
        report: IngestionReport = ingest_processed(tmp_path, chunker, mock_sb)

    assert isinstance(report, IngestionReport)
    assert report.documents_processed >= 1
    assert report.total_chunks_stored >= 1


# ---------------------------------------------------------------------------
# Test 2 — Retriever.retrieve against fixture data (Req 3.1)
# ---------------------------------------------------------------------------

def test_retriever_retrieve_returns_results() -> None:
    """Retriever.retrieve returns ≥1 result with similarity ≥ 0.70."""
    chunk_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())

    # Mock Supabase: rpc("match_chunks", ...) returns a row with similarity 0.82
    rpc_response = MagicMock()
    rpc_response.data = [
        {
            "chunk_id": chunk_id,
            "document_id": doc_id,
            "content": "Contemporary art in the Arab world explores post-colonial identity.",
            "metadata": {"category": "art"},
            "similarity": 0.82,
        }
    ]
    mock_sb = MagicMock()
    mock_sb.rpc.return_value.execute.return_value = rpc_response

    # Suppress _count_chunks warning path
    mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(count=200)

    # Mock OpenAI embeddings
    mock_oai = MagicMock()
    embedding_response = MagicMock()
    embedding_response.data = [MagicMock(embedding=[0.1] * 1536)]
    mock_oai.embeddings.create.return_value = embedding_response

    retriever = Retriever(mock_sb, mock_oai, match_count=5)
    results = retriever.retrieve("contemporary art Arab world")

    assert len(results) >= 1
    assert results[0].similarity >= 0.70


# ---------------------------------------------------------------------------
# Test 3 — run_pipeline with mock agents returns ExhibitionSynthesis (Req 4.8)
# ---------------------------------------------------------------------------

def test_run_pipeline_with_mock_agents() -> None:
    """run_pipeline with mocked specialist agents + curator returns ExhibitionSynthesis < 120 s."""
    dummy_chunks = [
        RetrievalResult(
            chunk_id=str(uuid.uuid4()),
            document_id=str(uuid.uuid4()),
            content=f"Chunk content {i} about the contemporary museum of the future.",
            metadata={"category": "art"},
            similarity=0.9,
        )
        for i in range(3)
    ]

    fake_insight = InsightObject(
        agent="test_agent",
        perspective="A test perspective on the topic.",
        key_findings=["Finding A", "Finding B"],
        selected_artifacts=["artifact-1", "artifact-2"],
    )

    fake_synthesis = ExhibitionSynthesis(
        exhibition_title="The Museum of Our Time",
        concept="An exhibition exploring the present as future history.",
        sections=[
            SectionObject(title=f"Section {i}", narrative=f"Narrative for section {i}.")
            for i in range(4)
        ],
        selected_items=["artifact-1", "artifact-2"],
    )

    start = time.time()

    with (
        patch("agents.pipeline._build_specialist_agents") as mock_build,
        patch.object(CuratorAgent, "run", return_value=fake_synthesis),
    ):
        # Each specialist agent mock returns fake_insight
        agent_mock = MagicMock()
        agent_mock.run.return_value = fake_insight
        mock_build.return_value = {
            "historian": agent_mock,
            "sociologist": agent_mock,
            "technology": agent_mock,
            "culture_art": agent_mock,
            "visual": agent_mock,
        }

        result = run_pipeline(dummy_chunks, openai_client=None, timeout_secs=120)

    elapsed = time.time() - start

    assert isinstance(result, ExhibitionSynthesis)
    assert result.exhibition_title  # non-empty string
    assert elapsed < 120.0


# ---------------------------------------------------------------------------
# Test 4 — analyze_image with Wikimedia URL (Req 6.1)
# ---------------------------------------------------------------------------

def test_analyze_image_wikimedia_url() -> None:
    """analyze_image with mocked HTTP + OpenAI returns a valid VisualDescription."""
    wikimedia_url = (
        "https://upload.wikimedia.org/wikipedia/commons/3/3f/Biharwe_entrance.jpg"
    )
    fake_bytes = b"\xff\xd8\xff" + b"\x00" * 64  # minimal fake JPEG-like bytes

    # Mock HTTP GET returning 200 with fake image bytes
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = fake_bytes

    # Build a mock OpenAI client
    mock_oai = MagicMock()

    # Vision completion returns structured text
    vision_content = (
        "Objects: arch, gate, stone wall; "
        "Scene: outdoor entrance of a historical site; "
        "Description: The image shows the entrance to Biharwe, a historical site in East Africa. "
        "Tags: history, architecture, Africa, heritage"
    )
    vision_choice = MagicMock()
    vision_choice.message.content = vision_content
    vision_completion = MagicMock()
    vision_completion.choices = [vision_choice]
    mock_oai.chat.completions.create.return_value = vision_completion

    # Embedding response for clip_embedding
    embed_data = MagicMock()
    embed_data.embedding = [0.05] * 1536
    embed_response = MagicMock()
    embed_response.data = [embed_data]
    mock_oai.embeddings.create.return_value = embed_response

    with patch("requests.get", return_value=mock_response):
        result = analyze_image(wikimedia_url, openai_client=mock_oai)

    assert isinstance(result, VisualDescription)
    assert result.description  # non-empty string
    assert isinstance(result.objects, list)
    assert isinstance(result.scene, str)
    assert isinstance(result.tags, list)
