# Sociologist Agent — AI Museum of the Future
**Author:** EyaRachdi  
**Branch:** `EyaRachdi_sociologistAgent`  
**Model:** `openai/gpt-oss-120b` via Groq (free)  
**Case:** Tunisia 2020–2026

---

## Objectif

Analyser la société tunisienne contemporaine (2020–2026) à travers une perspective sociologique,
identifier les transformations sociales clés, et produire des insights structurés pour l'exposition
virtuelle du musée.

> *"If a museum were created in 100 years to represent our time, what would it preserve about Tunisian society?"*

---

## Architecture complète

```
agents/
├── sociologist.py           # Agent principal — workflow 7 étapes
├── sociologist_tools.py     # 8 outils RAG et analyse

rag/
└── hyde_retriever.py        # Advanced RAG pipeline (HyDE)

prompts/
└── sociologist.md           # Prompt library v2 (Role + CoT + Few-shot)

tests/
└── test_sociologist.py      # 30 tests (unit + integration + evaluation + live)

test_sociologist_live.py     # Script de test live (Groq)
```

---

## Phase 1 — SCOPE

| Paramètre | Valeur |
|---|---|
| Pays | Tunisie |
| Période | 2020–2026 |
| Langues | Français + Anglais |
| Thèmes | 10 thèmes sociaux |
| Objectif | Insights museum-ready pour le Curator Agent |

---

## Phase 2 — SELECT

| Composant | Choix | Justification |
|---|---|---|
| LLM | `openai/gpt-oss-120b` via Groq | Gratuit, performant, JSON structuré |
| RAG | Advanced RAG + HyDE | Vocabulary gap entre requêtes abstraites et corpus concret |
| Embeddings | `all-MiniLM-L6-v2` local | Gratuit, pas de quota, 384 dims |
| Vector DB | Supabase pgvector | Gratuit, natif n8n, SQL familier |

---

## Phase 3 — ALIGN (Prompt Engineering)

### Techniques utilisées

| Technique | Description | Où |
|---|---|---|
| **Role Prompting** | Persona "Dr. Amira" — sociologue spécialisée Afrique du Nord | `sociologist.md` system prompt |
| **Chain of Thought** | 5 étapes de raisonnement avant l'output | `sociologist.py` `_build_system_prompt()` |
| **Few-shot Example** | Exemple concret d'un bon finding sociologique | `FEW_SHOT_EXAMPLE` constant |
| **Structured Output** | JSON schema strict avec 8 champs requis | `prompts/sociologist.md` |
| **Self-consistency** | L'agent valide et corrige son propre output | `_validate_and_fix()` |
| **Context Injection** | Chunks RAG formatés et injectés dans le prompt | `format_chunks_for_prompt()` |

---

## Phase 4 — APPLICATION INTEGRATION (Advanced RAG + HyDE)

### Pourquoi HyDE ?

Le problème du RAG classique : une requête abstraite *"inégalités sociales"* trouve difficilement
les chunks concrets *"chômage 40% zones rurales"* — le vocabulary gap réduit la similarité vectorielle.

**HyDE résout ça** : le LLM génère d'abord un document hypothétique qui utilise le même
langage concret que le corpus, puis on cherche les chunks similaires à ce document.

### Pipeline HyDE (rag/hyde_retriever.py)

```
Query: "gender_women Tunisia"
         |
         v
Step 1 — Query Expansion
"Tunisia women rights domestic violence gender equality
 feminist lockdown pandemic harraga..."
         |
         v
Step 2 — Generation document hypothetique (LLM)
"En Tunisie, les violences domestiques ont augmente
 de 30% pendant le confinement COVID de 2020..."
         |
         v
Step 3 — Vector Retrieval (Supabase)
Recherche chunks similaires au document hypothetique
         |
         v
Step 4 — Reranking
Score = 70% similarite vectorielle + 30% keywords
         |
         v
Step 5 — Context Injection dans prompt CoT
Top 20 chunks injectes dans le prompt de Dr. Amira
```

---

## Workflow de l'agent (7 étapes)

```
Input chunks (RAG ou direct)
         |
         v
1. Definir l'objectif        <- AGENT_OBJECTIVE constant
         |
         v
2. Choisir le modele         <- openai/gpt-oss-120b via Groq
         |
         v
3. Fournir les connaissances <- HyDE Advanced RAG (Supabase)
         |
         v
4. Outils & actions          <- 8 tools dans sociologist_tools.py
         |
         v
5. Workflow & instructions   <- Chain of Thought + Role + Few-shot
         |
         v
6. Tester & valider          <- _validate_and_fix() + self-check
         |
         v
7. Retourner InsightObject   <- perspective + key_findings + artifacts
```

---

## Outils disponibles (sociologist_tools.py)

