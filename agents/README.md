# Agents

Specialized agents that each examine the same retrieved evidence from a different perspective, plus a Curator agent that synthesizes their output into the final exhibition.

Planned agents (per the Week 1 architecture):

- **Historian** — key events, historical significance, long-term impact
- **Sociologist** — social trends, lifestyle changes, human behavior
- **Technology** — innovations, breakthroughs, future potential
- **Culture & Art** — cultural movements, arts & media, symbolic elements
- **Visual** — image analysis, visual curation, mood & aesthetics
- **Curator** — synthesizes all agent insights, selects the most relevant elements, structures the exhibition, writes the coherent narrative

Agents communicate through a shared layer (share insights, cross-validate, build connections) before handing off to the Curator. Architecture choice (orchestrator/router/sequential/hierarchical) and per-agent tool access to be documented here once implemented (Week 3).
