# Agents

Specialized agents that each examine the same retrieved evidence (text + visual context from RAG/multimodal) from a different perspective, feeding into an Orchestrator that synthesizes the final exhibition.

Planned agents (updated architecture, `docs/812254868_1128070259647648_1571835780547333349_n.png`):

- **Socio-Historical Agent** — key events, historical significance, long-term impact, social trends, lifestyle changes, human behavior (merges the earlier Historian + Sociologist split)
- **Science & Technology Agent** — research, innovations, breakthroughs, future potential
- **Culture & Media Agent** — cultural movements, arts & media, symbolic elements
- **Vision Agent** — image analysis, visual curation, mood & aesthetics
- **Orchestrator (n8n + LLM Curator)** — synthesizes all agent insights, selects the most relevant elements, structures the exhibition, writes the coherent narrative. n8n handles the workflow/orchestration mechanics; the LLM Curator does the synthesis.

Agents communicate through a shared **Communication Layer** (share insights, cross-validate, build connections) before handing off to the Orchestrator.

Implemented (see the "Specialist agents" section of the main README):

- `base_agent.py` — the shared design: own hybrid search, evidence formatting, per-finding `[chunk_id]` citation check, abstention, retries, cache, run recording.
- `historian.py`, `sociologist.py` (+ `sociologist_tools.py`, HyDE in `rag/hyde_retriever.py`), `technology.py`, `culture_art.py` (+ `culture_scope.py`), `visual.py` (vision model on evidence images).
- `reviewer.py` — peer review of all insights (agreements, tensions, weak findings).
- `curator.py` — bilingual exhibition with cited narratives; `fact_checker.py` — checks narratives against cited evidence.
- `pipeline.py` — specialists in parallel -> review -> curator -> fact-check; `run_log.py` saves each run to `runs/`.
