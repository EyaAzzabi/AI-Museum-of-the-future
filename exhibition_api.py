"""Exhibition API: run the whole pipeline over HTTP, follow it, and read saved exhibitions.

Registered on the web app (app.py), so the exhibition page and n8n use the same server.

POST /api/exhibition             start a run; 202 {"run_id", "status_url"}
                                 {"country", "year_from", "year_to", "review", "fact_check",
                                  "timeout", "wait", "from_run"}
POST /api/exhibition/<run_id>/cancel   stop at the next step (finished steps stay saved)
POST /api/exhibition/<run_id>/vision   describe the exhibition's images (vision.json)
GET  /api/exhibition/<run_id>    status, then the exhibition
GET  /api/exhibition/<run_id>/museum-image  reserved (404 until museum image is added)
GET  /api/exhibition/latest      last complete exhibition
GET  /api/exhibitions            saved runs, newest first

One run at a time (409). Optional EXHIBITION_API_TOKEN on POST.
"""
from __future__ import annotations

import hmac
import json
import logging
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

RUN_ID = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{6}$")
CITED_LINE = re.compile(r"^\[([0-9a-f-]{36})\]")
MAX_TIMEOUT = 900
WAIT_LIMIT = 900
LIST_LIMIT = 30
VISION_WORKERS = 2


class RunCancelled(Exception):
    """Raised inside a run once POST .../cancel was called."""


class _CancellableCompletions:
    def __init__(self, completions: Any, cancelled: threading.Event):
        self._completions = completions
        self._cancelled = cancelled

    def create(self, *args: Any, **kwargs: Any) -> Any:
        if self._cancelled.is_set():
            raise RunCancelled("run stopped by the user")
        return self._completions.create(*args, **kwargs)


class _CancellableLLM:
    def __init__(self, client: Any, cancelled: threading.Event):
        self._client = client
        self.chat = type("Chat", (), {"completions": _CancellableCompletions(client.chat.completions, cancelled)})()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


def _default_runner(params: dict, recorder: Any) -> None:
    from agents.llm_config import build_llm_client
    from agents.pipeline import context_from_run, curate, run_pipeline
    from agents.run_log import load_run
    from rag.vector_store.hybrid_retriever import SearchFilters, build_hybrid_retriever

    llm = _CancellableLLM(build_llm_client(), getattr(recorder, "cancelled", threading.Event()))
    if params["from_run"]:
        source = load_run(recorder.runs_dir / params["from_run"])
        for event in source["events"]:
            if event["kind"] in ("evidence", "images", "insight", "abstain", "agent_error", "review"):
                recorder.events.append(event)
        try:
            curate(context_from_run(source), llm, recorder, fact_check=params["fact_check"])
        finally:
            recorder.save()
        return
    filters = SearchFilters(country=params["country"], year_from=params["year_from"], year_to=params["year_to"])
    run_pipeline(
        [], llm, timeout_secs=params["timeout"],
        retriever=build_hybrid_retriever(llm_client=llm, filters=filters),
        recorder=recorder, review=params["review"], fact_check=params["fact_check"],
    )


