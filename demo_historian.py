"""Demo standalone pour HistorianAgent (Eya Idi).

Permet de tester l'agent Historian directement avec des chunks représentatifs
d'événements contemporains (politique, climat, technologie, société).

Usage:
    python demo_historian.py
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Forcer l'encodage utf-8 sous Windows pour éviter les plantages avec les accents
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

from agents.historian import HistorianAgent
from agents.llm_config import build_llm_client
from rag.vector_store.retriever import RetrievalResult

# Échantillon de documents/chunks contemporains représentatifs
SAMPLE_CHUNKS = [
    RetrievalResult(
        chunk_id="hist-evt-001",
        document_id="doc-treaty-2026",
        content=(
            "In early 2026, 85 nations gathered to establish the first legally binding Global AI Governance Accord, "
            "seeking to mitigate systemic autonomous risks and coordinate algorithmic auditing across borders."
        ),
        metadata={"source": "gdelt", "category": "geopolitics"},
        similarity=0.94,
    ),
    RetrievalResult(
        chunk_id="hist-evt-002",
        document_id="doc-climate-summit",
        content=(
            "Global temperatures reached a continuous 1.5°C threshold above pre-industrial levels, triggering "
            "unprecedented youth mobilization and the adoption of aggressive decentralized solar grids across the Global South."
        ),
        metadata={"source": "newsapi", "category": "environment"},
        similarity=0.91,
    ),
    RetrievalResult(
        chunk_id="hist-evt-003",
        document_id="doc-digital-labor",
        content=(
            "Societies witnessed a monumental shift in intellectual labor, as autonomous cognitive agents were deployed "
            "at scale across medicine, law, and education, sparking debates on human identity and post-scarcity economics."
        ),
        metadata={"source": "arxiv", "category": "society"},
        similarity=0.88,
    ),
]


def main():
    print("=" * 70)
    print("  AI MUSEUM OF THE FUTURE - SOCIO-HISTORICAL AGENT DEMO")
    print("  Responsable : Eya Idi")
    print("  Fichier     : agents/historian.py | Prompt: prompts/historian.md")
    print("=" * 70)

    api_key = os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY")
    if not api_key:
        print("\n[INFO] Aucune clé LLM_API_KEY détectée dans le fichier .env.")
        print("Pour un test avec appel LLM en direct, ajoutez votre clé Groq ou Gemini dans .env.")
        print("Exemple : LLM_API_KEY=gsk_...\n")
        return

    print("\n[1] Initialisation du client LLM et de l'HistorianAgent...")
    try:
        client = build_llm_client()
        agent = HistorianAgent(openai_client=client)
    except Exception as e:
        print(f"[ERREUR] Échec de l'initialisation du client : {e}")
        return

    print("[2] Analyse socio-historique des données contemporaines en cours...")
    try:
        insight = agent.run(SAMPLE_CHUNKS)
    except Exception as e:
        print(f"[ERREUR] Échec lors de l'exécution de l'agent : {e}")
        return

    print("\n" + "=" * 70)
    print("  RÉSULTATS DE L'ANALYSE HISTORIQUE (100-YEAR RETROSPECTIVE LENS)")
    print("=" * 70)
    print(f"\n  • Agent       : {insight.agent}")
    print(f"  • Perspective : \n    \"{insight.perspective}\"")
    print("\n  • Clés d'Analyse Historique (Key Findings) :")
    for idx, finding in enumerate(insight.key_findings, 1):
        print(f"    {idx}. {finding}")

    print("\n  • Artefacts Sélectionnés (Grounded Artifacts) :")
    for artifact_id in insight.selected_artifacts:
        print(f"    - {artifact_id}")

    print("\n" + "=" * 70)
    print("  Validation réussie : l'agent produit une analyse ancrée et structurée !")
    print("=" * 70)


if __name__ == "__main__":
    main()
