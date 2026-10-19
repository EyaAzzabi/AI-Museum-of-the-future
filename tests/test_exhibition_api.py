"""Offline tests for exhibition_api.py and the Exposition page."""
from __future__ import annotations

import json
import threading

import pytest
from flask import Flask

import exhibition_api
from agents.run_log import RunRecorder
from exhibition_api import create_exhibition_blueprint, exhibition_view

EVIDENCE = {
    "c1": {"content": "Tunisia opens a solar plant.", "title": "Solar plant", "source": "gdelt",
           "category": "news", "year": 2024, "url": "https://example.org/solar"},
    "c2": {"content": "Mosaic restored in Sousse.", "title": "Mosaic", "source": "wikipedia",
           "category": "culture", "year": 2022, "url": "https://example.org/mosaic"},
}
EXHIBITION = {
    "exhibition_title": "Tunisia Builds", "concept": "How Tunisia changed.",
    "sections": [
        {"title": "Energy", "narrative": "A solar plant opened [c1].", "artifacts": ["c1"]},
        {"title": "Heritage", "narrative": "A mosaic was restored [c2].", "artifacts": ["c2", "unknown"]},
    ],
    "selected_items": ["c1", "c2"], "missing_perspectives": ["sociologist"],
    "review": {"agreements": [], "tensions": [], "weak_findings": []},
    "fact_check": [{"section": 0, "title": "Energy", "supported": True, "unsupported_claims": []},
                   {"section": 1, "title": "Heritage", "supported": False, "unsupported_claims": ["restored"]}],
}


def test_default_image_lookup_skips_demo_chunk_ids():
    assert exhibition_api._default_image_lookup(["tn-politique-01", "tn-migration-02"]) == {}


def record_pipeline(recorder: RunRecorder, complete: bool = True) -> None:
    recorder.record("insight", agent="technology", insight={
        "agent": "technology", "perspective": "Energy grows.", "key_findings": ["Solar plant [c1]"],
        "selected_artifacts": ["c1"], "evidence": {"c1": EVIDENCE["c1"]}}, dropped_findings=[])
    recorder.record("insight", agent="culture_art", insight={
        "agent": "culture_art", "perspective": "Heritage.", "key_findings": ["Mosaic [c2]"],
        "selected_artifacts": ["c2"], "evidence": {"c2": EVIDENCE["c2"]}}, dropped_findings=[])
    recorder.record("abstain", agent="sociologist", reason="No evidence.")
    recorder.record("agent_error", agent="visual", error="RateLimitError('429 org_secret')")
    recorder.record("review", agent="reviewer", review={
        "agreements": [{"agents": ["technology", "culture_art"], "point": "change"}],
        "tensions": [], "weak_findings": []})
    if complete:
        recorder.record("result", exhibition=EXHIBITION)
    recorder.save()


@pytest.fixture
def make_client(tmp_path, monkeypatch):
    monkeypatch.delenv("EXHIBITION_API_TOKEN", raising=False)
    monkeypatch.setattr("agents.llm_config.get_model", lambda *a, **k: "test-model")

    def make(runner=None, image_lookup=None, describer=None):
        calls = []

        def default(params, recorder):
            calls.append(params)
            record_pipeline(recorder)

        def no_vision(_url):
            raise AssertionError("the vision model must not be called")

        app = Flask(__name__)
        app.register_blueprint(create_exhibition_blueprint(
            runner=runner or default, runs_dir=tmp_path,
            image_lookup=image_lookup, describer=describer or no_vision))
        client = app.test_client()
        client.calls = calls
        return client

    return make


def save_run(tmp_path, run_id, complete=True, config=None):
    recorder = RunRecorder(runs_dir=tmp_path, run_id=run_id, config=config or {"country": "Tunisia"})
    record_pipeline(recorder, complete=complete)
    return recorder


