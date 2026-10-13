"""Local HTTP bridge: n8n -> retrieval -> CultureArtAgent -> JSON insight."""
from __future__ import annotations

import hmac
import os
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request

from agents.culture_art import CultureArtAgent
from agents.culture_scope import analysis_status, resolve_country
from agents.llm_config import build_llm_client
from rag.vector_store.culture_retrieval import (
    CultureRetrievalError, build_supabase_client, retrieve_culture,
)


def create_app():
    load_dotenv(Path(__file__).resolve().parent / ".env")
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "agent": "culture_art"})

    @app.post("/api/culture-art")
    def analyze():
        token = os.getenv("CULTURE_API_TOKEN")
        if token and not hmac.compare_digest(request.headers.get("Authorization", ""), "Bearer " + token):
            return jsonify({"error": "Unauthorized"}), 401
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "A JSON object is required."}), 400
        query = data.get("query")
        top_k = data.get("top_k", 5)
        category = data.get("category")
        country = data.get("country")
        if not isinstance(query, str) or not query.strip() or len(query) > 2000:
            return jsonify({"error": "query must contain 1-2000 characters."}), 400
        if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 20:
            return jsonify({"error": "top_k must be an integer between 1 and 20."}), 400
        if category is not None and (not isinstance(category, str) or len(category) > 100):
            return jsonify({"error": "category must be a short string."}), 400
        try:
            resolve_country(query, country)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        try:
            retrieval_info = {}
            chunks = retrieve_culture(query, build_supabase_client(), top_k, category, country=country, diagnostics=retrieval_info)
            # No provider call needed when retrieval returned nothing.
            client = build_llm_client() if chunks else None
            result = CultureArtAgent(client).run(chunks, query=query, country=country)
            return jsonify({"query": query,
                            **analysis_status(result, chunks, query, country),
                            "retrieval": retrieval_info,
                            "retrieved_evidence": [asdict(chunk) for chunk in chunks],
                            "insight": asdict(result)})
        except CultureRetrievalError as exc:
            return jsonify({"error": str(exc)}), 503
        except Exception:
            return jsonify({"error": "LLM or provider call failed. Check backend configuration and quota."}), 502

    return app


if __name__ == "__main__":
    # Local development only. Docker/cloud n8n requires a reachable backend address.
    create_app().run(host="127.0.0.1", port=5001, debug=False)
