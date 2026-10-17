# Prompt library — Technology agent (Tasnim)

Prompt file: [`prompts/technology.md`](../../prompts/technology.md) (v5). Previous versions:
[`technology_v4.md`](../../evaluation/prompt_iterations/prompts/technology_v4.md),
[`technology_v3.md`](../../evaluation/prompt_iterations/prompts/technology_v3.md),
[`technology_v2.md`](../../evaluation/prompt_iterations/prompts/technology_v2.md).
Same conventions as the team library ([`prompts/PROMPT_LIBRARY.md`](../../prompts/PROMPT_LIBRARY.md), §2):
evidence lines start with `[chunk_id]`, every finding cites, guardrails are checked in code, the
changelog header is stripped before sending. Evidence types: **observed live**, **measured**,
**found by reading code**.

## Role in the system

Specialist "Science & Technology": which technologies defined 2020-2026 and what they changed for
people. Called by `agents/technology.py` (`TechnologyAgent.run`) inside the pipeline, by
`demo_technology.py` and by `serve_technology.py` (n8n). Output: `perspective`, cited
`key_findings`, `selected_artifacts`, and `domains_covered` / `evidence_gaps` (logged in the run only).

## Techniques

| Technique | Where in v5 | Why |
|---|---|---|
| Role prompting | system prompt: curator writing in 2126 | museum distance; separates research from adoption |
| Typed context injection | each evidence line ends with `<domain · kind of source>`; coverage table `{coverage}` | the model must know what a source can prove and which domains are missing |
| Chain-of-thought (hidden) | 4 steps: sort → bound → select → frame | bound each claim by the kind of its source before writing |
| Guardrails (prompt) | granularity rules, no added terms, figures copied as given, untrusted-data line | failures observed with v2 (below) |
| Guardrails (code) | figure check (`_drop_ungrounded_figures`), finding budget (`_enforce_budget`), citation check (`BaseAgent.finalize`) | an instruction lowers a failure rate, a check removes the failure |
| Few-shot (negative + positive) | bad / good rewrites of the genetic-sequences headline (v2 failure), the Liguria headline (v3 failure) and a vaccine interpretation (v4 failure) | real failures, so the model sees the exact mistakes |
| Structured output | JSON mode + literal template | parsed and validated in code |

## Versions

| Version | Change | Trigger | Evidence |
|---|---|---|---|
| v1 | "Highlight innovations", example `"artifact-reference-1"` | — | — |
| v2 | Future-curator role, fact vs. interpretation, `[chunk_id]` per finding | Live run: invented artifacts (`Startup Act 2018`, `Photo of Tunisian startup coworking space`) | Observed live (team library §3.7) |
| v3 | Typed evidence + coverage, 4 reasoning steps, granularity rules, figures copied, bad/good example, `domains_covered` / `evidence_gaps` | v2 failures below | Observed live; guardrail measured; v2 vs v3 measured (3 runs each) |
| v4 | 3-5 findings *including* at most 2 interpretations; no ", indicating ..." tail on a fact; a headline adds no technology, place or cause; a title is reported as "an article titled ..."; names copied as written; rules apply to the perspective; every interpretation cites; "outside technology" is not a gap; second bad/good example (Liguria) | v3 live failures below | v3 vs v4 measured on Supabase evidence (12 runs each) |
| v5 | An interpretation says what the cited items *may suggest*, never an outcome no source measures, and names only cited items; third bad/good example (vaccine interpretation); title example spelled out; coverage read as one label per item (+ code: domains mentioned by other items are "not a gap") | v4 failures in the v3/v4 comparison | v4 vs v5 measured on Supabase evidence (3 runs each, qwen3.8-27b) |

## Failures of v2 (observed live, run of 2026-10-14, qwen/qwen3.8-27b)

Source: `evaluation/prompt_iterations/live_run_2026-10-14.json`, `insights.technology` (5 findings).