| Outil | Description |
|---|---|
| `retrieve_social_evidence` | Query Supabase par theme social |
| `filter_by_theme` | Filtre chunks par keywords thematiques |
| `filter_by_source` | Filtre par source (gdelt, wikipedia...) |
| `compute_theme_coverage` | Compte chunks par theme |
| `extract_dates` | Extrait la plage temporelle des chunks |
| `format_chunks_for_prompt` | Formate les chunks pour injection LLM |
| `score_evidence_relevance` | Score combine (similarite + keywords) |
| `build_evidence_bundle` | Pipeline complet de recuperation |

---

## 10 Thèmes sociaux analysés (Tunisia)

1. `politics_civic` — Politique, elections, droits civiques
2. `economy_inequality` — Chomage, inflation, pauvrete
3. `gender_women` — Droits des femmes, violence, egalite
4. `youth_education` — Jeunesse, education, avenir
5. `migration_diaspora` — Migration, harraga, diaspora
6. `culture_identity` — Culture, identite, patrimoine
7. `religion_secularism` — Islam, laicite, liberte de culte
8. `environment_urban` — Eau, secheresse, urbanisation
9. `health_wellbeing` — Sante, COVID, bien-etre
10. `digital_social_media` — Internet, reseaux sociaux, tech

---

## Output — InsightObject (exemple réel obtenu)

```python
InsightObject(
    agent="sociologist",
    perspective=(
        "The early 2020s in Tunisia were marked by a rapid re-centralization "
        "of political power, soaring youth unemployment, and a digital turn "
        "that reshaped how citizens voiced dissent... "
        "[Themes: politics_civic, economy_inequality, gender_women] "
        "[Evidence: 6 chunks | Confidence: 92%]"
    ),
    key_findings=[
        "Kais Saied's July 2021 suspension of parliament accelerated a shift "
        "toward executive authoritarianism, reflecting popular fatigue with "
        "fragmented politics.",
        "Youth unemployment surged to over 40% in rural areas by 2022, "
        "deepening the urban-rural economic divide and fueling irregular migration.",
        "Domestic violence reports rose 30% during the 2020 COVID-19 lockdowns, "
        "exposing heightened gender-based vulnerability.",
        "Social media usage grew 45% with TikTok becoming the primary platform "
        "for youth political expression, replacing street protests.",
        "The 2022 Carthage Festival attracted 100,000 spectators despite the "
        "economic crisis, illustrating cultural resilience.",
    ],
    selected_artifacts=["c2", "c5", "c1", "c3"],
)
```

---

## Tests

```bash
# Tests unitaires et integration (sans cle LLM)
pytest tests/test_sociologist.py -v -m "not live"

# Test live avec Groq (necessite LLM_API_KEY dans .env)
python test_sociologist_live.py
```

**Resultats :** 30/30 tests passent

| Classe | Tests | Description |
|---|---|---|
| `TestSociologistTools` | 10 | Tests unitaires des 8 outils |
| `TestSociologistAgent` | 14 | Tests d'integration du workflow |
| `TestSociologistOutputQuality` | 6 | Tests de qualite de l'output |
| `TestSociologistLive` | 1 | Test live (skippe sans cle) |

---

## Évaluation du système

| Critère | Résultat |
|---|---|
| Confidence score | 92% sur chunks Tunisia |
| Findings produits | 5 findings spécifiques et sourcés |
| Couverture thématique | 5/10 thèmes détectés sur 6 chunks |
| Tests unitaires | 30/30 |
| Fallback sur erreur LLM | Oui — retourne InsightObject valide |
| Retry LLM | 3 tentatives avec backoff exponentiel |

---

## Sécurité

- Aucune clé API dans le code — tout via `.env` (gitignored)
- Fallback automatique si LLM échoue
- Validation et correction de l'output avant retour
- Secrets jamais loggués ni affichés

---

## Installation et utilisation

```bash
# 1. Cloner et installer
git clone https://github.com/EyaAzzabi/AI-Museum-of-the-future.git
git checkout EyaRachdi_sociologistAgent
pip install -r requirements.txt

# 2. Configurer .env
cp .env.example .env
# Ajouter: LLM_API_KEY=gsk_... (cle Groq gratuite)

# 3. Lancer le test live
python test_sociologist_live.py

# 4. Lancer les tests unitaires
pytest tests/test_sociologist.py -v -m "not live"
```

```python
# Utilisation dans le code
from agents.sociologist import SociologistAgent
from agents.llm_config import build_llm_client

llm_client = build_llm_client()  # Groq
agent = SociologistAgent(openai_client=llm_client, retriever=None)
result = agent.run(chunks)

print(result.perspective)   # Framing sociologique
print(result.key_findings)  # 4-6 findings specifiques
```

---

## Références

- HyDE: Gao et al. (2022) *"Precise Zero-Shot Dense Retrieval without Relevance Labels"* — https://arxiv.org/abs/2212.10496
- Chain of Thought: Wei et al. (2022) *"Chain-of-Thought Prompting Elicits Reasoning in Large Language Models"*
- Role Prompting: White et al. (2023) *"A Prompt Pattern Catalog to Enhance Prompt Engineering"*
