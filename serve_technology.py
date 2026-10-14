"""Local HTTP bridge: n8n -> TechnologyAgent (own hybrid search) -> JSON insight.

    python serve_technology.py                       # http://127.0.0.1:5002

POST /api/technology   {"country": "Tunisia", "year_from": 2020, "year_to": 2026,
                        "chunks": [{"chunk_id", "content", "metadata"}, ...],   # optional shared evidence
                        "use_rag": true}                                       # agent's own search
GET  /health

Set TECHNOLOGY_API_TOKEN to require "Authorization: Bearer <token>".
n8n template: n8n/workflows/TechnologyAgent_Tasnim_template.json.
"""
from __future__ import annotations

import hmac
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv
from flask import Flask, jsonify, request

MAX_CHUNKS = 50


def _default_agent(client: Any):
    from agents.technology import TechnologyAgent
    return TechnologyAgent(client)


def _default_client():
    from agents.llm_config import build_llm_client
    return build_llm_client()


def _default_retriever(country: str | None, year_from: int | None, year_to: int | None):
    from rag.vector_store.hybrid_retriever import SearchFilters, build_hybrid_retriever
    return build_hybrid_retriever(filters=SearchFilters(country=country, year_from=year_from, year_to=year_to))


def _parse_chunks(raw: Any) -> list:
    from rag.vector_store.retriever import RetrievalResult

    if raw is None:
        return []
    if not isinstance(raw, list) or len(raw) > MAX_CHUNKS:
        raise ValueError(f"chunks must be a list of at most {MAX_CHUNKS} objects.")
    chunks = []
    for item in raw:
        if not isinstance(item, dict) or not str(item.get("chunk_id") or "").strip() \
                or not isinstance(item.get("content"), str):
            raise ValueError("each chunk needs a chunk_id and a content string.")
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        chunks.append(RetrievalResult(chunk_id=str(item["chunk_id"]), document_id=str(item.get("document_id") or ""),
                                      content=item["content"], metadata=metadata))
    return chunks


def _optional_year(data: dict, key: str, default: int) -> int | None:
    value = data.get(key, default)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 1900 <= value <= 2100:
        raise ValueError(f"{key} must be a year or null.")
    return value


def dropped_findings(events: list[dict]) -> list[dict]:
    """One entry per finding removed by a Technology guardrail (figure check or finding budget)."""
    out = []
    for event in events:
        if event.get("rule") == "finding_budget":
            out.extend({"finding": f, "rule": "finding_budget"} for f in event.get("dropped", []))
        else:
            out.append({"finding": event["finding"], "rule": "ungrounded_figure", "figures": event["figures"]})
    return out


def create_app(agent_factory: Callable = _default_agent, client_factory: Callable = _default_client,
               retriever_factory: Callable = _default_retriever) -> Flask:
    load_dotenv(Path(__file__).resolve().parent / ".env")
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 256 * 1024

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "agent": "technology"})

    @app.post("/api/technology")
    def analyze():
        from agents.run_log import RunRecorder

        token = os.getenv("TECHNOLOGY_API_TOKEN")
        if token and not hmac.compare_digest(request.headers.get("Authorization", ""), "Bearer " + token):
            return jsonify({"error": "Unauthorized"}), 401
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "A JSON object is required."}), 400
        country = data.get("country", "Tunisia")
        use_rag = data.get("use_rag", True)
        try:
            if country is not None and (not isinstance(country, str) or len(country) > 100):
                raise ValueError("country must be a short string or null.")
            if not isinstance(use_rag, bool):
                raise ValueError("use_rag must be a boolean.")
            year_from = _optional_year(data, "year_from", 2020)
            year_to = _optional_year(data, "year_to", 2026)
            chunks = _parse_chunks(data.get("chunks"))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        if not chunks and not use_rag:
            return jsonify({"error": "Send chunks or set use_rag to true."}), 400

        try:
            agent = agent_factory(client_factory())
            agent.recorder = RunRecorder()
            if use_rag:
                agent.retriever = retriever_factory(country or None, year_from, year_to)
            insight = agent.run(chunks)
        except Exception:  # noqa: BLE001 - provider/database details stay in the server log
            app.logger.exception("technology agent failed")
            return jsonify({"error": "LLM, database or provider call failed. Check backend configuration and quota."}), 502

        selection = (agent.recorder.events_of("evidence_selection") or [{}])[-1]
        return jsonify({
            "status": "abstained" if not insight.key_findings else "ok",
            "coverage": selection.get("coverage", ""),
            "evidence_pool": selection.get("pool", 0),
            "dropped_findings": dropped_findings(agent.recorder.events_of("guardrail")),
            "insight": asdict(insight),
        })

    return app


if __name__ == "__main__":
    # Local development only. Docker/cloud n8n requires a reachable backend address.
    create_app().run(host="127.0.0.1", port=5002, debug=False)
