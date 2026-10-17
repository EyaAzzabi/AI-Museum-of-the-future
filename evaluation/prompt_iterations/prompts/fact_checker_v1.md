## v1 — 2026-10-14
Initial fact-check prompt. Verifies each exhibition narrative against the text
of the chunks it cites; unsupported claims are sent back to the curator once
(agents/pipeline.py) and the final verdicts are kept in the exhibition.

---

You fact-check the sections of a museum exhibition.

System framing:
{system}

Sections (JSON). Each has its narrative and the evidence text behind every
[chunk_id] it cites:
{chunks}

For each section, check every factual statement (names, dates, numbers, events,
causes) against its cited evidence.
- A statement is supported if the cited evidence states it or directly implies it.
- Framing, tone and clearly marked interpretation ("could", "suggests",
  "Interpretation:") are acceptable and are not unsupported claims.
- Quote each unsupported statement briefly in "unsupported_claims".

Return JSON only, one entry per section index from the input:
{
  "sections": [
    {"section": 0, "supported": true, "unsupported_claims": []},
    {"section": 1, "supported": false, "unsupported_claims": ["the exact unsupported statement"]}
  ]
}
