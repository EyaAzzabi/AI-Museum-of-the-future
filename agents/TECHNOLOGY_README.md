# Technology agent — Science & Technology perspective

Author: Tasnim · Branch: `Tasnim_technologyAgent`

| What | File |
|---|---|
| Agent | [`agents/technology.py`](technology.py) |
| Deterministic tools (taxonomy, balancing, figure check) | [`agents/technology_tools.py`](technology_tools.py) |
| Prompt (v5) and its library | [`prompts/technology.md`](../prompts/technology.md), [`docs/technology/PROMPT_LIBRARY_TECHNOLOGY.md`](../docs/technology/PROMPT_LIBRARY_TECHNOLOGY.md) |
| Demo | [`demo_technology.py`](../demo_technology.py) |
| HTTP bridge for n8n + workflow template | [`serve_technology.py`](../serve_technology.py), [`n8n/workflows/TechnologyAgent_Tasnim_template.json`](../n8n/workflows/TechnologyAgent_Tasnim_template.json) |
| Retrieval evaluation | [`evaluation/evaluate_technology_retrieval.py`](../evaluation/evaluate_technology_retrieval.py), [`evaluation/technology_retrieval_cases.json`](../evaluation/technology_retrieval_cases.json) |
| Prompt before/after comparison (v2 → v3 → v4 → v5) | [`evaluation/compare_technology_prompts.py`](../evaluation/compare_technology_prompts.py) |
| Tests (offline, mocked LLM) | [`tests/agents/test_technology_agent.py`](../tests/agents/test_technology_agent.py), [`tests/agents/test_technology_integration.py`](../tests/agents/test_technology_integration.py) |

All of these are Technology-only files. The shared code (`base_agent.py`, `pipeline.py`, the
retriever, the other agents and their tests) is used as is, not modified.

## Role in the system

One of the five specialists that run in parallel in [`pipeline.py`](pipeline.py). Question it answers:
*which technologies defined 2020-2026 and what did they change for people?* Its `InsightObject`
(perspective, cited findings, selected artifacts and their evidence) goes to the peer reviewer, the
curator and the fact-checker like every other specialist's. In the multi-agent design it brings the
"what changed in tools and infrastructure" view that the historian (events) and the sociologist
(society) do not cover, and its findings are cross-checked by the reviewer against theirs.

**Tools the agent has:** the shared hybrid retriever (vector + full-text, filters, dedup), its own
keyword taxonomy (`classify_domain`, `evidence_kind`), the balancing step (`diversify`), the coverage
table (`coverage_summary`) and the figure check (`ungrounded_numbers`); the LLM through `BaseAgent`
(retries, cache, run log).

## Workflow

```
input chunks + own hybrid search (6 domain queries fused, k=36)  BaseAgent.gather_evidence
  -> candidate pool (<= 36)
  -> domain-balanced selection (14 items)                         technology_tools.diversify
  -> evidence lines  [id] (year · source/category · title) text <domain · kind>
     + coverage table per domain                                  TechnologyAgent.format_evidence / _render_prompt
  -> LLM, JSON mode, prompt v5                                    BaseAgent._call_llm (retries, cache, run log)
  -> figure guardrail                                             TechnologyAgent._drop_ungrounded_figures
  -> finding budget: <= 5 cited findings, <= 2 interpretations     TechnologyAgent._enforce_budget
  -> citation guardrail, abstention if nothing is cited           BaseAgent.finalize
```

Run-log events added for this agent (in `runs/<run_id>/run.json`): `evidence_selection` (pool size,
kept IDs, coverage), `analysis` (`domains_covered`, `evidence_gaps` from the model), `guardrail`
(`rule="ungrounded_figure"`: the dropped finding and its unsupported figures; `rule="finding_budget"`:
the findings cut by the budget). The n8n API returns both in `dropped_findings`, with their `rule`.

## Design choices and why (each from an observed failure)

Starting point: the agent of the live run of 2026-10-14 (prompt v2, qwen/qwen3.8-27b), saved in
[`evaluation/prompt_iterations/live_run_2026-10-14.json`](../evaluation/prompt_iterations/live_run_2026-10-14.json).

