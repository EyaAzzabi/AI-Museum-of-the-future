"""
Test live du Sociologist Agent — Tunisia 2020-2026
===================================================
Author : EyaRachdi
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Fix encoding for Windows
sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

# ── Vérification clé OpenAI ───────────────────────────────────────────────────
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("[ERREUR] OPENAI_API_KEY non trouvée dans .env")
    sys.exit(1)

from openai import OpenAI
from agents.sociologist import SociologistAgent
from rag.vector_store.retriever import RetrievalResult

client = OpenAI(api_key=api_key)

# ── Chunks de test réalistes — Tunisie 2020-2026 ──────────────────────────────
CHUNKS = [
    RetrievalResult(
        chunk_id="c1", document_id="d1",
        content="Tunisia's unemployment rate reached 18% in 2022, with youth unemployment exceeding 40% in rural areas. The economic crisis deepened inequality between urban Tunis and rural regions.",
        metadata={"source": "worldbank", "category": "economy"},
        similarity=0.91,
    ),
    RetrievalResult(
        chunk_id="c2", document_id="d2",
        content="President Kais Saied suspended parliament in July 2021, concentrating executive power and triggering widespread debate about Tunisia's democratic trajectory.",
        metadata={"source": "wikipedia", "category": "politics"},
        similarity=0.88,
    ),
    RetrievalResult(
        chunk_id="c3", document_id="d3",
        content="Tunisian women's rights organizations reported a 30% increase in domestic violence cases during COVID-19 lockdowns in 2020.",
        metadata={"source": "gdelt", "category": "news"},
        similarity=0.85,
    ),
    RetrievalResult(
        chunk_id="c4", document_id="d4",
        content="Irregular migration from Tunisia to Europe surged between 2021-2023, with thousands of young Tunisians attempting the dangerous Mediterranean crossing known as 'harraga'.",
        metadata={"source": "gdelt", "category": "news"},
        similarity=0.83,
    ),
    RetrievalResult(
        chunk_id="c5", document_id="d5",
        content="Social media usage in Tunisia grew 45% between 2020-2024. TikTok became the primary platform for youth political expression, replacing street protest as the main form of civic engagement.",
        metadata={"source": "youtube", "category": "culture"},
        similarity=0.79,
    ),
    RetrievalResult(
        chunk_id="c6", document_id="d6",
        content="Le festival de Carthage 2022 a rassemblé plus de 100,000 spectateurs malgré la crise économique, démontrant la résistance culturelle tunisienne.",
        metadata={"source": "wikimedia", "category": "culture"},
        similarity=0.75,
    ),
]

def sep(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

# ── Lancement du test ─────────────────────────────────────────────────────────
sep("TEST - SOCIOLOGIST AGENT (Tunisia 2020-2026)")
print(f"  Chunks d'entree : {len(CHUNKS)}")
print(f"  Modele LLM      : openai/gpt-oss-120b (Groq)")
print(f"  Mode             : Sans RAG (chunks directs)")

try:
    agent = SociologistAgent(openai_client=None, retriever=None)
    print("\n  Lancement de l'analyse...")
    result = agent.run(CHUNKS)

    sep("RESULTAT")
    print(f"\n  Agent      : {result.agent}")
    print(f"\n  Perspective:\n  {result.perspective}")
    print(f"\n  Findings ({len(result.key_findings)}):")
    for i, f in enumerate(result.key_findings, 1):
        print(f"    {i}. {f}")
    print(f"\n  Artifacts selectionnes : {result.selected_artifacts}")

    sep("TEST REUSSI")

except Exception as e:
    sep("TEST ECHOUE")
    print(f"  Erreur : {e}")
    import traceback
    traceback.print_exc()