def _default_image_lookup(chunk_ids: list[str]) -> dict[str, str]:
    if not chunk_ids:
        return {}
    try:
        from supabase import create_client

        from scripts.config import SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL

        client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        chunks = client.table("chunks").select("id,document_id").in_("id", chunk_ids).execute().data or []
        doc_ids = sorted({c["document_id"] for c in chunks})
        docs = (
            client.table("documents").select("id,metadata").in_("id", doc_ids).execute().data or []
            if doc_ids else []
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Image lookup failed: %s", exc)
        return {}
    image_of = {d["id"]: (d.get("metadata") or {}).get("image_url") for d in docs}
    return {c["id"]: image_of[c["document_id"]] for c in chunks if image_of.get(c["document_id"])}


def vision_descriptions(events: list[dict]) -> dict[str, str]:
    """Vision text by chunk id from the images event, or recovered from the visual LLM prompt."""
    found: dict[str, str] = {}
    for event in events:
        if event.get("kind") == "images":
            found.update({k: v for k, v in (event.get("descriptions") or {}).items() if isinstance(v, str) and v})
    if found:
        return found
    for event in events:
        if event.get("kind") != "llm_call" or event.get("agent") != "visual":
            continue
        current, lines = None, []
        for line in str(event.get("user") or "").splitlines() + ["Task:"]:
            match = CITED_LINE.match(line)
            if match or line.startswith("Task:"):
                if current and lines:
                    found[current] = "\n".join(lines).strip()[:500]
                current, lines = (match.group(1) if match else None), []
            elif line.startswith("vision: ") and current:
                lines = [line[len("vision: "):]]
            elif lines:
                lines.append(line)
    return found


def _default_describer(image_url: str) -> str:
    from multimodal.analyze_image import analyze_image, summarize_for_evidence

    return summarize_for_evidence(analyze_image(image_url))


def exhibition_view(
    run: dict,
    image_lookup: Callable[[list[str]], dict] | None = None,
    vision: dict[str, str] | None = None,
) -> dict:
    events = run.get("events") or []
    result = next((e.get("exhibition") for e in reversed(events) if e.get("kind") == "result"), None)
    evidence: dict[str, dict] = {}
    insights: dict[str, dict] = {}
    for event in events:
        kind, agent = event.get("kind"), event.get("agent")
        if kind == "insight":
            data = event.get("insight") or {}
            evidence.update(data.get("evidence") or {})
            insights[agent] = {
                "status": "ok" if data.get("key_findings") else "abstained",
                "perspective": data.get("perspective", ""),
                "key_findings": data.get("key_findings") or [],
                "selected_artifacts": data.get("selected_artifacts") or [],
            }
        elif kind == "abstain" and agent not in insights:
            insights[agent] = {"status": "abstained", "reason": event.get("reason")}
        elif kind == "agent_error":
            insights[agent] = {"status": "error"}
    review = next((e.get("review") for e in reversed(events) if e.get("kind") == "review"), None) \
        or (result or {}).get("review") or {}
    vision = vision if vision is not None else vision_descriptions(events)

    exhibition = None
    if result:
        artifact_ids = sorted({cid for s in result.get("sections") or [] for cid in s.get("artifacts") or []})
        images = image_lookup(artifact_ids) if image_lookup else {}
        verdicts = {v.get("section"): v for v in result.get("fact_check") or [] if isinstance(v, dict)}
        exhibition = {
            "title": result.get("exhibition_title", ""),
            "concept": result.get("concept", ""),
            "sections": [
                {
                    "title": section.get("title", ""),
                    "narrative": section.get("narrative", ""),
                    "artifacts": [
                        {
                            "id": cid,
                            **evidence.get(cid, {}),
                            "image_url": images.get(cid) or (evidence.get(cid) or {}).get("image_url"),
                            "vision": vision.get(cid) or (evidence.get(cid) or {}).get("vision_description"),
                        }
                        for cid in section.get("artifacts") or []
                    ],
                    "fact_check": verdicts.get(i),
                }
                for i, section in enumerate(result.get("sections") or [])
            ],
            "missing_perspectives": result.get("missing_perspectives") or [],
        }
    return {
        "run_id": run.get("run_id"),
        "started_at": run.get("started_at"),
        "status": "done" if exhibition else "failed",
        "cancelled": any(e.get("kind") == "cancelled" for e in events),
        "config": run.get("config") or {},
        "timings": run.get("timings") or {},
        "exhibition": exhibition,
        "review": {key: review.get(key) or [] for key in ("agreements", "tensions", "weak_findings")},
        "insights": insights,
    }


def _parse_params(data: dict) -> dict:
    def year(key: str, default: int) -> int | None:
        if key not in data or data[key] is None or data[key] == "":
            return default
        value = data[key]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{key} must be an integer year.")
        return value

    def flag(key: str, default: bool) -> bool:
        if key not in data:
            return default
        if not isinstance(data[key], bool):
            raise ValueError(f"{key} must be true or false.")
        return data[key]

    country = data.get("country", "Tunisia")
    if country is not None and not isinstance(country, str):
        raise ValueError("country must be a string.")
    timeout = data.get("timeout", 400)
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 30 <= timeout <= MAX_TIMEOUT:
        raise ValueError(f"timeout must be between 30 and {MAX_TIMEOUT} seconds.")
    from_run = data.get("from_run")
    if from_run is not None and (not isinstance(from_run, str) or not RUN_ID.match(from_run)):
        raise ValueError("from_run must be a run id such as 20261014-205736-68ae22.")
    return {
        "country": country or None, "year_from": year("year_from", 2020), "year_to": year("year_to", 2026),
        "review": flag("review", True), "fact_check": flag("fact_check", True), "timeout": timeout,
        "wait": flag("wait", False), "from_run": from_run,
    }


def create_exhibition_blueprint(
    runner: Callable[[dict, Any], None] = _default_runner,
    runs_dir: str | Path | None = None,
    image_lookup: Callable[[list[str]], dict] | None = _default_image_lookup,
    describer: Callable[[str], str] = _default_describer,
) -> Blueprint:
    from agents.run_log import DEFAULT_RUNS_DIR, RunRecorder

    class CancellableRecorder(RunRecorder):
        def __init__(self, *args: Any, **kwargs: Any):
            super().__init__(*args, **kwargs)
            self.cancelled = threading.Event()

        def record(self, kind: str, **data: Any) -> None:
            if self.cancelled.is_set() and kind != "cancelled":
                raise RunCancelled("run stopped by the user")
            super().record(kind, **data)

    runs = Path(runs_dir) if runs_dir else DEFAULT_RUNS_DIR
    bp = Blueprint("exhibition", __name__)
    lock = threading.Lock()
    jobs: dict[str, dict] = {}

    def unauthorized() -> bool:
        token = os.getenv("EXHIBITION_API_TOKEN")
        return bool(token) and not hmac.compare_digest(
            request.headers.get("Authorization", ""), "Bearer " + token
        )

    def run_path(run_id: str) -> Path:
        return runs / run_id / "run.json"

    def vision_path(run_id: str) -> Path:
        return runs / run_id / "vision.json"

    def load(run_id: str) -> dict | None:
        from agents.run_log import load_run

        path = run_path(run_id)
        return load_run(path) if path.exists() else None

    def saved_vision(run_id: str) -> dict[str, str]:
        try:
            data = json.loads(vision_path(run_id).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return {k: v for k, v in data.items() if isinstance(v, str)} if isinstance(data, dict) else {}

    def vision_for(run: dict) -> dict[str, str]:
        found = vision_descriptions(run.get("events") or [])
        source_id = (run.get("config") or {}).get("from_run")
        if not found and isinstance(source_id, str) and RUN_ID.match(source_id):
            source = load(source_id)
            found = vision_descriptions((source or {}).get("events") or [])
        return {**found, **saved_vision(str(run.get("run_id") or ""))}

    def view(run: dict) -> dict:
        return exhibition_view(run, image_lookup, vision_for(run))

    def running_job() -> str | None:
        return next((rid for rid, job in jobs.items() if job["status"] == "running"), None)

    def status_of(run_id: str) -> tuple[dict, int]:
        job = jobs.get(run_id)
        if job and job["status"] == "running":
            return {
                "run_id": run_id, "status": "running", "started_at": job["started_at"],
                "cancelling": job["recorder"].cancelled.is_set(),
            }, 200
        run = load(run_id)
        if run is None:
            if job:
                return {"run_id": run_id, "status": "failed", "error": job["error"]}, 200
            return {"error": "Unknown run."}, 404
        body = view(run)
        if job and job.get("error"):
            body["error"] = job["error"]
        return body, 200

    def work(run_id: str, params: dict, recorder: Any) -> None:
        try:
            runner(params, recorder)
            error = None
        except Exception as exc:  # noqa: BLE001
            if recorder.cancelled.is_set():
                recorder.record("cancelled")
                recorder.save()
                error = "Run stopped by the user. The steps already finished are saved."
            else:
                logger.exception("exhibition run %s failed", run_id)
                text = str(exc)
                reason = "provider rate limit" if "429" in text or "rate limit" in text.lower() else "pipeline error"
                error = f"The run stopped ({reason}). Partial results, if any, are saved; see the server log."
        with lock:
            jobs[run_id].update(status="failed" if error else "done", error=error)

    @bp.post("/api/exhibition")
    def start():
        from agents.llm_config import get_model

        if unauthorized():
            return jsonify({"error": "Unauthorized"}), 401
        data = request.get_json(silent=True)
        if data is None:
            data = {}
        if not isinstance(data, dict):
            return jsonify({"error": "A JSON object is required."}), 400
        try:
            params = _parse_params(data)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        if params["from_run"] and not run_path(params["from_run"]).exists():
            return jsonify({"error": "from_run: no saved run with this id."}), 404

        with lock:
            busy = running_job()
            if busy:
                return jsonify({
                    "error": "A run is already in progress.", "run_id": busy,
                    "status_url": f"/api/exhibition/{busy}",
                }), 409
            recorder = CancellableRecorder(runs_dir=runs, config={
                "model": get_model(), "country": params["country"],
                "years": [params["year_from"], params["year_to"]],
                "review": params["review"], "fact_check": params["fact_check"],
                "timeout": params["timeout"], "rerank": False,
                "from_run": params["from_run"], "trigger": "api",
            })
            run_id = recorder.run_id
            thread = threading.Thread(target=work, args=(run_id, params, recorder), daemon=True)
            jobs[run_id] = {
                "status": "running", "thread": thread, "error": None, "recorder": recorder,
                "started_at": datetime.now(timezone.utc).isoformat(),
            }
            thread.start()

        if params["wait"]:
            thread.join(WAIT_LIMIT)
            body, code = status_of(run_id)
            return jsonify(body), code if body.get("status") != "running" else 202
        return jsonify({"run_id": run_id, "status": "running", "status_url": f"/api/exhibition/{run_id}"}), 202

    @bp.post("/api/exhibition/<run_id>/cancel")
    def cancel(run_id: str):
        if unauthorized():
            return jsonify({"error": "Unauthorized"}), 401
        job = jobs.get(run_id)
        if not job or job["status"] != "running":
            return jsonify({"error": "No run in progress with this id."}), 404
        job["recorder"].cancelled.set()
        return jsonify({
            "run_id": run_id, "status": "cancelling",
            "detail": "Stops at the next step; LLM calls already sent finish first.",
        }), 202

    @bp.get("/api/exhibition/latest")
    def latest():
        for folder in sorted((p for p in runs.glob("*") if RUN_ID.match(p.name)), reverse=True):
            run = load(folder.name)
            if run and any(e.get("kind") == "result" for e in run.get("events") or []):
                return jsonify(view(run))
        return jsonify({"error": "No complete exhibition has been saved yet."}), 404

    @bp.get("/api/exhibition/<run_id>")
    def status(run_id: str):
        if not RUN_ID.match(run_id):
            return jsonify({"error": "Invalid run id."}), 400
        body, code = status_of(run_id)
        return jsonify(body), code

    @bp.post("/api/exhibition/<run_id>/vision")
    def describe_images(run_id: str):
        if unauthorized():
            return jsonify({"error": "Unauthorized"}), 401
        if not RUN_ID.match(run_id):
            return jsonify({"error": "Invalid run id."}), 400
        run = load(run_id)
        if run is None:
            return jsonify({"error": "Unknown run."}), 404
        current = view(run)
        if not current["exhibition"]:
            return jsonify({"error": "This run has no exhibition."}), 400
        todo = {
            a["id"]: a["image_url"]
            for s in current["exhibition"]["sections"] for a in s["artifacts"]
            if a.get("image_url") and not a.get("vision")
        }

        def describe(item: tuple[str, str]) -> tuple[str, str]:
            try:
                return item[0], describer(item[1])
            except Exception as exc:  # noqa: BLE001
                logger.warning("vision failed for %s: %s", item[0], exc)
                return item[0], ""

        if todo:
            with ThreadPoolExecutor(max_workers=min(VISION_WORKERS, len(todo))) as pool:
                new = {cid: text for cid, text in pool.map(describe, todo.items()) if text}
            if new:
                vision_path(run_id).write_text(
                    json.dumps({**saved_vision(run_id), **new}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
        body = view(run)
        body["vision_added"] = sum(
            1 for s in body["exhibition"]["sections"] for a in s["artifacts"]
            if a["id"] in todo and a.get("vision")
        )
        return jsonify(body)

    @bp.get("/api/exhibitions")
    def list_runs():
        items = []
        for folder in sorted((p for p in runs.glob("*") if RUN_ID.match(p.name)), reverse=True)[:LIST_LIMIT]:
            if folder.name in jobs and jobs[folder.name]["status"] == "running":
                continue
            try:
                run = load(folder.name)
            except ValueError:
                continue
            if run is None:
                continue
            result = next(
                (e.get("exhibition") for e in reversed(run.get("events") or []) if e.get("kind") == "result"),
                None,
            )
            config = run.get("config") or {}
            if config.get("demo"):
                continue
            items.append({
                "run_id": folder.name, "started_at": run.get("started_at"), "complete": bool(result),
                "title": (result or {}).get("exhibition_title"), "country": config.get("country"),
                "model": config.get("model"), "from_run": config.get("from_run"),
            })
        return jsonify({"running": running_job(), "runs": items})

    return bp
