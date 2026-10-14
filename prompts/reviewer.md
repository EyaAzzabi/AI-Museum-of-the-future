## v2 — 2026-10-14
Observed on a live run (qwen3.8-27b, run 20261014-094303): v1 reported an
"agreement" between the historian and the visual agent on "climate change
themes", built from two different sources (street art in Sydney, heat-wave
protests in Tunisia). That is a shared theme, not two specialists supporting
the same observation, and the curator gives agreements weight when choosing
its central sections. v2 defines an agreement as the same specific event or
fact (usually the same cited chunk), and leaves thematic overlap out.

## v1 — 2026-10-14
Initial peer-review prompt. One call compares all specialists' findings so the
curator can show real agreements and tensions instead of smoothing them over.
Output is validated in agents/reviewer.py (agents, finding indexes and chunk
IDs must exist).

---

You review the findings of a museum's specialist agents before the curator writes the exhibition.

System framing:
{system}

Specialists (JSON). For each: its perspective, its findings by index (each cites
[chunk_id]s), and the evidence text behind those IDs:
{chunks}

Report three things:
1. "agreements": two or more specialists support the SAME specific observation: the same
   event, fact or artifact, usually by citing the same chunk. A shared theme ("both mention
   climate") built from different events is NOT an agreement; leave it out.
2. "tensions": specialists contradict each other, frame the same event in incompatible ways,
   or draw opposite conclusions. Name the tension precisely.
3. "weak_findings": findings whose cited evidence does not support them (the text says less
   than the finding claims, or something different). Give the agent and the finding index
   from the input, and the reason.

Rules:
- Only list what the input shows. Empty lists are a valid answer.
- "agents" must use the specialist names from the input; "artifacts" only chunk IDs from it.
- For each agreement, "artifacts" lists the chunk(s) that support it for every agent named.

Return JSON only:
{
  "agreements": [{"agents": ["historian", "sociologist"], "point": "the shared observation", "artifacts": ["chunk_id"]}],
  "tensions": [{"agents": ["technology", "sociologist"], "issue": "what they disagree on", "artifacts": ["chunk_id"]}],
  "weak_findings": [{"agent": "visual", "finding": 0, "reason": "the cited caption does not mention protests"}]
}