| # | v2 wrote | The source says | Failure |
|---|---|---|---|
| A | "cybersecurity expertise **extended to biological domains**, with **experts** reporting that AI capabilities **allowed** the design of new genetic sequences" | Arabic headline: "Cybersecurity expert: AI **can** design new genetic sequences" | one expert → experts; possibility → fact; one headline → a trend |
| B | "public **discourse focused** on the efficacy of **mRNA** vaccines" | one archived TV programme on "a second potential COVID-19 vaccine" | a term the source does not contain; one programme → "discourse" |
| C | "trials involving **100** participants" | "50 product designers and 50 product managers" | computed figure |
| D | prompt-to-design "**altered** the time-savability of product design workflows" | an arXiv randomized trial on standardized tasks | a study result read as a change of practice |
| E | 3 of 4 cited sources are AI | — | no energy, space or digital-adoption evidence (retrieval) |

## Before → after (v2 → v3)

```text
v2: Evidence. Each item starts with its [chunk_id], then (year · source/category · title):
v3: Evidence. Each item reads: [chunk_id] (year · source/category · title) text <technology domain · kind of source>.
    Coverage of the evidence by domain:
    {coverage}

v2: - A headline or abstract supports only what it states; do not turn one paper or
      article into a global trend. Prefix interpretations with "Interpretation:".
v3: 2. Bound: ... research paper: what the authors propose, build or measure, in their study
       only. It does not show that a technology was adopted, nor that it changed society.  (D)
    - Do not add technologies, products ... (e.g. do not write "mRNA" if the source says "vaccine").  (B)
    - Copy figures exactly as the source gives them; do not add up, convert or round them.  (C)
    - Keep the source's strength: "can" or "could" stays a possibility, "one expert says"
      stays one person, a proposed model is not a deployed one.  (A)
    - One item is one example, never a trend, a "discourse" or a whole field.  (A, B)
    Bad:  "By 2026 cybersecurity expertise extended to biology, with experts reporting that AI allowed ..."
    Good: "In 2026 a cybersecurity expert warned in the press that AI can design new genetic sequences ..."
```

Failure E is a retrieval problem, fixed in code, not in the prompt: one search query per domain
and `diversify()` (see [`agents/TECHNOLOGY_README.md`](../../agents/TECHNOLOGY_README.md)).

## Measured

- **Figure guardrail (deterministic, no LLM), on the 5 observed v2 findings:** 1 dropped (C, "100"),
  4 kept; "nearly 95 percent" is kept because its source contains it.
- **Overstatement markers on the observed v2 findings** (`compare_technology_prompts.score`): all four
  marker families fire (A: "allowed", "experts", "extended to"; B: "mRNA", "discourse"). This is the
  baseline v3 is compared against.
- **Evidence balance on the live-run evidence** (`demo_technology.py --dry-run`, 21 chunks → 14):
  4 of 6 technology domains reach the prompt: AI 3, digital 1 (Tunisian internet-use indicator),
  energy 1 (Tunisian electricity crisis), health 1; cybersecurity and space have no evidence in this
  input, and the coverage table says so. Balancing cannot add what retrieval did not find.
