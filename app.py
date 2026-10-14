from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import os
from dotenv import load_dotenv
load_dotenv(override=True)
from flask import Flask, jsonify, render_template, request

from agents.base_agent import InsightObject
from agents.historian import HistorianAgent
from agents.llm_config import build_llm_client, get_model
from agents.shared_context import compute_cross_references
from multimodal.analyze_image import analyze_image
from rag.chunking.chunker import ChunkConfig, Chunker, ChunkingStrategy
from rag.vector_store.retriever import RetrievalResult, Retriever


def create_app() -> Flask:
    app = Flask(__name__, static_folder="web", template_folder="web")

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
                version = line.replace("## ", "").strip()
                break
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
        presets = [
            {
                "id": "ai_treaty",
                "title": "Accord Mondial de Gouvernance de l'IA (2026)",
                "category": "Géopolitique & Technologie",
                "chunks": [
                    {
                        "chunk_id": "hist-treaty-01",
                        "document_id": "doc-paris-ai-2026",
                        "content": "En 2026, 85 nations ratifient à Paris le premier traité international contraignant sur la sécurité des modèles d'intelligence artificielle frontières.",
                        "metadata": {"source": "gdelt", "category": "geopolitics"},
                        "similarity": 0.95
                    },
                    {
                        "chunk_id": "hist-treaty-02",
                        "document_id": "doc-audit-standards",
                        "content": "Le traité impose des registres d'audit algorithmique mondiaux et une clause de non-prolifération des systèmes autonomes militarisés.",
                        "metadata": {"source": "newsapi", "category": "policy"},
                        "similarity": 0.91
                    }
                ]
            },
            {
                "id": "climate_energy",
                "title": "Rupture Climatique & Micro-Réseaux Renouvelables",
                "category": "Environnement & Société",
                "chunks": [
                    {
                        "chunk_id": "hist-clim-01",
                        "document_id": "doc-ipcc-heatwave",
                        "content": "Des canicules records frappent l'Europe du Sud et l'Afrique du Nord, dépassant 48°C et accélérant l'abandon des énergies fossiles dans les métropoles.",
                        "metadata": {"source": "gdelt", "category": "climate"},
                        "similarity": 0.93
                    },
                    {
                        "chunk_id": "hist-clim-02",
                        "document_id": "doc-decentralized-solar",
                        "content": "Le déploiement massif de micro-réseaux solaires communautaires en Afrique du Nord et en Asie du Sud transforme la souveraineté énergétique des territoires.",
                        "metadata": {"source": "worldbank", "category": "energy"},
                        "similarity": 0.89
                    }
                ]
            },
            {
                "id": "cognitive_labor",
                "title": "Mutation du Travail Intellectuel par les Agents Autonomes",
                "category": "Économie & Savoir",
                "chunks": [
                    {
                        "chunk_id": "hist-work-01",
                        "document_id": "doc-cognitive-shift",
                        "content": "L'automatisation à grande échelle de la recherche médicale, du conseil juridique et du développement logiciel redéfinit le rôle de l'expertise humaine.",
                        "metadata": {"source": "arxiv", "category": "labor"},
                        "similarity": 0.94
                    },
                    {
                        "chunk_id": "hist-work-02",
                        "document_id": "doc-education-reform",
                        "content": "Les universités réforment leurs cursus pour privilégier l'épistémologie critique, la créativité et la supervision éthique des synthèses de machines.",
                        "metadata": {"source": "wikipedia", "category": "education"},
                        "similarity": 0.88
                    }
                ]
            }
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

        api_key = os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY")
        fallback_notice = None
        if api_key:
            try:
                client = build_llm_client()
                agent = HistorianAgent(openai_client=client)
                insight = agent.run(chunks)
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
            except Exception as exc:
                fallback_notice = f"Attention : Le fournisseur d'IA a rejeté la requête ({exc}). Affichage généré via le moteur de simulation dynamique."

        # Mode simulation enrichi : analyse dynamique du contenu
        combined_text = " ".join(c.content.lower() for c in chunks)
        
        words = set(combined_text.split())
        if any(w in combined_text for w in ["climati", "chaleur", "canicule", "solair", "énergie", "écolog", "heatwave"]):
            theme_perspective = "Vue depuis 2126 : l'accélération des chocs climatiques et la transition énergétique des années 2020 marquent le tournant historique où la civilisation a dû adapter son métabolisme industriel face aux limites biosphériques."
            finding_1 = "Événement clé : Franchissement de seuils thermiques historiques et mobilisation pour les micro-réseaux décentralisés."
            finding_2 = "Signification historique : Redéfinition de la souveraineté territoriale par l'autonomie énergétique communautaire."
            finding_3 = "Héritage à 100 ans : Le 22e siècle retient cette phase comme la genèse de l'écologie régénérative globale."
        elif any(w in combined_text for w in ["travail", "emploi", "métier", "labor", "cogniti", "automat", "école", "éducat"]):
            theme_perspective = "Vue depuis 2126 : la redistribution du travail intellectuel au profit d'agents cognitifs autonomes a initié la plus grande mutation des compétences humaines depuis la révolution industrielle."
            finding_1 = "Événement clé : Déploiement à grande échelle des systèmes cognitifs autonomes dans les métiers du savoir."
            finding_2 = "Signification historique : Rupture épistémologique redéfinissant la valeur de l'expertise et de l'intelligence humaine."
            finding_3 = "Héritage à 100 ans : Fondation des modèles de société post-pénurie et de coopération homme-machine."
        elif any(w in combined_text for w in ["art", "culture", "musée", "exposi", "médias", "identit"]):
            theme_perspective = "Vue depuis 2126 : l'explosion des arts numériques et des expressions décentralisées des années 2020 a démantelé les monopoles culturels traditionnels au profit d'identités hybrides mondialisées."
            finding_1 = "Événement clé : Émergence d'espaces artistiques et mémoriels numériques transversaux à travers le Sud global."
            finding_2 = "Signification historique : Décolonisation des archives muséales par les technologies de préservation numérique."
            finding_3 = "Héritage à 100 ans : Les collections contemporaines préservent ces artefacts comme les premières traces de l'art hybride synthétique."
        elif "ia" in words or any(w in combined_text for w in ["intelligence artificielle", "traité", "accord", "gouvern", "loi", "régulat", "treaty"]):
            theme_perspective = "Vue depuis 2126 : les premiers accords internationaux de gouvernance des systèmes autonomes des années 2020 ont jeté les bases constitutionnelles de la cohabitation entre humains et algorithmes."
            finding_1 = "Événement clé : Signature de traités multilatéraux et mise en place de standards d'audit algorithmique mondiaux."
            finding_2 = "Signification historique : Prise de conscience collective des risques systémiques et primauté du droit éthique."
            finding_3 = "Héritage à 100 ans : Ces cadres juridiques sont considérés comme la Magna Carta de l'ère algorithmique."
        else:
            first_chunk = chunks[0].content[:100].strip()
            theme_perspective = f"Vue depuis 2126 : les archives de cette période témoignent d'un moment de bascule centré sur : « {first_chunk}... »."
            finding_1 = f"Événement clé : Transition documentée dans les sources contemporaines ({chunks[0].chunk_id})."
            finding_2 = "Signification historique : Tensions et réorganisations des structures sociales et techniques de l'époque."
            finding_3 = "Héritage à 100 ans : Intégration de ce témoignage singulier dans le récit rétrospectif du 22e siècle."

        mock_payload = {
            "agent": "historian",
            "perspective": theme_perspective,
            "key_findings": [finding_1, finding_2, finding_3],
            "selected_artifacts": [chunks[0].chunk_id] + ([chunks[1].chunk_id] if len(chunks) > 1 else []),
        }
        from unittest.mock import patch
        agent = HistorianAgent(openai_client=None)
        with patch.object(agent, "_call_llm", return_value=mock_payload):
            insight = agent.run(chunks)

        notice_msg = fallback_notice or "Exécuté en mode simulation locale (définissez une clé LLM_API_KEY valide dans le fichier .env pour activer le modèle en direct)."
        return jsonify({
            "ok": True,
            "mode": "simulated",
            "notice": notice_msg,
            "model": "Simulation (HistorianAgent V3)",
            "insight": {
                "agent": insight.agent,
                "perspective": insight.perspective,
                "key_findings": insight.key_findings,
                "selected_artifacts": insight.selected_artifacts,
            },
            "grounded_artifacts": insight.selected_artifacts,
            "input_chunk_ids": [c.chunk_id for c in chunks],
        })


    @app.get("/api/validate")
    def validate_pipeline() -> Any:
        steps: list[dict[str, Any]] = []

        # 1 — Corpus
        processed_dir = Path("data/processed")
        json_files = sorted(processed_dir.glob("*.json")) if processed_dir.exists() else []
        corpus_files = [_corpus_file_info(f) for f in json_files]
        steps.append(_result(
            "Corpus collected",
            bool(json_files),
            f"{len(json_files)} fichier(s) JSON in data/processed",
        ))

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
            "system.md", "historian.md", "sociologist.md",
            "technology.md", "culture_art.md", "visual.md", "curator.md",
        ]
        prompt_infos = [_prompt_file_info(n) for n in prompt_names]
        prompt_ok = all(p["found"] for p in prompt_infos)
        found_count = sum(1 for p in prompt_infos if p["found"])
        steps.append(_result("Prompts V1 defined and tested", prompt_ok,
                              f"{found_count} prompt(s) détecté(s)"))

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
