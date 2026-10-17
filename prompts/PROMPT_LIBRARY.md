# Prompt Library — AI Museum of the Future

Standalone deliverable for the Advanced Deep Learning final project (Esprit 2026-2027, 5DS).
For every prompt of the system it documents its role, the techniques it uses, the failures
we observed, how we fixed them, and at least one before/after iteration. Prompt files live
in [`prompts/`](.); each starts with a version changelog that is stripped before the prompt
is sent to the model.

**How to read the evidence.** We distinguish three kinds of evidence, and say which one
each claim rests on:

- **Observed live**: seen in a real run against the Supabase corpus and a real LLM
  (Groq: `openai/gpt-oss-120b`, `openai/gpt-oss-20b` or `qwen/qwen3.8-27b`). Runs are
  saved by `agents/run_log.py`; the inputs of the run used for the measured comparisons
  are committed in [`evaluation/prompt_iterations/`](../evaluation/prompt_iterations/).
- **Measured**: a before/after comparison on fixed inputs, same model, only the prompt
  changed ([`evaluation/compare_prompt_versions.py`](../evaluation/compare_prompt_versions.py)).
  Each version ran once: LLM outputs vary between runs, so small differences are not significant.
- **Found by reading code or tests**: a defect identified without a live run. Stated as such.

**Measured before/after on a live run (same input, same model, one run each):**

| Prompt | Before | After |
|---|---|---|
| Fact-checker v1 → v2 | 5/10 and 6/10 annotated statements judged correctly (missed causal claims and an uncited sentence; one false alarm) | 9/10 (one miss), but stricter on interpretive sentences |
| Peer reviewer v1 → v2 | a theme-only "agreement" in both runs | none; the real shared-evidence agreement kept |
| Curator v5 → v6 | 11 statements flagged in 3 of 5 sections by the fact-checker | not measured yet (free-tier limits, section 3.1) |

---

## 1. Overview

| Prompt | File | Used by | Main techniques | Versions |
|---|---|---|---|---|
| System framing | `system.md` | all agents (shared framing) | role prompting | v1 |
| Historian | `historian.md` + system prompt in `agents/historian.py` | specialist | role (archivist in 2126), structured analytical framework, structured output, grounding guardrails, output language control (French) | v1 → v4 |
| Sociologist | `sociologist.md` + system prompt in `agents/sociologist.py` | specialist | role ("Dr. Amira"), chain-of-thought steps, few-shot example, structured output, self-check | v1 → v3 |
| Technology | `technology.md` | specialist | role, fact vs. interpretation, citation guardrail, structured output | v1 → v2 |
| Culture & Art | `culture_art.md` (+ `culture_art_v1.md`, `culture_art_v2.md`) | specialist | role, untrusted-data guardrail (prompt injection), few-shot positive + abstention examples, evidence-granularity rules, structured output | v1 → v5 |
| Visual | `visual.md` | specialist (multimodal) | role, grounding in vision-model descriptions, citation guardrail | v1 → v2 |
| Peer reviewer | `reviewer.md` | agent-to-agent critique | role, explicit definitions, structured output | v1 → v2 |
| Curator | `curator.md` | synthesis | role, explicit constraints (4-6 sections, arc, length), structured output, citation guardrail, bilingual output, retry with feedback | v1 → v6 |
| Fact-checker | `fact_checker.md` | verification of the curator | role, explicit decision rules, structured output | v1 → v2 |
| HyDE generator | in `rag/hyde_retriever.py` | sociologist retrieval | hypothetical document generation | 2 iterations (parameters) |
| Relevance reranker | in `rag/vector_store/retriever.py` | hybrid search | LLM-as-judge scoring, structured output | v1 |
| Culture screening | in `rag/vector_store/culture_reranker.py` | Culture & Art retrieval | graded rubric (0-3), verbatim-quote guardrail, injection guardrail | v5 → v5.2 |
| Image description | in `multimodal/analyze_image.py` | visual agent | multimodal (image + text) prompting | v1 (parser fixed) |
| Faithfulness judge | in `evaluation/evaluate_run.py` | evaluation | LLM-as-judge, structured output | v1 |

## 2. Conventions shared by all agent prompts

These were introduced after failures and apply to every specialist (enforced in
[`agents/base_agent.py`](../agents/base_agent.py)):