class TestExhibitionView:
    def test_sections_carry_artifacts_images_and_verdicts(self, tmp_path):
        run = save_run(tmp_path, "20261014-100000-aaaaaa").to_dict()
        view = exhibition_view(run, image_lookup=lambda ids: {"c2": "https://img/mosaic.jpg"})
        assert view["status"] == "done"
        energy, heritage = view["exhibition"]["sections"]
        assert energy["artifacts"][0]["title"] == "Solar plant"
        assert energy["artifacts"][0]["image_url"] is None
        assert heritage["artifacts"][0]["image_url"] == "https://img/mosaic.jpg"
        assert heritage["artifacts"][1]["id"] == "unknown"
        assert energy["fact_check"]["supported"] is True
        assert "org_secret" not in json.dumps(view)

    def test_agent_status_and_review(self, tmp_path):
        view = exhibition_view(save_run(tmp_path, "20261014-100000-aaaaaa").to_dict())
        assert view["insights"]["technology"]["status"] == "ok"
        assert view["insights"]["sociologist"]["status"] == "abstained"
        assert view["insights"]["visual"]["status"] == "error"
        assert view["review"]["agreements"][0]["point"] == "change"

    def test_partial_run_exposes_agent_selected_articles_and_images(self, tmp_path):
        run = save_run(tmp_path, "20261014-100000-aaaaaa", complete=False).to_dict()
        view = exhibition_view(run, image_lookup=lambda ids: {"c1": "https://img/solar.jpg"})
        assert view["status"] == "failed"
        assert view["exhibition"] is None
        assert "provider rate limit" in view["error"]
        assert "org_secret" not in view["error"]
        assert view["insights"]["technology"]["selected_artifacts"] == ["c1"]
        assert view["artifacts"][0]["id"] == "c1"
        assert view["artifacts"][0]["image_url"] == "https://img/solar.jpg"


class TestStartRun:
    def test_wait_returns_the_exhibition(self, make_client):
        body = make_client().post("/api/exhibition", json={"wait": True}).get_json()
        assert body["status"] == "done" and body["exhibition"]["title"] == "Tunisia Builds"

    def test_background_run_then_poll(self, make_client):
        client = make_client()
        started = client.post("/api/exhibition", json={}).get_json()
        assert started["status"] == "running"
        run_id = started["run_id"]
        for _ in range(50):
            body = client.get(f"/api/exhibition/{run_id}").get_json()
            if body.get("status") != "running":
                break
            threading.Event().wait(0.05)
        assert body["exhibition"]["title"] == "Tunisia Builds"

    def test_rejects_bad_parameters(self, make_client):
        assert make_client().post("/api/exhibition", json={"timeout": 5}).status_code == 400
        assert make_client().post("/api/exhibition", json={"chunks": ["invalid"]}).status_code == 400
        assert make_client().post("/api/exhibition", json={"use_rag": False}).status_code == 400
        assert make_client().post("/api/exhibition", json={"query": "q" * 301}).status_code == 400

    def test_shared_chunks_and_rag_setting_are_passed_to_runner(self, make_client):
        client = make_client()
        chunk = {"chunk_id": "preset-1", "content": "A documented event.", "metadata": {"country": "Tunisia"}}
        response = client.post("/api/exhibition", json={
            "query": "An exhibition", "chunks": [chunk], "use_rag": False, "wait": True,
        })
        assert response.status_code == 200
        assert client.calls[0]["chunks"] == [{
            **chunk, "document_id": "",
        }]
        assert client.calls[0]["use_rag"] is False
        assert client.calls[0]["query"] == "An exhibition"

    def test_default_runner_passes_shared_chunks_without_initializing_rag(self, monkeypatch):
        from types import SimpleNamespace

        from rag.vector_store.retriever import RetrievalResult

        import agents.pipeline

        client = SimpleNamespace(chat=SimpleNamespace(completions=object()))
        captured = {}
        monkeypatch.setattr("agents.llm_config.build_llm_client", lambda: client)
        monkeypatch.setattr(
            agents.pipeline,
            "run_pipeline",
            lambda chunks, _client, **kwargs: captured.update(chunks=chunks, retriever=kwargs["retriever"]),
        )
        exhibition_api._default_runner({
            "from_run": None,
            "chunks": [{
                "chunk_id": "preset-1",
                "document_id": "doc-1",
                "content": "A documented event.",
                "metadata": {"country": "Tunisia"},
            }],
            "use_rag": False,
            "query": "An exhibition",
            "country": "Tunisia",
            "year_from": 2020,
            "year_to": 2026,
            "timeout": 400,
            "review": True,
            "fact_check": True,
        }, SimpleNamespace(cancelled=threading.Event()))
        assert captured["chunks"] == [RetrievalResult(
            chunk_id="preset-1", document_id="doc-1", content="A documented event.",
            metadata={"country": "Tunisia"},
        )]
        assert captured["retriever"] is None

    def test_token_required_when_set(self, make_client, monkeypatch):
        monkeypatch.setenv("EXHIBITION_API_TOKEN", "secret")
        assert make_client().post("/api/exhibition", json={}).status_code == 401

    def test_from_run_must_exist(self, make_client):
        assert make_client().post("/api/exhibition", json={"from_run": "20261014-100000-ffffff"}).status_code == 404

    def test_from_run_is_passed_to_the_runner(self, make_client, tmp_path):
        save_run(tmp_path, "20261014-090000-bbbbbb")
        client = make_client()
        client.post("/api/exhibition", json={"from_run": "20261014-090000-bbbbbb", "wait": True})
        assert client.calls[0]["from_run"] == "20261014-090000-bbbbbb"


