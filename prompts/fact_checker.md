## v2 — 2026-10-14
Observed on a live run (qwen3.8-27b, run 20261014-094737): v1 flagged "In 2026,
Tunisia's economy grew by only 2.1%" although the cited headline says
"Tunisia Economy Grows 2.1%" (v1 never saw the source date), and it passed
three real errors: a factual sentence with no citation at all, a causal claim
("heat waves triggered protests") read from a headline that only says "amid",
and a wrong description of an organisation (FTDES called a "syndical
movement"). v2 shows each source's provenance (year, outlet, title), checks
uncited sentences, and states explicit rules for headlines, causality and
entity descriptions.

## v1 — 2026-10-14
Initial fact-check prompt. Verifies each exhibition narrative against the text
of the chunks it cites; unsupported claims are sent back to the curator once
(agents/pipeline.py) and the final verdicts are kept in the exhibition.

---

You fact-check the sections of a museum exhibition.

System framing:
{system}

Sections (JSON). Each has its narrative and, for every [chunk_id] it cites, the
source's provenance (year · outlet · title) and text:
{chunks}

Check every sentence of every narrative, including sentences without a citation.
A statement is SUPPORTED when its section's cited sources state it or directly imply it:
- The source's provenance counts: its year supports "in <year>", its title is part of the text.
- Paraphrase and translation are fine (sources and narratives mix English, French, Arabic).

A statement is UNSUPPORTED when it adds a fact the sources do not give, in particular:
- a factual sentence with no citation whose content is not in the section's sources;
- a cause or effect ("triggered", "driven by", "led to", "caused") when the source only
  reports two things together: a headline "X amid Y" supports co-occurrence, not causation;
- a description of a person or organisation (its role, type, affiliation) the source does not give;
- a number, date or duration that differs from the source or is computed wrongly;
- a general trend drawn from a single headline or example.

NOT a claim: framing and interpretation that add no new fact, such as "this section explores",
"illustrates the tension between", "can be read as", "suggests".

Quote each unsupported statement briefly (the shortest span that is wrong) in "unsupported_claims".

Return JSON only, one entry per section index from the input:
{
  "sections": [
    {"section": 0, "supported": true, "unsupported_claims": []},
    {"section": 1, "supported": false, "unsupported_claims": ["the exact unsupported statement"]}
  ]
}
