"""
Test live des agents avec ta clé OpenAI.
Usage: python test_agents_live.py
"""
import os
from dotenv import load_dotenv
from openai import OpenAI

from agents.historian import HistorianAgent
from agents.sociologist import SociologistAgent
from agents.technology import TechnologyAgent
from agents.culture_art import CultureArtAgent
from agents.visual import VisualAgent
from agents.pipeline import run_pipeline
from rag.vector_store.retriever import RetrievalResult

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("[ERREUR] OPENAI_API_KEY non trouvée dans .env")
    raise SystemExit(1)

client = OpenAI(api_key=api_key)

# ── Chunks de test ────────────────────────────────────────────────────────────
CHUNKS = [
    RetrievalResult(
        chunk_id="c1", document_id="d1",
        content="Large language models are transforming scientific research in 2026, enabling new discoveries in biology and physics.",
        metadata={"source": "arxiv", "category": "science"}, similarity=0.92,
    ),
    RetrievalResult(
        chunk_id="c2", document_id="d2",
        content="Climate protests reach 120 countries as record heatwaves break across Europe and North Africa.",
        metadata={"source": "gdelt", "category": "news"}, similarity=0.88,
    ),
    RetrievalResult(
        chunk_id="c3", document_id="d3",
        content="Contemporary art exhibitions in Tunis and Cairo explore post-colonial identity through digital and mixed media.",
        metadata={"source": "wikimedia", "category": "culture"}, similarity=0.85,
    ),
    RetrievalResult(
        chunk_id="c4", document_id="d4",
        content="Quantum computing milestones achieved: first 1000-qubit processor deployed in research labs worldwide.",
        metadata={"source": "arxiv", "category": "science"}, similarity=0.82,
    ),
    RetrievalResult(
        chunk_id="c5", document_id="d5",
        content="Social media regulation bills introduced in 40 countries, reshaping online discourse and misinformation policies.",
        metadata={"source": "wikipedia", "category": "history"}, similarity=0.79,
    ),
]

def sep(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def print_insight(result):
    print(f"  Agent      : {result.agent}")
    print(f"  Perspective: {result.perspective}")
    print(f"  Findings   :")
    for f in result.key_findings:
        print(f"    - {f}")
    print(f"  Artifacts  : {result.selected_artifacts}")

# ── Test 1: Historian Agent ───────────────────────────────────────────────────
sep("1. HISTORIAN AGENT")
try:
    agent = HistorianAgent(openai_client=client)
    result = agent.run(CHUNKS)
    print_insight(result)
except Exception as e:
    print(f"  [ERREUR] {e}")

# ── Test 2: Sociologist Agent ─────────────────────────────────────────────────
sep("2. SOCIOLOGIST AGENT")
try:
    agent = SociologistAgent(openai_client=client)
    result = agent.run(CHUNKS)
    print_insight(result)
except Exception as e:
    print(f"  [ERREUR] {e}")

# ── Test 3: Technology Agent ──────────────────────────────────────────────────
sep("3. TECHNOLOGY AGENT")
try:
    agent = TechnologyAgent(openai_client=client)
    result = agent.run(CHUNKS)
    print_insight(result)
except Exception as e:
    print(f"  [ERREUR] {e}")

# ── Test 4: Culture & Art Agent ───────────────────────────────────────────────
sep("4. CULTURE & ART AGENT")
try:
    agent = CultureArtAgent(openai_client=client)
    result = agent.run(CHUNKS)
    print_insight(result)
except Exception as e:
    print(f"  [ERREUR] {e}")

# ── Test 5: Visual Agent ──────────────────────────────────────────────────────
sep("5. VISUAL AGENT")
try:
    agent = VisualAgent(openai_client=client)
    result = agent.run(CHUNKS)
    print_insight(result)
except Exception as e:
    print(f"  [ERREUR] {e}")

# ── Test 6: Full Pipeline ─────────────────────────────────────────────────────
sep("6. PIPELINE COMPLET (tous agents + curator)")
try:
    synthesis = run_pipeline(CHUNKS, client, timeout_secs=120)
    print(f"  Titre      : {synthesis.exhibition_title}")
    print(f"  Concept    : {synthesis.concept}")
    print(f"  Sections   :")
    for s in synthesis.sections:
        print(f"    [{s.title}]")
        print(f"     {s.narrative[:100]}...")
    print(f"  Items      : {synthesis.selected_items}")
except Exception as e:
    print(f"  [ERREUR] {e}")

print(f"\n{'='*60}")
print("  Tests terminés.")
print('='*60)
