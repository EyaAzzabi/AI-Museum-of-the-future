# Sociologist Agent — AI Museum of the Future
**Author:** EyaRachdi  
**Branch:** `EyaRachdi_sociologistAgent`  
**Model:** `gpt-4o-mini`  
**Case:** Tunisia 2020–2026

---

## Objectif

Analyser la société tunisienne contemporaine (2020–2026) à travers une perspective sociologique,
identifier les transformations sociales clés, et produire des insights structurés pour l'exposition
virtuelle du musée.

> *"If a museum were created in 100 years to represent our time, what would it preserve about Tunisian society?"*

---

## Architecture

```
agents/
├── sociologist.py           # Agent principal — workflow 7 étapes
├── sociologist_tools.py     # 8 outils RAG et analyse

prompts/
└── sociologist.md           # Prompt library v2 (Role + CoT + Few-shot)

tests/
└── test_sociologist.py      # 30 tests (unit + integration + evaluation + live)
```

---

## Prompt Engineering — Techniques utilisées

| Technique | Description | Où |
|---|---|---|
| **Role Prompting** | Persona "Dr. Amira" — sociologue spécialisée Afrique du Nord | `sociologist.md` system prompt |
| **Chain of Thought** | 5 étapes de raisonnement avant l'output | `sociologist.py` `_build_system_prompt()` |
| **Few-shot Example** | Exemple d'un bon finding sociologique | `FEW_SHOT_EXAMPLE` constant |
| **Structured Output** | JSON schema strict avec 8 champs | `prompts/sociologist.md` |
| **Self-consistency** | L'agent valide et corrige son propre output | `_validate_and_fix()` |
| **Context Injection** | Chunks RAG formatés et injectés dans le prompt | `format_chunks_for_prompt()` |

---

## Workflow de l'agent (7 étapes)

```
Input chunks (RAG ou direct)
         │
         ▼
1. Définir l'objectif        ← AGENT_OBJECTIVE constant
         │
         ▼
2. Choisir le modèle         ← gpt-4o-mini (LLM_MODEL)
         │
         ▼
3. Fournir les connaissances ← RAG retrieval (Supabase) + merge chunks
         │
         ▼
4. Outils & actions          ← 8 tools dans sociologist_tools.py
         │
         ▼
5. Workflow & instructions   ← Chain of Thought + Role + Few-shot
         │
         ▼
6. Tester & valider          ← _validate_and_fix() + self-check
         │
         ▼
7. Retourner InsightObject   ← perspective + key_findings + artifacts
```

---

## Outils disponibles (sociologist_tools.py)

| Outil | Description |
|---|---|
| `retrieve_social_evidence` | Query Supabase par thème social |
| `filter_by_theme` | Filtre chunks par keywords thématiques |
| `filter_by_source` | Filtre par source (gdelt, wikipedia...) |
| `compute_theme_coverage` | Compte chunks par thème |
| `extract_dates` | Extrait la plage temporelle des chunks |
| `format_chunks_for_prompt` | Formate les chunks pour injection LLM |
| `score_evidence_relevance` | Score combiné (similarité + keywords) |
| `build_evidence_bundle` | Pipeline complet de récupération |

---

## Thèmes sociaux analysés (Tunisia)

1. `politics_civic` — Politique, élections, droits civiques
2. `economy_inequality` — Chômage, inflation, pauvreté
3. `gender_women` — Droits des femmes, violence, égalité
4. `youth_education` — Jeunesse, éducation, avenir
5. `migration_diaspora` — Migration, harraga, diaspora
6. `culture_identity` — Culture, identité, patrimoine
7. `religion_secularism` — Islam, laïcité, liberté de culte
8. `environment_urban` — Eau, sécheresse, urbanisation
9. `health_wellbeing` — Santé, COVID, bien-être
10. `digital_social_media` — Internet, réseaux sociaux, tech

---

## Output — InsightObject

```python
InsightObject(
    agent="sociologist",
    perspective="Tunisia's 2020-2026 period was defined by... [Themes: ...] [Confidence: 82%]",
    key_findings=[
        "The 2021 constitutional crisis revealed Tunisia's democratic fatigue...",
        "Youth unemployment exceeding 40% created a generation with no economic future...",
        "COVID-19 lockdowns amplified gender inequalities, domestic violence rising 30%...",
        "Social media replaced street protest as youth political expression...",
        "Cultural sector maintained vitality as social resilience infrastructure...",
    ],
    selected_artifacts=["chunk_id_1", "chunk_id_2", "chunk_id_3"],
)
```

---

## Tests

```bash
# Tous les tests (sans appel LLM réel)
pytest tests/test_sociologist.py -v -m "not live"

# Avec appel LLM réel (nécessite OPENAI_API_KEY)
pytest tests/test_sociologist.py -v -m live
```

**Résultats :** 30/30 tests passent ✅

| Classe | Tests | Description |
|---|---|---|
| `TestSociologistTools` | 10 | Tests unitaires des 8 outils |
| `TestSociologistAgent` | 14 | Tests d'intégration du workflow |
| `TestSociologistOutputQuality` | 6 | Tests de qualité de l'output |
| `TestSociologistLive` | 1 | Test live (skippé sans clé) |

---

## Utilisation

```python
from agents.sociologist import SociologistAgent
from openai import OpenAI

# Mode direct (sans RAG)
client = OpenAI(api_key="sk-...")
agent = SociologistAgent(openai_client=client)
result = agent.run(chunks)

# Mode complet (avec RAG)
from rag.vector_store.retriever import Retriever
retriever = Retriever(supabase_client, openai_client)
agent = SociologistAgent(openai_client=client, retriever=retriever)
result = agent.run(chunks)

print(result.perspective)
print(result.key_findings)
```