| Observed in the live run | Change | Where |
|---|---|---|
| 3 of 4 cited sources were AI (2 arXiv papers + 1 headline); energy, space and digital adoption absent, although they are in `data/topics.py` | One search query per technology domain (6), a larger pool (36), then a round-robin over domains and, inside a domain, over source kinds | `search_queries`, `diversify` |
| Tunisian sources are often French or Arabic ("une grave crise électrique") | French/Arabic terms in the taxonomy, French keywords in the search | `TECH_DOMAINS`, `search_keywords` |
| An arXiv randomized trial was reported as a change in "product design workflows" | Each evidence line states its kind (research paper / news / archive / indicator / encyclopedia); the prompt says what each kind can support | `evidence_kind`, prompt step 2 |
| "100 participants" for a trial with "50 product designers and 50 product managers" | Figures must be copied, not computed; a finding whose figures are not in its cited sources is dropped in code | `ungrounded_numbers`, `_drop_ungrounded_figures` |
| "*can* design genetic sequences" (one expert, Arabic headline) became "experts reported AI *allowed* ... expertise *extended* to biology" | Granularity rules + this case as a bad/good example | prompt v3 |
| "mRNA" added to a source that only says "vaccine" | Explicit rule with this example | prompt v3 |
| The perspective said coverage was limited but could not say where | Coverage table per domain in the prompt; `domains_covered` / `evidence_gaps` in the output (logged, not shown in the exhibition) | `coverage_summary`, prompt v3 |
| v3: "solar and wind" added to "renewable energy"; ليجوريا written "Legoria"; a title read as an event | A headline adds no technology, place or cause; names copied as written; a title is reported as "an article titled ..."; Liguria as a second bad/good example | prompt v4 |
| v3: 10 findings (one interpretation per fact); "indicating ..." tails on facts | 3-5 findings including at most 2 interpretations; no reading inside a fact sentence | prompt v4 |
| v3: the coverage line "not clearly technology" listed as a missing domain | Line renamed "outside technology"; the prompt says it is not a domain | `DOMAIN_LABELS`, prompt v4 |
| v4 still returned 6-7 findings in 2 of 3 runs | Budget enforced in code: at most 5 cited findings, at most 2 interpretations; facts first (one place kept for an interpretation, a second only if room is left: a first rule that kept 2 interpretations cut a fact a kept interpretation relied on), facts kept round-robin over domains (variety survives the cut), interpretations resting on kept facts first, model order preserved; uncited findings take no place (the shared citation check drops them after) | `_enforce_budget`, `max_findings`, `max_interpretations` |
| v4 interpretations stated outcomes no source measures ("reduced mortality", "societal concerns shifted"), once about an item they did not cite | An interpretation says what the cited items *may suggest*, never an outcome, names only cited items; vaccine bad/good example | prompt v5 |
| v4 and v5 perspectives: "no cybersecurity evidence" while citing a cyber-defense paper (counted under AI) | The coverage table also lists domains mentioned by items of other domains: "0 as main domain; also in 2 items counted under AI & computing - not a gap" | `mentioned_domains`, `coverage_summary` |

**Why guardrails in code and not only in the prompt.** The team's shared lesson: an instruction lowers
the failure rate, a check removes the failure. Figures are the easiest claim to verify mechanically and
the most damaging when wrong in a museum text.

**Why a keyword taxonomy and not an LLM or embedding classifier.** Deterministic, free, testable and
explainable at the defence; covers the English, French and Arabic sources of the corpus. Limits: a
chunk about several domains gets one label (ties go to the first domain), and an unknown term falls
into "outside technology", which is still sent to the model, last.

**Why balance after retrieval and not by filtering in the database.** The hybrid retriever already
fuses vector + keyword search and deduplicates; balancing the fused pool keeps the relevance order
inside each domain and needs no change to the shared retriever.

**Why the tag goes at the end of the evidence line.** The shared format `[id] (provenance) text` is
what every agent, the citation check and the team's tests rely on; the Technology tag is appended
after it so nothing shared changes.

## Measured

