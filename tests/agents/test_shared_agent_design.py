"""BaseAgent shared design: own search, evidence formatting, cache, recording, visual images."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from agents.base_agent import BaseAgent, citations_in
from agents.historian import HistorianAgent
from agents.run_log import RunRecorder, load_run
from agents.technology import TechnologyAgent
from agents.visual import VisualAgent
from rag.vector_store.retriever import RetrievalResult

INPUT = [RetrievalResult(chunk_id="in-1", document_id="d1", content="Input chunk.", metadata={})]
FOUND = [
    RetrievalResult(chunk_id="own-1", document_id="d2", content="Found by the agent.",
                    metadata={"year": 2023, "source": "gdelt", "category": "news", "title": "Headline"}),
    RetrievalResult(chunk_id="in-1", document_id="d1", content="Duplicate of the input.", metadata={}),
]


def _llm(payload: dict):
    client = MagicMock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))]
    )
    return client


def test_agent_adds_its_own_search_results_to_the_input():
    retriever = MagicMock()
    retriever.search_many.return_value = FOUND
    retriever.default_filters = None
    agent = TechnologyAgent(openai_client=None)
    agent.retriever = retriever

    evidence = agent.gather_evidence(INPUT)

    assert [e.chunk_id for e in evidence] == ["in-1", "own-1"]
    kwargs = retriever.search_many.call_args.kwargs
    assert retriever.search_many.call_args.args[0] == list(TechnologyAgent.search_queries)
    assert "statistics" in kwargs["filters"].exclude_categories
    assert kwargs["rerank_query"] == TechnologyAgent.focus


def test_own_search_failure_is_not_fatal():
    retriever = MagicMock()
    retriever.search_many.side_effect = RuntimeError("db down")
    agent = HistorianAgent(openai_client=None)
    agent.retriever = retriever
    assert [e.chunk_id for e in agent.gather_evidence(INPUT)] == ["in-1"]


def test_evidence_line_shows_id_then_provenance():
    line = BaseAgent.format_evidence(FOUND[0])
    assert line.startswith("[own-1] (2023 · gdelt/news · Headline) Found by the agent.")


def test_citations_accept_lists():
    assert citations_in("A [x] and [y, z; w].") == ["x", "y", "z", "w"]


def test_llm_cache_answers_identical_prompts_from_disk(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_CACHE_DIR", str(tmp_path))
    client = _llm({"perspective": "p", "key_findings": ["f [in-1]"]})
    agent = HistorianAgent(client)
    first = agent._call_llm("s", "u")
    second = agent._call_llm("s", "u")
    assert first == second
    assert client.chat.completions.create.call_count == 1


def test_recorder_captures_prompts_evidence_and_insight(tmp_path):
    recorder = RunRecorder(runs_dir=tmp_path, run_id="t1")
    agent = HistorianAgent(_llm({"perspective": "p", "key_findings": ["Fait [in-1]."]}))
    agent.recorder = recorder
    agent.run(INPUT)
    path = recorder.save()

    run = load_run(path.parent)
    kinds = [e["kind"] for e in run["events"]]
    assert kinds == ["evidence", "llm_call", "insight"]
    assert run["events"][1]["user"].count("[in-1]") == 1
    assert run["events"][2]["insight"]["selected_artifacts"] == ["in-1"]


def test_visual_agent_describes_images_with_the_vision_model():
    chunk = RetrievalResult(chunk_id="img-1", document_id="d", content="Photo caption.",
                            metadata={"image_url": "https://example.org/a.jpg", "category": "image"})
    client = _llm({"perspective": "p", "key_findings": ["A crowd in a square [img-1]."]})
    agent = VisualAgent(client, max_images=2)
    with patch("multimodal.analyze_image.analyze_image",
               return_value=SimpleNamespace(description="A crowd holding flags in a square.")) as vision:
        result = agent.run([chunk])
    vision.assert_called_once()
    prompt = client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
    assert "vision: A crowd holding flags in a square." in prompt
    assert result.selected_artifacts == ["img-1"]


def test_visual_agent_without_images_skips_vision():
    client = _llm({"perspective": "p", "key_findings": ["Caption only [in-1]."]})
    with patch("multimodal.analyze_image.analyze_image") as vision:
        VisualAgent(client).run(INPUT)
    vision.assert_not_called()


def test_shortened_uuid_citations_resolve_to_the_full_id():
    from agents.base_agent import resolve_citations

    ids = ["71108630-9f1e-4c2a-8a55-1b2c3d4e5f60", "71108631-0000-0000-0000-000000000000", "e84ceff7-6a5b-4c1d"]
    text, refs, unknown = resolve_citations("Growth [71108630] and access [e84ceff7, 7110].", ids)
    assert text == "Growth [71108630-9f1e-4c2a-8a55-1b2c3d4e5f60] and access [e84ceff7-6a5b-4c1d, 7110]."
    assert refs == [ids[0], ids[2]]
    assert unknown == ["7110"]   # too short to be unambiguous


def test_agent_keeps_findings_citing_an_id_prefix():
    chunk = RetrievalResult(chunk_id="71108630-9f1e-4c2a-8a55-1b2c3d4e5f60", document_id="d", content="GDP grew 2.1%.")
    agent = HistorianAgent(_llm({"perspective": "p", "key_findings": ["La croissance [71108630]."]}))
    result = agent.run([chunk])
    assert result.key_findings == ["La croissance [71108630-9f1e-4c2a-8a55-1b2c3d4e5f60]."]
    assert result.selected_artifacts == [chunk.chunk_id]


def test_unparseable_responses_are_recorded(tmp_path):
    client = MagicMock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='["not", "an", "object"]'))]
    )
    agent = HistorianAgent(client)
    agent.recorder = RunRecorder(runs_dir=tmp_path)
    try:
        agent._call_llm("s", "u")
    except ValueError:
        pass
    assert agent.recorder.events_of("llm_call")[0]["error"] == "LLM response was not a JSON object."