1. **Evidence is shown with its ID and provenance.** Each evidence line reads
   `[chunk_id] (year · source/category · title) text`. *Why:* in the first integrated
   live run the agents were shown chunk text only, so they could not cite real sources
   and invented artifact IDs (section 3.7).
2. **Every finding cites its source** as `[chunk_id]`. The code keeps a finding only if it
   cites at least one ID and every cited ID is in the agent's evidence; otherwise the
   finding is dropped. With nothing left, the agent **abstains** and the curator reports
   the perspective as missing. *Why:* generic default findings ("Historical themes
   identified from the corpus") and padded filler ("Additional social pattern 4 — requires
   more evidence") were passed to the curator as if they were analysis (found by reading
   code during integration).
3. **Structured output.** All agents call the model in JSON mode and the code validates the
   schema; prompts end with a literal JSON template.
4. **Guardrails in code, not only in the prompt.** Prompts ask for real IDs, the code
   checks them. A prompt instruction alone was not enough (sections 3.4 and 3.7).
5. **Retrieved text is data, not instructions.** Culture & Art, the screening prompt and the
   reviewer state this explicitly (prompt-injection guardrail).
6. **Changelog headers are stripped** before sending: they document the prompt for us,
   and would only cost tokens and distract the model.

---

## 3. Prompts

### 3.1 Curator — `curator.md` (v1 → v6)

**Role.** Turns the five specialist insights (plus their cross-references and the peer
review) into the exhibition: a bilingual title and concept, 4-6 sections with cited
narratives, and the selected artifacts. Called by `agents/curator.py`; the code validates
the output and retries up to 3 times with feedback.

**Techniques.** Role prompting (chief curator writing for a general audience), explicit
constraints (section count, narrative arc, 60-120 words), structured output with a literal
JSON template, citation guardrail (only IDs from `evidence`), bilingual output rules,
use of agent-to-agent signals (`review.agreements`, `review.tensions`, `review.weak_findings`).

| Version | Change | Trigger | Evidence |
|---|---|---|---|
| v1 → v2 | State "between 4 and 6 sections"; example shows 5 placeholders instead of 2 | Live run: output had 2-3 sections and failed the code's 4-6 check. The model copied the example's shape, the count was stated nowhere. | Observed live; v2 confirmed on the same input that failed |
| v3 | Build on cross-references, show disagreements, report unavailable perspectives, narrative arc and length; code retries with feedback | Design iteration (no single failure) | — |
| v4 | Bilingual: title and concept EN / FR, each section in the language of its main perspective | Team decision: the historian writes in French | Observed live: historian-led sections in French, the others in English |
| v5 | Narratives cite `[chunk_id]`; the prompt now carries the text behind each cited ID and the peer review | Live run: the exhibition listed invented "artifacts" (`Startup Act 2018`, `2022 Carthage Film Festival poster – migration theme`) and the parliament section cited the youth-unemployment chunk (`tn-2`) instead of the parliament chunk (`tn-1`) | Observed live; after the fix two live runs had only real IDs and correct section citations |
| v5 (prompt size) | Evidence snippets 300 → 180 characters, redundant artifact lists removed | Live run: prompt of 8,177 tokens exceeded the free tier's 8,000 tokens per minute | Observed live; the same inputs then went through |
| v6 | Evidence-granularity rules; no uncited factual sentence | Fact-checker flagged embellishments of headlines in 3 of 5 v5 sections (see below) | Not measured yet: the v5/v6 comparison was blocked by free-tier limits (qwen3.8-27b: 1,000 output tokens per minute; gpt-oss-120b: daily tokens used up). Run `python -m evaluation.compare_prompt_versions --only curator` |

**Before → after (v5 → v6), the rule that changed:**

```text
v5: - Cite sources in every narrative: put the exact [chunk_id] after each factual
      sentence ... state only what that evidence text says.

v6: - (same) ... A sentence without a citation may only frame or connect
      ("this section explores..."), never state a fact.
    - Most evidence items are headlines or short excerpts. A headline supports only what
      it states: "X amid Y" means X and Y happened together, not that Y caused X. Do not
      add causes, effects, figures, durations or descriptions of people and organisations
      that the evidence does not give, and do not turn one headline into a general trend.
      Mark interpretation as interpretation ("can be read as", "suggests").
```