| Measurement | Result | How |
|---|---|---|
| Figure guardrail on the 5 observed v2 findings | 1 dropped ("100 participants"), 4 kept | deterministic, `tests/agents/test_technology_agent.py` + replay |
| Overstatement markers on the observed v2 findings | all 4 failure families present (baseline for v3) | `tests/agents/test_technology_integration.py` |
| Balance on the live-run evidence (21 → 14) | 4 of 6 domains in the prompt; Tunisian electricity crisis and internet indicator reach the top of the list | `python demo_technology.py --dry-run` |
| Own search on Supabase (country=Tunisia), 2026-10-14 | before: pool 10 → 10 sent, 2 domains (digital 6, AI 3, other 1); after: pool 36 → 14 sent, 5 domains (AI 3, digital 3, health 3, energy 2, space 1; other 2) | `python demo_technology.py --rag --dry-run` |
| Per-domain retrieval on Supabase, k=5, 2026-10-14 | precision@5: AI 0.80, digital 1.00, cyber 0.40, energy 0.60, health 1.00, space 0.20; mean 0.67, hit@5 1.00, MRR 0.83 (same with and without the Tunisia filter: no Tunisian technology chunk, every result is a top-up) | `python -m evaluation.evaluate_technology_retrieval` |
| Balance of the 14 items sent, pool of 36, before vs after `diversify()` | domains 2 → 5 of 6; largest domain 0.64 → 0.21; research papers 0.29 → 0.14; cost: "not technology" 0.07 → 0.14 | same command |
| Live run, prompt v3, gpt-oss-120b, Supabase, 2026-10-14 (`runs/20261014-185754-67686d`) | 10 of 10 findings kept, 5 domains cited; v2 failures A and B gone ("AI could be used to design new genetic sequences", "a news report"; "COVID-19 vaccine nearly 95 percent effective", no "mRNA"); new failures listed below | `python demo_technology.py --rag --save` |
| Prompt v2 vs v3 on fixed evidence, 3 runs each, gpt-oss-120b, 2026-10-14 | "mRNA" added: v2 3/3 runs → v3 0/3 in findings; adoption overreach: 3/3 → 1/3; coverage gaps named in the perspective: 0/3 → 3/3; failures A and C did not reproduce with this model even with v2 (details in the prompt library) | `python -m evaluation.compare_technology_prompts --before v2 --runs 3` |
| Prompt v3 vs v4 on the same 14 Supabase items, 4 samples × 3 runs = 12 runs each, gpt-oss-120b, 2026-10-14 | "solar and wind" added: 6/12 → 0/12; Liguria mistransliterated: 10/12 → 0/12; title read as an event: 12/12 → 1/12; reading attached to a fact: 11/12 → 2/12; interpretations per run: 4-5 → 1-2; findings returned: 8.6 → 5.9 on average, still > 5 in 8/12 runs; with the code budget: > 5 in the output 0/6 runs for both prompts; v4 interpretations still claim unmeasured effects (details in the prompt library) | `python -m evaluation.compare_technology_prompts --rag --runs 3` |
| Live run, prompt v4 + finding budget, Supabase, 2026-10-14 (`runs/20261014-191848-15e8c7`) | 6 returned → 5 kept (3 facts, 2 interpretations; first budget rule), 1 fact cut by the budget (second AI item; AI already represented), 0 figure drops; Liguria spelled correctly, no added technology | `python demo_technology.py --rag --save` |
| Prompt v4 vs v5, same 14 Supabase items, 3 runs each, qwen3.8-27b (gpt-oss-120b daily quota used up), 2026-10-14 | interpretation stating an unmeasured outcome or shift: 3/3 → 0/3 (all hedged "may suggest"); interpretation mentioning an uncited item: 1/3 → 0/3; "mRNA" in the perspective: 1/3 → 0/3; "no cybersecurity evidence" while citing the cyber-defense paper: 3/3 → 3/3, fixed in code (coverage), not by the prompt | `LLM_MODEL=qwen/qwen3.8-27b python -m evaluation.compare_technology_prompts --rag --runs 3` |
| Whole pipeline (`run_exhibition.py --timeout 400`), qwen3.8-27b, Tunisia 2020-2026 (`runs/20261014-205736-68ae22`) | all 5 specialists produced insights (technology: 5 findings, 0 dropped; pool 36 → 14); the peer reviewer flagged no technology finding (one historian finding flagged); the curator then failed on the free-tier output limit (asks 1140 tokens, limit 1000/min), shared code | `python run_exhibition.py` |
| Same pipeline with the default timeout (180 s) | technology, sociologist and culture timed out: the 5 specialists share the CPU for embeddings and search (technology alone: 13-19 s) | — |

## Failure found on the real database (and fixed)