- **v2 vs v3 on fixed evidence, measured 2026-10-14** (`python -m evaluation.compare_technology_prompts --runs 3`,
  openai/gpt-oss-120b, the 21 chunks cited in the live run, 3 runs per version, same code; raw output in
  `evaluation/prompt_iterations/technology_results_2026-10-14.json`).

  Automatic output of the script:

  | version | run | returned | kept | figure drops | overstatement markers |
  |---|---|---|---|---|---|
  | v2 | 1 | 10 | 10 | 0 | 5 |
  | v2 | 2 | 8 | 8 | 0 | 1 |
  | v2 | 3 | 5 | 5 | 0 | 3 |
  | v3 | 1 | 8 | 8 | 0 | 2 |
  | v3 | 2 | 8 | 8 | 0 | 2 |
  | v3 | 3 | 10 | 5 | 0 | 0 |

  The marker count is noisy: "enabled" and "widespread" also fire on acceptable interpretations
  ("Broad internet access enabled ...", "widespread digital connectivity" from a 76.5 % figure). Our
  reading of the 6 runs, failure by failure:

  | Failure (from the v2 live run) | v2 (3 runs) | v3 (3 runs) |
  |---|---|---|
  | B — "mRNA" added to a source that says "vaccine" (findings) | **3 / 3** runs | **0 / 3** (but v3 run 3 wrote "mRNA vaccines" in its *perspective*, which the script does not score) |
  | D — research read as adoption, or invented later effects ("later reduced manual analyst workload", "transformed design work", "curbed pandemic severity and enabled a swift return") | 3 / 3 | 1 / 3 ("Broad internet access enabled new forms of remote work ..." from a usage figure); otherwise hedged: "If adopted, such AI-prompt tools could ..." |
  | Perspective names the domains without evidence | 0 / 3 ("limited to a handful of reports") | **3 / 3** (cybersecurity and space named) |
  | A — "can" read as "allowed", one expert as experts | 0 / 3 | 0 / 3 |
  | C — computed figure | 0 / 3 | 0 / 3 |
  | Fact and interpretation merged in one finding | 1 / 3 (run 3: "...; Interpretation: ...") | 0 / 3 |
  | Findings dropped by the code guardrails | 0 | 5 in run 3 (citation check, not figures) |

  **Reading.** v3 removes the added term (B) and most adoption overreach (D), and always states the
  coverage gaps. A and C did not reproduce with gpt-oss-120b even with v2 (they were observed with
  qwen3.8-27b), so this comparison cannot show that v3 fixes them; the figure guardrail stays as the
  safety net for C. The 5 findings dropped in v3 run 3 were not saved by the first version of the
  script; it now also saves `returned_findings`. Three runs per version: indicative, not significant.

## First live run of v3 (observed, 2026-10-14, gpt-oss-120b, Supabase, `runs/20261014-185754-67686d`)

Not the fixed-input comparison (different evidence from the v2 run), but it shows which v2 failures
remain. 10 of 10 findings kept, 5 domains cited, 0 dropped by the figure guardrail.

- **Fixed:** A — "In 2026 a news report noted that AI **could** be used to design new genetic sequences"
  (possibility and single source kept); B — "a COVID-19 vaccine reported as nearly 95 percent
  effective" (no "mRNA", no "discourse").
