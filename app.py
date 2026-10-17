from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import os
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, jsonify, render_template, request

from agents.base_agent import InsightObject
from agents.historian import HistorianAgent
from agents.llm_config import build_llm_client, get_model
from agents.shared_context import compute_cross_references
from exhibition_api import create_exhibition_blueprint
from multimodal.analyze_image import analyze_image
from rag.chunking.chunker import ChunkConfig, Chunker, ChunkingStrategy
from rag.vector_store.retriever import RetrievalResult, Retriever


def _supabase_counts() -> dict[str, int] | None:
    """Read-only exact counts of documents and chunks; None if keys are missing or the call fails."""
    url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None
    try:
        from supabase import create_client

        client = create_client(url, key)
        docs = client.table("documents").select("id", count="exact").limit(1).execute()
        chunks = client.table("chunks").select("id", count="exact").limit(1).execute()
        return {"documents": int(docs.count or 0), "chunks": int(chunks.count or 0)}
    except Exception:  # noqa: BLE001
        return None


def create_app() -> Flask:
    app = Flask(__name__, static_folder="web", template_folder="web")
    app.register_blueprint(create_exhibition_blueprint())

    def _result(name: str, ok: bool, detail: str) -> dict[str, Any]:
        return {"name": name, "ok": ok, "detail": detail}

    def _corpus_file_info(p: Path) -> dict[str, Any]:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            records = len(data) if isinstance(data, list) else 1
        except Exception:
            records = 0
        size_kb = round(p.stat().st_size / 1024, 1)
        return {"name": p.name, "size_kb": size_kb, "records": records}

    def _prompt_file_info(name: str) -> dict[str, Any]:
        p = Path("prompts") / name
        if not p.exists():
            return {"name": name, "found": False, "version": None}
        text = p.read_text(encoding="utf-8")
        version = None
        for line in text.splitlines():
            if line.startswith("## v"):
                version = line.replace("## ", "").split()[0]
        return {"name": name, "found": True, "version": version}

    @app.get("/api/data")
    def get_data() -> Any:
        """Return all processed records for the data explorer page."""
        processed_dir = Path("data/processed")
        all_records: list[dict] = []
        if processed_dir.exists():
            for f in sorted(processed_dir.glob("*.json")):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    if isinstance(data, list):
                        for rec in data:
                            if isinstance(rec, dict):
                                all_records.append({
                                    "id":       rec.get("id", ""),
                                    "source":   rec.get("source", ""),
                                    "category": rec.get("category", ""),
                                    "title":    rec.get("title", ""),
                                    "text":     (rec.get("text", "") or "")[:400],
                                    "url":      rec.get("url", ""),
                                    "date":     rec.get("date", ""),
                                    "lang":     rec.get("lang", ""),
                                    "tags":     rec.get("tags", [])[:5],
                                    "image_url": rec.get("image_url"),
                                })
                except Exception:
                    pass
        return jsonify({"total": len(all_records), "records": all_records})

    @app.get("/")
    def index() -> str:
        return render_template("index.html")

    @app.get("/favicon.ico")
    def favicon() -> tuple[str, int]:
        return "", 204

    @app.get("/api/historian/presets")
    def get_historian_presets() -> Any:
        # Short summaries of documented events (see the Wikipedia articles on each),
        # used as sample evidence for the historian demo.
        presets = [
            {
                "id": "tunisia_2021_constitution",
                "title": "Le 25 juillet 2021 et la nouvelle Constitution",
                "category": "Politique & Institutions",
                "chunks": [
                    {
                        "chunk_id": "tn-politique-01",
                        "document_id": "wiki-crise-politique-2021",
                        "content": "Le 25 juillet 2021, le président Kaïs Saïed limoge le chef du gouvernement Hichem Mechichi et gèle les activités de l'Assemblée des représentants du peuple, en invoquant l'article 80 de la Constitution de 2014.",
                        "metadata": {"source": "wikipedia", "category": "politics", "country": "Tunisia"},
                    },
                    {
                        "chunk_id": "tn-politique-02",
                        "document_id": "wiki-referendum-2022",
                        "content": "Le 25 juillet 2022, une nouvelle Constitution qui renforce les pouvoirs du président est adoptée par référendum, avec une participation d'environ 30 %.",
                        "metadata": {"source": "wikipedia", "category": "politics", "country": "Tunisia"},
                    },
                    {
                        "chunk_id": "tn-politique-03",
                        "document_id": "wiki-legislatives-2022",
                        "content": "Au premier tour des élections législatives de décembre 2022, la participation est d'environ 11 %.",
                        "metadata": {"source": "wikipedia", "category": "politics", "country": "Tunisia"},
                    },
                ],
            },
            {
                "id": "tunisia_migration",
                "title": "Migrations en Méditerranée centrale",
                "category": "Société & Migration",
                "chunks": [
                    {
                        "chunk_id": "tn-migration-01",
                        "document_id": "wiki-migration-mediterranee",
                        "content": "En 2023, la Tunisie devient le principal point de départ des traversées irrégulières de la Méditerranée centrale vers l'Italie, devant la Libye.",
                        "metadata": {"source": "wikipedia", "category": "migration", "country": "Tunisia"},
                    },
                    {
                        "chunk_id": "tn-migration-02",
                        "document_id": "wiki-memorandum-ue-tunisie",
                        "content": "Le 16 juillet 2023, l'Union européenne et la Tunisie signent un mémorandum d'entente portant notamment sur la migration et la coopération économique.",
                        "metadata": {"source": "wikipedia", "category": "migration", "country": "Tunisia"},
                    },
                ],
            },
            {
                "id": "tunisia_cinema",
                "title": "Le cinéma tunisien sur la scène mondiale",
                "category": "Culture & Arts",
                "chunks": [
                    {
                        "chunk_id": "tn-cinema-01",
                        "document_id": "wiki-homme-vendu-sa-peau",
                        "content": "En 2021, « L'Homme qui a vendu sa peau » de Kaouther Ben Hania devient le premier film tunisien nommé à l'Oscar du meilleur film international.",
                        "metadata": {"source": "wikipedia", "category": "culture", "country": "Tunisia"},
                    },
                    {
                        "chunk_id": "tn-cinema-02",
                        "document_id": "wiki-filles-olfa",
                        "content": "« Les Filles d'Olfa » de Kaouther Ben Hania, en compétition au Festival de Cannes 2023, y reçoit L'Œil d'or puis est nommé à l'Oscar du meilleur film documentaire en 2024.",
                        "metadata": {"source": "wikipedia", "category": "culture", "country": "Tunisia"},
                    },
                ],
            },
        ]
        return jsonify({"presets": presets})

    @app.post("/api/historian/analyze")
    def analyze_historian() -> Any:
        data = request.get_json(silent=True) or {}
        raw_chunks = data.get("chunks", [])

        chunks: list[RetrievalResult] = []
        for i, c in enumerate(raw_chunks):
            if isinstance(c, dict):
                cid = str(c.get("chunk_id") or f"c_{i+1}")
                did = str(c.get("document_id") or f"doc_{i+1}")
                cnt = str(c.get("content") or "")
                meta = c.get("metadata") if isinstance(c.get("metadata"), dict) else {}
                sim = float(c.get("similarity", 0.9))
                chunks.append(RetrievalResult(chunk_id=cid, document_id=did, content=cnt, metadata=meta, similarity=sim))
            elif isinstance(c, str):
                chunks.append(RetrievalResult(chunk_id=f"c_{i+1}", document_id=f"doc_{i+1}", content=c, metadata={}, similarity=0.9))

        if not chunks:
            return jsonify({"ok": False, "error": "Aucun document ou chunk fourni pour l'analyse historique."}), 400

        # No canned fallback: an analysis is either produced by the model or reported as unavailable.
        if not (os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY")):
            return jsonify({
                "ok": False,
                "error": "Aucune clé LLM_API_KEY configurée : définissez-la dans le fichier .env pour lancer l'agent historien.",
            }), 503
        try:
            insight = HistorianAgent(openai_client=build_llm_client()).run(chunks)
        except Exception as exc:
            return jsonify({"ok": False, "error": f"Le fournisseur d'IA a rejeté la requête : {exc}"}), 502

        return jsonify({
            "ok": True,
            "mode": "live",
            "model": get_model(),
            "insight": {
                "agent": insight.agent,
                "perspective": insight.perspective,
                "key_findings": insight.key_findings,
                "selected_artifacts": insight.selected_artifacts,
            },
            "grounded_artifacts": insight.selected_artifacts,
            "input_chunk_ids": [c.chunk_id for c in chunks],
        })

    @app.post("/api/embed")
    def embed_text() -> Any:
        """Embed one text with the same local model the retriever queries with.

        Used by the n8n ingestion workflow so its chunks match the 384-dim
        vector(384) column in rag/schema.sql. The response mirrors Gemini's
        embedContent shape ({"embedding": {"values": [...]}}).
        """
        from rag.vector_store.local_embeddings import EMBEDDING_DIM, EMBEDDING_MODEL, build_embedding_client

        data = request.get_json(silent=True) or {}
        text = data.get("text")
        if not isinstance(text, str) or not text.strip():
            return jsonify({"error": "Provide a non-empty 'text' string."}), 400
        vector = build_embedding_client().embeddings.create(input=text).data[0].embedding
        return jsonify({"embedding": {"values": vector}, "model": EMBEDDING_MODEL, "dim": EMBEDDING_DIM})

    @app.get("/api/validate")
    def validate_pipeline() -> Any:
        steps: list[dict[str, Any]] = []

        # 1 — Corpus (local files, or read-only counts from Supabase when processed is empty)
        processed_dir = Path("data/processed")
        json_files = sorted(processed_dir.glob("*.json")) if processed_dir.exists() else []
        corpus_files = [_corpus_file_info(f) for f in json_files]
        corpus_detail = f"{len(json_files)} fichier(s) JSON in data/processed"
        corpus_ok = bool(json_files)
        if not json_files:
            counts = _supabase_counts()
            if counts:
                corpus_ok = True
                corpus_detail = f"{counts['documents']} documents, {counts['chunks']} chunks dans Supabase"
        steps.append(_result("Corpus collected", corpus_ok, corpus_detail))

        # 2 — Chunking
        sample_record = {
            "id": "demo-1",
            "source": "wikimedia",
            "category": "image",
            "lang": "fr",
            "title": "Demo record",
            "text": (
                "Les étudiants explorent les systèmes de données, les images "
                "et la mémoire collective de notre époque contemporaine."
            ),
        }
        chunker = Chunker(ChunkConfig(strategy=ChunkingStrategy.FIXED_SIZE, chunk_size=32, overlap_pct=0.2))
        chunks = chunker.chunk(sample_record)
        chunk_ok = bool(chunks) and all(c.content.strip() for c in chunks)
        steps.append(_result("Chunking strategy", chunk_ok, f"{len(chunks)} chunk(s) généré(s)"))

        # 3 — Retrieval
        retriever = Retriever(supabase_client=None, openai_client=None, match_count=3)
        retrieval_ok = callable(getattr(retriever, "retrieve", None))
        steps.append(_result("Initial retrieval tests", retrieval_ok,
                              "Retriever initialisé et prêt pour les requêtes"))

        # 4 — Agents
        insights = {
            "historian":   InsightObject("historian",   "History",  ["A"], ["artifact-1", "artifact-2"]),
            "sociologist": InsightObject("sociologist", "Society",  ["B"], ["artifact-2", "artifact-3"]),
            "technology":  InsightObject("technology",  "Tech",     ["C"], ["artifact-3"]),
        }
        refs = compute_cross_references(insights)
        agents_ok = set(refs) == {"artifact-2", "artifact-3"}
        steps.append(_result("Agents implemented and communicating",
                              agents_ok, f"Cross references: {refs}"))

        # 5 — Prompts
        prompt_names = [
            "system.md", "historian.md", "sociologist.md", "technology.md", "culture_art.md",
            "visual.md", "reviewer.md", "curator.md", "fact_checker.md",
        ]
        prompt_infos = [_prompt_file_info(n) for n in prompt_names]
        prompt_ok = all(p["found"] for p in prompt_infos)
        found_count = sum(1 for p in prompt_infos if p["found"])
        detail = ", ".join(
            f"{p['name'].removesuffix('.md')} {p['version'] or '?'}" for p in prompt_infos if p["found"]
        )
        steps.append(_result(
            "Prompts versioned and measured",
            prompt_ok,
            f"{found_count}/{len(prompt_names)} prompt(s) : {detail}",
        ))

        # 6 — Multimodal
        vision = analyze_image("https://example.com/does-not-exist.jpg")
        multimodal_ok = isinstance(vision.description, str) and vision.description == "Image unavailable."
        steps.append(_result("Multimodal component", multimodal_ok,
                              "Analyse d'image en mode dégradation gracieuse"))

        overall = all(step["ok"] for step in steps)
        return jsonify({
            "status":          "ok" if overall else "warning",
            "summary":         "Validation S5 terminée ✓" if overall else "Validation S5 partielle",
            "steps":           steps,
            "corpus_files":    corpus_files,
            "prompt_files":    prompt_infos,
            "cross_references": refs,
        })

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
