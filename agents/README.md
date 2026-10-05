# Agents

Specialized agents that each examine the same retrieved evidence (text + visual context from RAG/multimodal) from a different perspective, feeding into an Orchestrator that synthesizes the final exhibition.

Planned agents (updated architecture, `docs/812254868_1128070259647648_1571835780547333349_n.png`):

- **Socio-Historical Agent** — key events, historical significance, long-term impact, social trends, lifestyle changes, human behavior (merges the earlier Historian + Sociologist split)
- **Science & Technology Agent** — research, innovations, breakthroughs, future potential
- **Culture & Media Agent** — cultural movements, arts & media, symbolic elements
- **Vision Agent** — image analysis, visual curation, mood & aesthetics
- **Orchestrator (n8n + LLM Curator)** — synthesizes all agent insights, selects the most relevant elements, structures the exhibition, writes the coherent narrative. n8n handles the workflow/orchestration mechanics; the LLM Curator does the synthesis.

Agents communicate through a shared **Communication Layer** (share insights, cross-validate, build connections) before handing off to the Orchestrator. Per-agent tool access and the exact orchestration pattern (sequential/parallel handoff to the Orchestrator) to be documented here once implemented (Week 3).