class TestCancel:
    def test_cancel_stops_at_next_step_and_keeps_finished_steps(self, make_client, tmp_path):
        after_first = threading.Event()
        may_continue = threading.Event()

        def runner(params, recorder):
            recorder.record("insight", agent="technology", insight={
                "agent": "technology", "perspective": "ok", "key_findings": ["x [c1]"],
                "selected_artifacts": ["c1"], "evidence": {"c1": EVIDENCE["c1"]}}, dropped_findings=[])
            after_first.set()
            may_continue.wait(2)
            recorder.record("insight", agent="historian", insight={
                "agent": "historian", "perspective": "late", "key_findings": [],
                "selected_artifacts": [], "evidence": {}}, dropped_findings=[])

        client = make_client(runner=runner)
        run_id = client.post("/api/exhibition", json={}).get_json()["run_id"]
        assert after_first.wait(2)
        assert client.post(f"/api/exhibition/{run_id}/cancel").status_code == 202
        may_continue.set()
        for _ in range(50):
            body = client.get(f"/api/exhibition/{run_id}").get_json()
            if body.get("status") != "running":
                break
            threading.Event().wait(0.05)
        assert body.get("cancelled") or body.get("error")
        assert "technology" in (body.get("insights") or {})


class TestReadRuns:
    def test_latest_and_list(self, make_client, tmp_path):
        save_run(tmp_path, "20261014-100000-aaaaaa")
        save_run(tmp_path, "20261014-120000-cccccc", complete=False)
        client = make_client()
        assert client.get("/api/exhibition/latest").get_json()["exhibition"]["title"] == "Tunisia Builds"
        runs = client.get("/api/exhibitions").get_json()["runs"]
        assert runs[0]["run_id"] == "20261014-120000-cccccc"
        assert runs[1]["complete"] is True

    def test_images_are_looked_up(self, make_client, tmp_path):
        save_run(tmp_path, "20261014-100000-aaaaaa")
        body = make_client(image_lookup=lambda ids: {"c1": "https://img/solar.jpg"}).get(
            "/api/exhibition/20261014-100000-aaaaaa").get_json()
        assert body["exhibition"]["sections"][0]["artifacts"][0]["image_url"] == "https://img/solar.jpg"


class TestVisionRoute:
    def test_describe_images_once(self, make_client, tmp_path):
        save_run(tmp_path, "20261014-100000-aaaaaa")
        seen = []

        def describer(url):
            seen.append(url)
            return "Solar panels in a desert."

        client = make_client(
            image_lookup=lambda ids: {"c1": "https://img/solar.jpg", "c2": "https://img/mosaic.jpg"},
            describer=describer)
        body = client.post("/api/exhibition/20261014-100000-aaaaaa/vision").get_json()
        assert body["vision_added"] == 2
        assert body["exhibition"]["sections"][0]["artifacts"][0]["vision"].startswith("Solar")
        seen.clear()
        again = client.post("/api/exhibition/20261014-100000-aaaaaa/vision").get_json()
        assert again["vision_added"] == 0 and seen == []