What v5 wrote from the headline *"Protests in Libya, Tunisia Amid Extreme Heat Wave"*:
"extreme heat waves **triggered** visible protests ... rising temperatures **directly
precipitated** public grievance, linking environmental vulnerability to the **breakdown of
social order**". Other v5 embellishments: FTDES (an NGO) described as "the national
syndical movement"; "onze ans après la révolution" in 2026 (it was fifteen years);
"the administrative decentralisation failed to prevent the collapse" from a headline about
an electricity crisis.

**Before → after (v1 → v2), the example that the model copied:**

```text
v1: "sections": [ {"title": "Section 1 title", ...}, {"title": "Section 2 title", ...} ]
v2: "Between 4 and 6 sections (inclusive), no fewer, no more." + 5 example sections
```

### 3.2 Fact-checker — `fact_checker.md` (v1 → v2)

**Role.** After the curator, checks every narrative against the text of the chunks it cites.
Unsupported statements go back to the curator once; the final verdicts are stored in the
exhibition (`ExhibitionSynthesis.fact_check`). Called by `agents/fact_checker.py`.

**Techniques.** Role prompting, explicit decision rules (what counts as supported /
unsupported / not a claim), structured output per section, validated in code (a section the
model does not return is reported as unchecked, never as supported).

**Failure observed live (v1, qwen3.8-27b).** On the curator v5 exhibition above, v1 flagged
11 statements. Annotated against the sources (10 statements, `annotations.json`), v1 was right
on 5 of 10:
- **false alarm:** "In 2026, Tunisia's economy grew by only 2.1%" — the cited headline is
  "Tunisia Economy Grows 2.1% as Debt Crowds Out Firms" (dated 2026). v1 received only the
  text, not the date;
- **missed:** the causal claim "heat waves triggered protests" (headline says "amid"), the
  "breakdown of social order", FTDES described as a "syndical movement", and a factual
  sentence with no citation at all ("structural deficits and long-term unemployment persisted").

**Fix (v2).** The prompt receives each source's provenance (year · outlet · title), checks
sentences without a citation, and gives explicit rules for headlines ("X amid Y" is
co-occurrence), causality, descriptions of people and organisations, numbers and durations,
and what is *not* a claim (framing, marked interpretation).

**Before → after (decision rules):**

```text
v1: - A statement is supported if the cited evidence states it or directly implies it.
    - Framing, tone and clearly marked interpretation are acceptable.

v2: Check every sentence ..., including sentences without a citation.
    SUPPORTED ... The source's provenance counts: its year supports "in <year>" ...
    UNSUPPORTED ... in particular:
    - a factual sentence with no citation whose content is not in the section's sources;
    - a cause or effect ("triggered", "driven by", "led to") when the source only reports
      two things together: a headline "X amid Y" supports co-occurrence, not causation;
    - a description of a person or organisation the source does not give;
    - a number, date or duration that differs from the source or is computed wrongly;
    - a general trend drawn from a single headline or example.
```

**Measured (same exhibition, same model, one run each):**

| | Correct on 10 annotated statements | Missed errors | False alarms | Statements flagged in total |
|---|---|---|---|---|
| v1, live run | 5 / 10 | A, B, F, H | E (the 2.1% figure) | 11 |
| v1, rerun | 6 / 10 | A, B, F, H | — | 6 |
| **v2** | **9 / 10** | F | — | 19 |

(A, B: causal claims from an "amid" headline; F: FTDES described as a syndical movement;
H: uncited sentence on unemployment; E: the 2.1% figure. Full list in `annotations.json`.)