The first run on Supabase sent only 10 items, 6 of them "digital": `HybridRetriever.search_many`
fuses all queries with reciprocal rank fusion and returns **k results in total**, not k per query,
and the agent asked for k=10. The offline tests had missed it because the mocked retriever ignored
k. Fix: `search_k = max_evidence = 36` (still one search call, as the shared design expects), so the
fused list keeps the top results of every domain query and `diversify()` has a real pool to balance.
A test now uses a retriever that fuses and caps k like the real one
(`test_every_domain_reaches_the_prompt_although_search_many_caps_k_in_total`).

## Failures of prompt v3 observed live (run 20261014-185754-67686d)

| Finding (v3) | Source | Failure |
|---|---|---|
| "increased production of renewable energy, showing ongoing investment in **solar and wind** power" | Arabic headline: Liguria boosts renewable energy production | technologies added; "ليجوريا" (Liguria) transliterated as "Legoria" |
| "access to social media **was being regulated** responsibly, indicating governmental or platform-level controls" | headline "Responsibly regulated access to social media" | a title (possibly an opinion) read as an event |
| "a SpaceX rocket impacted the Moon ... **indicating continued commercial lunar activity**" | headline on the impact and NASA crater images | interpretation not labelled |
| 10 findings (5 facts + 5 "Interpretation:") | prompt asks for 3-5 | count rule ignored |
| perspective lists "not clearly technology" as a missing domain | coverage table line | the table's "other" line read as a domain |

These became prompt v4 (see the design table above and the v3 vs v4 measurement). Still failing with
v4: interpretations that claim effects no source measures ("dramatically reduced COVID-19 mortality",
"affecting employment"), and the 5-finding limit exceeded in 2 of 3 runs. The limit is now enforced in
code (`_enforce_budget`); the interpretation rule became prompt v5 (measured above).

## Limits and next steps

- Cybersecurity has 0 items as *main* domain on Supabase: the corpus's cybersecurity items also talk
  about AI, and a chunk's main domain is the one with the most term hits (AI wins). The coverage table
  now says the domain is mentioned by 2 AI items and is not a gap; the model's logged `evidence_gaps`
  can still list it (seen once with qwen3.8-27b, not shown in the exhibition).
- v5 was measured with qwen3.8-27b only (3 runs): confirm on gpt-oss-120b when its daily quota is back
  (`python -m evaluation.compare_technology_prompts --rag --runs 3`).
- Whole pipeline on the free tier: give the specialists `--timeout 400`; the shared curator needs a
  model whose output limit exceeds 1140 tokens/min (gpt-oss-120b) to finish the exhibition.
- With country=Tunisia every technology item is marked "outside the requested country": the corpus has
  no Tunisian technology source; the retriever tops up with global evidence and says so.

- Balancing can only use what the corpus contains: Tunisian technology material is scarce, so most
  technology evidence is global and marked "outside the requested country" by the retriever.
- Statistics stay excluded from the agent's own search (`search_exclude_categories`); World Bank
  adoption indicators (internet users, mobile subscriptions) would be strong technology evidence and
  are the next retrieval experiment (they can already arrive through the shared input chunks).
- The figure guardrail checks figures, not words: an overstatement without figures ("allowed" for
  "can") is left to the prompt, the peer reviewer and the fact-checker.

## Run

```bash
python -m pytest tests/agents/test_technology_agent.py tests/agents/test_technology_integration.py -q
python demo_technology.py --dry-run                       # no key: evidence, coverage, prompt
python demo_technology.py                                 # LLM_API_KEY: live analysis of the live-run evidence
python demo_technology.py --rag --save                    # + Supabase: own search, run saved to runs/
python serve_technology.py                                # http://127.0.0.1:5002/api/technology (n8n)
python -m evaluation.evaluate_technology_retrieval        # Supabase keys
python -m evaluation.compare_technology_prompts --rag --runs 3   # v4 vs v5, LLM + Supabase keys
python -m evaluation.compare_technology_prompts --rag --runs 3 --before v3   # v3 vs v5
python -m evaluation.compare_technology_prompts --before v2 --runs 3  # v2 vs v5, live-run evidence
python run_exhibition.py --timeout 400                    # whole pipeline, all agents (free tier: longer timeout)
```

n8n: import `n8n/workflows/TechnologyAgent_Tasnim_template.json`, start `python serve_technology.py`,
then `POST <n8n>/webhook/technology` with `{"country": "Tunisia"}` (optional: `year_from`, `year_to`,
`chunks`, `use_rag`). If n8n runs in Docker, set `TECHNOLOGY_API_URL=http://host.docker.internal:5002/api/technology`.