def test_n8n_workflow_targets_these_routes():
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "n8n" / "workflows" / "Exhibition_pipeline_end_to_end.json"
    workflow = json.loads(path.read_text(encoding="utf-8"))
    names = {node["name"] for node in workflow["nodes"]}
    for source, outputs in workflow["connections"].items():
        assert source in names
        assert all(link["node"] in names for branch in outputs["main"] for link in branch)
    urls = " ".join(node["parameters"].get("url", "") for node in workflow["nodes"])
    assert "'/api/exhibition'" in urls and "'/api/exhibition/' + $json.run_id" in urls
    loop = workflow["connections"]["Still running?"]["main"][0]
    assert loop == [{"node": "Wait 60 s", "type": "main", "index": 0}]
    assert all(node.get("webhookId") for node in workflow["nodes"] if node["type"] == "n8n-nodes-base.webhook")
    assert "localhost" not in urls
    summary = next(n for n in workflow["nodes"] if n["name"] == "Exhibition summary")
    assert summary["type"] == "n8n-nodes-base.code"
    code = summary["parameters"]["jsCode"]
    assert "museum_url" in code and "halls" in code and "/virtual?run=" in code
    assert "_kind" in code and "image" in code
    names = {node["name"] for node in workflow["nodes"]}
    assert "Only hall images" in names and "Download museum images" in names
    assert workflow["connections"]["Exhibition summary"]["main"][0][0]["node"] == "Only hall images"
    download = next(n for n in workflow["nodes"] if n["name"] == "Download museum images")
    assert download["parameters"]["options"]["response"]["response"]["responseFormat"] == "file"


def test_dashboard_serves_the_exhibition_page():
    from app import create_app

    client = create_app().test_client()
    html = client.get("/tableau-de-bord").get_data(as_text=True)
    assert 'id="section-exhibition"' in html and 'data-section="exhibition"' in html
    assert 'id="exMuseum"' in html and 'id="exMuseumHalls"' in html
    assert "exhibition.js" in html
    js = client.get("/web/exhibition.js").get_data(as_text=True)
    assert client.get("/web/exhibition.js").status_code == 200
    assert "renderMuseumHalls" in js and "museum=1" in js


def test_validation_lists_current_prompt_versions():
    from app import create_app

    steps = create_app().test_client().get("/api/validate").get_json()["steps"]
    prompts = next(s for s in steps if s["name"].startswith("Prompts"))
    assert prompts["detail"].startswith("9/9")
    assert "technology" in prompts["detail"] and "curator" in prompts["detail"]


def test_web_app_registers_the_exhibition_routes():
    from app import create_app

    rules = {rule.rule for rule in create_app().url_map.iter_rules()}
    assert {
        "/api/exhibition", "/api/exhibition/<run_id>", "/api/exhibition/latest",
        "/api/exhibitions", "/api/exhibition/<run_id>/cancel", "/api/exhibition/<run_id>/vision",
    } <= rules


def test_default_runner_replay(tmp_path, monkeypatch):
    class FakeCompletions:
        def create(self, *a, **k):
            return type("R", (), {"choices": [type("C", (), {"message": type("M", (), {"content": "{}"})()})()]})()

    class FakeLLM:
        chat = type("Chat", (), {"completions": FakeCompletions()})()

    source = RunRecorder(runs_dir=tmp_path, run_id="20261014-090000-bbbbbb", config={})
    record_pipeline(source, complete=False)
    monkeypatch.setattr("agents.llm_config.build_llm_client", lambda: FakeLLM())
    monkeypatch.setattr("agents.pipeline.curate", lambda ctx, llm, recorder, fact_check=True: recorder.record(
        "result", exhibition=EXHIBITION) or EXHIBITION)
    recorder = RunRecorder(runs_dir=tmp_path, run_id="20261014-100000-aaaaaa",
                           config={"from_run": "20261014-090000-bbbbbb"})
    exhibition_api._default_runner(
        {"from_run": "20261014-090000-bbbbbb", "fact_check": True, "country": None,
         "year_from": 2020, "year_to": 2026, "timeout": 60, "review": True},
        recorder,
    )
    kinds = [e["kind"] for e in recorder.events]
    assert "insight" in kinds and "result" in kinds