v2 catches the causal claims and the uncited sentence and no longer flags the dated figure.
**What v2 still gets wrong:** it misses the FTDES description (F); it flags more statements
overall, including some interpretive sentences its own rules exempt ("these works illustrate
how communities visually processed the 'dangerous twilight' of their time"); and both v1 and
v2 flagged "Friederike Otto emphasised that heatwaves are the most affected by climate change",
although the cited Arabic headline says exactly that (a cross-language false alarm that our
10-statement annotation did not include). Next iteration: separate "unsupported fact" from
"interpretation" in the output, and test translated sources explicitly.

### 3.3 Peer reviewer — `reviewer.md` (v1 → v2)

**Role.** Agent-to-agent communication step: one call reads all specialist insights side by
side and returns agreements, tensions and weak findings, which the curator uses. Called by
`agents/reviewer.py`; the code drops any agent, finding index or chunk ID that does not exist.

**Techniques.** Role prompting (fair, precise reviewer), explicit definitions of each output
category, structured output; one call instead of one critique per specialist (cost).

**Failure observed live (v1).** v1 reported an "agreement" between the historian and the
visual agent on "climate change themes", built from two different sources (street art in
Sydney; heat-wave protests in Tunisia). That is a shared theme, not two specialists supporting
the same observation, and the curator gives agreements weight when choosing its central
sections. The other v1 outputs were useful: a real historian/sociologist tension (global
"twilight of democracies" vs. internal stagnation) and two weak findings whose reasons were
correct (e.g. the sociologist's "digital exclusion from the labour market" cites only an
internet-usage figure).

**Before → after:**

```text
v1: "agreements": points where two or more specialists independently support the same
    observation (same event, trend or artifact).
v2: "agreements": two or more specialists support the SAME specific observation: the same
    event, fact or artifact, usually by citing the same chunk. A shared theme ("both mention
    climate") built from different events is NOT an agreement; leave it out.
    For each agreement, "artifacts" lists the chunk(s) that support it for every agent named.
```

**Measured (same insights, same model, one run each).** An agreement counts as
"shared evidence" when one of its chunks is cited by two of the agents it names.

| | Agreements backed by a chunk two agents cite | Theme-only agreements | Tensions | Weak findings |
|---|---|---|---|---|
| v1, live run | 1 (electricity crisis 2026) | 1 (climate: Sydney street art + heat-wave protests) | 1 | 2 |
| v1, rerun | 1 (same) | 1 (same climate overlap again) | 1 | 3 |
| **v2** | 1 (same) | **0** | 1 | 4 |

The theme-only agreement appeared in both v1 runs and disappeared with v2, while the real
agreement was kept. One of v2's weak findings is a multimodal catch: the visual agent's claim
that a photograph "documents a protest" is not supported, because the vision description shows
men in swim trunks on a street, not a protest. The tension found changed between runs (v1 live: historian vs. sociologist; v1 rerun: culture
and art vs. historian and sociologist; v2: technology's "technological maturation" vs. the
historian's and sociologist's crisis framing), which illustrates the run-to-run variance noted
in section 6.

### 3.4 Historian — `historian.md` + system prompt in `agents/historian.py` (v1 → v4)

**Role.** Socio-historical specialist: key events, their significance, and how 2126 will
remember them. Writes in French (the curator keeps it bilingual).

**Techniques.** Role prompting (archivist-historian in the 22nd century), a three-pillar
analytical framework (Événement clé / Portée historique / Impact à l'échelle d'un siècle) as
structured reasoning, structured output, output-language control, grounding guardrails.

| Version | Change | Trigger | Evidence |
|---|---|---|---|
| v1 | Skeleton | — | — |
| v2 | Focus on turning points and long-term trajectory, not news summaries | The agent sometimes invented artifact IDs | Observed by the author (Eya) |
| v3 | Three-pillar framework, 100-year distance, "select ONLY chunk IDs present in the evidence", French output | Same invented IDs | The code then filtered invented IDs, but the shared renderer still showed no IDs, so the model could not cite real ones and the code silently fell back to the first 3 chunks (found by reading code during integration) |
| v4 | Every finding ends with `[chunk_id]`; evidence lines show `(year · source/category · title)` | Shared citation contract | Observed live: once IDs were shown (still v3), the live endpoint on the Tunisian presets selected exactly the three preset chunks; with v4, the qwen run kept 5 of 5 cited findings |

**Before → after (v3 → v4):**

```text
v3: - For "selected_artifacts", choose ONLY chunk IDs that appear explicitly in the evidence.
v4: + Chaque finding se termine par l'identifiant exact de sa source entre crochets,
      par ex. « ... [chunk_id] ». Un finding sans citation valide est supprimé.
```

**Open issue (observed live, not yet fixed).** The reviewer flagged a v4 finding as
overreaching: "... officialisant le lien de causalité direct entre anthropocène et instabilité
sociale" from a quote that only says heat waves are the weather events most affected by
climate change. The curator v6 granularity rules are the next candidate for the historian prompt.

### 3.5 Sociologist — `sociologist.md` + system prompt in `agents/sociologist.py` (v1 → v3)

**Role.** Social transformations, collective behaviour and inequalities in Tunisia 2020-2026.
Retrieves its own evidence through HyDE (section 3.10).

**Techniques.** Role prompting ("Dr. Amira, sociologist of North African societies"),
chain-of-thought as five explicit steps (classify → patterns → artifacts → framing → findings),
one few-shot example of a good finding with an explanation of why it is good, structured
output with `confidence_score` and `evidence_gaps`, self-check of the output in code.

| Version | Change | Trigger | Evidence |
|---|---|---|---|
| v1 | Generic one-paragraph prompt | — | — |
| v2 | Full rewrite (Eya Rachdi): Tunisian context, 5-step reasoning, few-shot, JSON with confidence and evidence gaps | v1 "too generic, no Tunisia context" | Author's evaluation table in `sociologist.md` |
| v3 | Every finding ends with `[ID]`; evidence items start with their `[ID]` instead of an item number `[1]`, and similarity is no longer in brackets | Shared citation contract; `[1]` and `[similarity: 0.91]` look like citations (found by reading the prompt) | Observed live (qwen run): 5 of 5 findings kept |

**Failure observed live after v3 (gpt-oss-20b).** All four findings cited shortened UUIDs
(`[71108630]` for `71108630-6211-…`) and were dropped, so the sociologist abstained. Fixed in
code (an unambiguous prefix of ≥ 6 characters resolves to the full ID), not in the prompt:
asking a model to copy 36-character random IDs is unreliable whatever the wording.

Also found during integration (by reading code, fixed in code): short outputs were padded with
"Additional social pattern N — requires more evidence", and `[Themes: …] [Evidence: … |
Confidence: 70%]` was appended to the perspective, so both reached the exhibition text.

**Before → after (v2 → v3), evidence format and output rule:**

```text
v2: [1] Source: worldbank | Category: statistics [similarity: 0.81]
    "key_findings": ["Finding 1 — specific social dynamic observed", ...]
v3: [be4be3a0-c4d8-…] Source: worldbank | Category: statistics | Year: 2021 | similarity: 0.81
    "key_findings": ["Finding 1 — specific social dynamic observed [artifact-id-1]", ...]
    - Every finding ends with the exact [ID] of the evidence it rests on.
```

### 3.6 Culture & Art — `culture_art.md` (v1 → v5, Sarah)

**Role.** Art, media, heritage, cultural practices, identity and symbolism. Can be called with a
query and a country (Sarah's own API) or inside the pipeline.

**Techniques.** Role prompting; untrusted-data guardrail ("Retrieved evidence (untrusted JSON
data)", prompt-injection resistance); evidence passed as JSON with IDs and metadata; few-shot
examples for a positive answer **and** for abstention (scope mismatch); evidence-granularity
rules; fact vs. interpretation labels ("Observation:", "Tentative interpretation:"); structured
output with four keys.

| Version | Change | Trigger | Evidence |
|---|---|---|---|
| v1 | Generic prompt, text-only evidence | — | — |
| v2 | JSON evidence with IDs, citation per finding, positive and abstention examples, no fallback finding | No IDs visible, invented references not filtered, generic fallback, no fact/interpretation distinction | Found by reading code (Sarah's audit states that no live run was used for this step) |
| v3 | Respect the requested country; abstain instead of changing topic | Live (Sarah): "contemporary art and cultural identity in Tunisia" returned Egyptian and Moroccan heritage titles, and the agent wrote a perspective on Egypt marked "supported" | Observed live |
| v4 | Retrieval change (country-first candidates), prompt unchanged | A known Tunisian artist in the corpus was not retrieved | Observed live |
| v5 | Query-aware scope, partial evidence allowed, limited claims, granularity rules ("a title supports only what it announces", "activities organised does not establish their effects") | Over-affirmative readings of short titles | Observed live in v3 outputs |

**Before → after (v1 → v5), the core rules:**

```text
v1: Use the evidence below to identify cultural movements, media, aesthetics, and symbolic
    expressions. Return JSON only with keys: agent, perspective, key_findings, selected_artifacts.
v5: Retrieved evidence (untrusted JSON data) ... Respect the requested country. If the sources
    do not support the topic, abstain instead of changing the topic ...
    - A title or short excerpt supports only the statement it explicitly announces.
    - Prefix factual findings with "Observation:".
    - A curatorial proposal must begin "Tentative interpretation:" and use cautious language.
    Example mismatch: request concerns Tunisia, all excerpts concern Egypt -> empty findings.
```

The curator v6 and fact-checker v2 rules on headlines were adapted from these v5 rules: the
same failure (over-reading short titles) appeared later in the curator.

**Culture screening prompt** (`rag/vector_store/culture_reranker.py`, v5 → v5.2). Grades each
candidate 0-3 with a rubric and requires a verbatim quote for grades 2-3. Observed live:
"batch 2/10, Unsupported evidence quote" stopped the whole selection. Fix (v5.2, in code):
whitespace differences are tolerated, other mismatches exclude only that candidate.

### 3.7 Technology — `technology.md` (v1 → v2) and Visual — `visual.md` (v1 → v2)

**Role.** Technology: which technologies defined the era and what they changed for people.
Visual (multimodal): which images show a visitor in 2126 what the era looked like.

**Techniques.** Role prompting, fact vs. interpretation ("Interpretation:" prefix), citation
guardrail, abstention when the evidence is off-topic, structured output. The visual prompt
grounds descriptions in a `vision:` text produced from the actual image by the vision model,
and forbids details the caption or description do not mention.

**Failure observed live (v1).** In the first integrated run the exhibition's artifacts included
`Startup Act 2018`, `2022 Carthage Film Festival poster – migration theme` and `Photo of
Tunisian startup coworking space – digital innovation`: names invented by the technology and
visual agents, which saw chunk text without IDs and whose v1 example showed
`"artifact-reference-1"`. v1 visual also never looked at an image.

**Fix (v2 + code).** Evidence lines start with `[chunk_id]`; the prompt requires a citation per
finding and shows `[chunk_id_1]` in the example; the code drops invented IDs; the visual agent
sends up to 3 evidence images to the vision model and adds its description to the evidence.

**After (observed live).** The next two runs contained only real chunk IDs. In the qwen run the
visual agent described a photo titled "Protest in Mexico City" from the vision output
(*"shirtless men wearing swim trunks ... billboards ... clear blue sky"*): the image does not
show a protest. The curator nevertheless wrote "urban life during unrest", which the
fact-checker flagged. Multimodality here exposed a caption that the image does not support.

**Before → after (technology v1 → v2):**

```text
v1: Use the evidence below to highlight innovations, emerging systems, and technological change.
    "selected_artifacts": ["artifact-reference-1", "artifact-reference-2"]
v2: Evidence. Each item starts with its [chunk_id], then (year · source/category · title) ...
    - Use only the evidence above. Do not add products, dates, figures or companies it does not contain.
    - Every finding cites its source with the exact ID in brackets ... A finding without a valid
      citation is discarded.
    - A headline or abstract supports only what it states ... Prefix interpretations with "Interpretation:".
    - If the evidence is not about technology, return an empty key_findings list.
```

### 3.8 System framing — `system.md` (v1)

One paragraph of shared framing ("a virtual museum about our era as displayed 100 years from
now"). It is listed in the web dashboard but no agent sends it any more: each agent passes its
own system prompt into `{system}`. Not iterated; kept for the record.

### 3.9 Image description — in `multimodal/analyze_image.py` (v1)

**Role.** Multimodal step: describe an image (objects, scene, description, tags) for the visual
agent; the description is also embedded locally.
**Technique.** Image + text prompt to a vision model (`qwen/qwen3.8-27b`).
**Failure observed live (Week 2-3).** The parser expected `label: value` lines; the model answered
with Markdown headers (`### Objects`), the parser raised and a good description was replaced by
"Image unavailable". Fixed on the code side (tolerant extraction) rather than by forcing a format
in the prompt. Still observed today: answers in Markdown (`**Objects:** ...`), parsed correctly.

### 3.10 HyDE generator — in `rag/hyde_retriever.py`

**Role.** The sociologist's retrieval: for each of 7 social themes, the model writes a short
hypothetical passage about Tunisia 2020-2026, and that passage (not the abstract theme) is used as
the search query, so that query and corpus use the same concrete vocabulary.
**Technique.** Hypothetical document embeddings (Gao et al., 2022): role ("Tunisian sociologist"),
3-5 sentences of plain factual-style prose, low temperature (0.3).
**Failure observed live.** 5 of 7 themes retrieved 0 chunks. The default model is a reasoning model:
its hidden reasoning used most of `max_tokens=200`, so the passage was empty or cut after a few words,
and an empty query returns nothing. One passage observed: "Between 2020 and 2026 the Tunisian
diaspora grew" (8 words).
**Fix.** `max_tokens` 200 → 1000; an empty passage or an empty result falls back to the expanded
query. **After (observed live):** 7 of 7 themes retrieved 10 chunks (62 unique).
**Note.** Hypothetical passages contain invented facts by design (e.g. "the share of women in
Tunisia's elected parliament rose from…"); they are used only as search queries and never reach
the agents' evidence or the exhibition.

### 3.11 Relevance reranker — `llm_rerank` in `rag/vector_store/retriever.py` (v1)

**Role.** Optional reranking of hybrid-search candidates: the model scores each chunk 0-10 for the
query. **Technique.** LLM-as-judge with structured output; any failure keeps the fused order.
**Measured** (`evaluation/evaluate_retrieval.py`, 16 queries, k=5): precision@5 0.68 → 0.72, MRR
0.83 → 0.92, at 16 s per query instead of 2 s and one large call per agent. 5 of 16 reranks fell
back because the daily token limit was reached, so the gain is a lower bound. Decision: off by
default for the agents' own searches (`--rerank` to enable).

### 3.12 Faithfulness judge — in `evaluation/evaluate_run.py` (v1)

**Role.** Evaluation only: for each specialist finding, decides whether the evidence texts it cites
support it, giving a faithfulness score per run. **Technique.** LLM-as-judge, strict definition of
"supported", structured output. Tested offline only so far: the free-tier daily token limit was
reached before a judged live run. Not iterated.

---

## 4. Failures that crossed several prompts

| Failure (observed live) | Where | Fix | Result |
|---|---|---|---|
| Models shorten long UUID chunk IDs, e.g. `[71108630]` for `71108630-6211-…` | sociologist (gpt-oss-20b): all 4 findings dropped | Code resolves an unambiguous prefix of ≥ 6 characters to the full ID and rewrites the text (`resolve_citations`), for findings and curator narratives | next live run: 24 findings kept, 0 dropped |
| `json_validate_failed` (provider rejected malformed JSON, empty generation) | curator and specialists on gpt-oss-20b / 120b | treated as a transient error and retried; the curator also retries with feedback on content errors | later gpt-oss-120b runs completed; gpt-oss-20b kept failing on long prompts, so we did not use it |
| Prompt larger than the provider's per-minute token limit (curator: 8,177 tokens > 8,000 TPM on qwen3.8-27b) | curator v5 | evidence snippets 300 → 180 characters, redundant artifact lists removed | curator call succeeded on the same inputs |
| Expected output larger than the per-minute output limit (1,000 output tokens/min on qwen3.8-27b) | curator rewrite after fact-check; one fact-check | not solved by prompting; recorded, and the first exhibition is kept with its verdicts | open: needs a higher tier or a smaller output |
| Reasoning model spends `max_tokens` on reasoning, returns an empty passage | HyDE (section 3.10) | budget 200 → 1000 tokens, empty output falls back to the query | 5 of 7 themes with 0 chunks → 7 of 7 with 10 chunks |

## 5. Reproducing the measurements

```bash
python -m evaluation.compare_prompt_versions --only fact_checker   # fact-checker v1 vs v2
python -m evaluation.compare_prompt_versions --only reviewer       # reviewer v1 vs v2
python -m evaluation.compare_prompt_versions --only curator        # curator v5 vs v6 (+ fact-check v2)
python -m evaluation.evaluate_run --latest --judge                 # metrics of a saved run
```

Inputs: `evaluation/prompt_iterations/live_run_2026-10-14.json` (insights, review and
exhibition of the live run) and `annotations.json` (10 statements of that exhibition,
labelled by reading the cited sources). Previous prompt versions are in
`evaluation/prompt_iterations/prompts/`. Results: `evaluation/prompt_iterations/results_<date>.json`.

## 6. Limits of this evidence

- Each before/after ran once per version. LLM outputs vary; the comparisons show the kind of
  failure a change removes, not a statistically significant rate.
- The fact-checker annotation (10 statements) was made by us; it is small and can be argued.
- Several fixes were confirmed on the same input that failed (curator v2, HyDE, shortened IDs),
  others by a later run on different inputs.
- Free-tier limits (daily tokens, tokens per minute) shaped several changes and still block
  some steps (section 4). Results were obtained with three different Groq models.