- **Still failing / new:** technologies added to a headline ("solar and wind" for "renewable energy");
  a proper name mistransliterated ("Legoria" for ليجوريا, Liguria); a title read as an event ("access
  to social media was being regulated"); one unlabelled interpretation ("indicating continued
  commercial lunar activity"); 10 findings instead of 3-5 (every fact followed by an interpretation);
  "not clearly technology" listed as a missing domain.
- These became prompt v4 (below); the coverage line is now "outside technology".

## Before → after (v3 → v4), measured 2026-10-14

`python -m evaluation.compare_technology_prompts --rag --runs 3`: openai/gpt-oss-120b, the agent's own
Supabase search (country=Tunisia) run **once** per sample, the same 14 items given to both versions,
same code. The Supabase evidence is used because the v3 failures were observed on it (Liguria,
social-media headlines); the 21 live-run chunks do not contain them. Four samples of 3 runs per
version, so **12 runs per version**:

| Sample | Code | Raw output in `evaluation/prompt_iterations/` |
|---|---|---|
| A (first run) | figure guardrail, no finding budget | overwritten by sample B (same file name at the time); its findings were read and are counted below |
| B (20:14) | same as A (the run started before the budget was added) | `technology_results_2026-10-14-2019_v3_vs_v4_rag.json` |
| C | + finding budget (first rule: 2 interpretations kept before facts) | `technology_results_2026-10-14-2059_v3_vs_v4_rag.json` |
| D (run in parallel with C) | same as C | `technology_results_2026-10-14-2055_v3_vs_v4_rag.json` |

The script now puts the time in the file name, so a run never overwrites another.

Automatic output (returned = what the model wrote; kept = after the code guardrails):

| Sample | version | returned per run | kept per run | over budget per run | unlabelled readings per run |
|---|---|---|---|---|---|
| A | v3 | 8, 5, 10 | 7, 5, 10 | 3, 0, 5 | 0, 2, 3 |
| A | v4 | 6, 5, 7 | 6, 5, 7 | 1, 0, 2 | 0, 0, 1 |
| B | v3 | 10, 10, 8 | 10, 10, 8 | 5, 5, 3 | 3, 4, 2 |
| B | v4 | 6, 7, 5 | 6, 7, 5 | 1, 2, 0 | 0, 0, 0 |
| C | v3 | 10, 10, 10 | **5, 5, 5** | 5, 5, 5 | 2, 0, 1 |
| C | v4 | 6, 7, 5 | **5, 5, 5** | 1, 2, 0 | 0, 0, 0 |
| D | v3 | 10, 8, 4 | **5, 5, 4** | 5, 3, 0 | 3, 1, 2 |
| D | v4 | 6, 5, 6 | **5, 5, 5** | 1, 0, 1 | 0, 0, 0 |

Our reading of the 24 runs (the markers are a proxy: in sample C, v4 run 2 the "solar and wind" marker
fires on a correct finding, the Arabic headline وزير الكهرباء: تنفيذ مشروعات الطاقة الشمسية والرياح does
say solar and wind):

| Failure (from the v3 live run) | v3 (12 runs) | v4 (12 runs) |
|---|---|---|
| "solar and wind" added to a headline that says "renewable energy" | **6 / 12** | **0 / 12** |
| ليجوريا (Liguria) mistransliterated ("Legoria", "Leguria", "Lijoria", "Lejoria") | **10 / 12** | **0 / 12** |
| Title read as an event ("regulators announced / introduced / promoted responsible access to social media") | **12 / 12** | **1 / 12** (D run 1: "a news headline reported that access to social media was being regulated"; otherwise "a news article titled ...", or not cited) |
| Reading attached to a fact (", indicating / reflecting / aiming ...") | 11 / 12 | 2 / 12 |
| Fact and interpretation merged in one finding | 1 / 12 | 0 / 12 |
| Interpretations without a citation (dropped by the shared check) | 1 / 12 (D run 1: all 5) | 0 / 12 |
| "outside technology" named as a missing domain | 2 / 12 | 0 / 12 |
| More than 5 findings returned by the model | 10 / 12 | 8 / 12 |
| Findings returned, mean | 8.6 | 5.9 |
| Interpretations per run | 4-5 (once 1) | 1-2 |
| More than 5 findings in the output | 5 / 6 runs without the budget, **0 / 6 with it** | 4 / 6 without, **0 / 6 with it** |

**Reading.** v4 removes the failures it targets (added technology and guessed name in 0 of 12 runs,
title read as an event in 1 of 12 instead of 12 of 12, coverage line never read as a gap) and divides
the interpretations by about three. The count instruction only lowers the number returned
(8.6 → 5.9); the code budget makes the limit hold in every run. v3 also invented a place once
("2026 news from Algeria reported that the company Legoria ..."). The
figure guardrail dropped one v3 finding in sample A, "By 2026 prompt engineering was highlighted ...":
that source has no date (`year` is None), so the year was invented, a true positive.

**Finding budget, second rule.** In sample C, v4 run 2 the first rule kept 2 interpretations and cut 2
facts, one of which (the social-media headline) a kept interpretation relied on. Facts are the grounded
part, so the rule is now *facts first*: one place is kept for an interpretation when there is one, the
second interpretation only if a place is left (`TechnologyAgent._enforce_budget`, logged as `guardrail`
with `rule="finding_budget"`; tests `test_budget_keeps_facts_first_with_the_domain_variety`,
`test_budget_keeps_two_interpretations_when_facts_leave_room`).

**Still failing with v4 (next):** interpretations claim effects no source measures ("dramatically
reduced COVID-19 mortality", "biotechnology saving lives", "directly altered public health outcomes");
an interpretation can mention an item it does not cite ("discussions of social-media regulation" citing
only the genetic-sequences headline). These became prompt v5 (next section).

## Before → after (v4 → v5), measured 2026-10-14

`LLM_MODEL=qwen/qwen3.8-27b python -m evaluation.compare_technology_prompts --rag --runs 3`: the daily
token quota of gpt-oss-120b was used up by the v3/v4 samples, and gpt-oss-20b returns empty JSON with
the shared `_call_llm` (all agents), so this comparison uses qwen3.8-27b, the model of the team's first
live run. Same 14 Supabase items for both versions (`evidence_ids` identical in both files). The 3 v4
calls of the first file hit the free-tier output-token limit (429, OTPM 1000) and were rerun alone
(`--only before`). Raw output: `technology_results_2026-10-14-2204_v4_vs_v5_rag.json` (v5) and
`technology_results_2026-10-14-2208_v4_vs_v5_rag.json` (v4).

| version | run | returned | kept | figure drops | unmeasured-outcome marker | perspective markers |
|---|---|---|---|---|---|---|
| v4 | 1 | 4 | 3 | 1 | 0 | 1 ("mRNA vaccines") |
| v4 | 2 | 6 | 5 | 0 | 0 | 0 |
| v4 | 3 | 5 | 5 | 0 | 0 | 0 |
| v5 | 1 | 4 | 4 | 0 | 0 | 0 |
| v5 | 2 | 5 | 5 | 0 | 0 | 0 |
| v5 | 3 | 5 | 5 | 0 | 0 | 0 |

The outcome marker was built from the gpt-oss-120b wording and fires on neither version here: qwen
overreaches with other words, so our reading decides:

| Failure (from the v4 runs) | v4 (3 runs) | v5 (3 runs) |
|---|---|---|
| Interpretation states an outcome or shift no source measures ("marked a pivotal point in global health security", "societal concerns shifted ... to a global climate of conflict and economic disparity", "the rapid implementation of vaccines") | **3 / 3** | **0 / 3** (all hedged: "may suggest"; one adds "though it does not measure the practical impact") |
| Interpretation mentions an item it does not cite | 1 / 3 (vaccines, citing only the AI and Bluesky papers) | 0 / 3 |
| Term added in the perspective ("mRNA vaccines" for "vaccine") | 1 / 3 | 0 / 3 |
| Fact sentence with an added claim ("public interest in health technology peaked", "AI was influencing ... biological research") | 1 / 3 | 0 / 3 |
| Perspective says there is no cybersecurity evidence while citing the cyber-defense paper | 3 / 3 | 3 / 3 |

**Reading.** v5 fixes the interpretations (hedged, cited, no outcome) and keeps the v4 gains. In v4 run 1
the figure guardrail dropped the interpretation that mentioned the 2020 vaccines without citing them: the
year "2020" was not in the two cited sources, so a figure check also caught an uncited mention.

**The perspective failure is in the evidence, not the prompt.** The v5 rule ("a domain you cite an item
about is not a domain with no evidence") did not change it: the coverage table said "cybersecurity &
privacy: 0 - no evidence" because the cyber-defense paper is counted under AI. Fixed in code:
`coverage_summary` now writes "cybersecurity & privacy: 0 as main domain; also in 2 items counted under
AI & computing - not a gap" (`mentioned_domains`; test
`test_coverage_does_not_call_a_domain_absent_when_items_of_other_domains_mention_it`). Live run after the
fix (`runs/20261014-211136-b0534b`, qwen3.8-27b): the perspective names "human-AI collaboration in
cybersecurity" and only says there is no evidence on cybersecurity "as a primary domain"; the logged
`evidence_gaps` field still lists it (not shown in the exhibition).

Three runs per version and one model: indicative. To confirm on gpt-oss-120b when its quota is back:
`python -m evaluation.compare_technology_prompts --rag --runs 3`.

## Known limits

- Marker words are a proxy: "experts" can be correct when a source quotes several; read the findings.
- The figure guardrail ignores one-digit numbers and checks figures, not words.
- One run per version is not significant (LLM variance): use `--runs 3`.
