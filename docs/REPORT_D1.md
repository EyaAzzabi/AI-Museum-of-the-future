# AI Museum of the Future — Technical report (D1, draft)

Target: ~8 pages. Numbers from the repository as of 2026-10. Sections marked **TODO (owner)** are for teammates.

| § | Section | Owner | ~pages |
|---|---|---|---|
| 1 | Problem and concept | all | 0.5 |
| 2 | Architecture | Tasnim | 1 |
| 3 | Data and RAG (B5) | RAG owner | 1.5 |
| 4 | Multimodal (C4) | Hassan / Tasnim | 1 |
| 5 | Agents and prompts | each agent owner | 1.5 |
| 6 | Orchestration, web, n8n | Tasnim | 1 |
| 7 | Evaluation | all | 1 |
| 8 | Limits and next steps | all | 0.5 |

---

## 1. Problem and concept

A visitor in **2126** walks into a museum about our era (focus: Tunisia 2020–2026). Public sources are collected, searched with RAG, read by five specialist agents, reviewed, curated into 4–6 sections, and fact-checked. Every claim cites its source chunk.

**TODO (all):** one paragraph on why multi-agent rather than one prompt.

## 2. Architecture

```
collectors → chunking → embeddings → Supabase (pgvector + FTS)
                                      ↓
                         hybrid retrieval (vector + keyword)
                                      ↓
        historian · sociologist · technology · culture/art · visual
                                      ↓
                         peer review → curator → fact-checker
                                      ↓
              runs/<run_id>/run.json → Flask API → Exposition page · n8n
```

Embeddings: `paraphrase-multilingual-MiniLM-L12-v2` (384-d), local. LLM: Groq-compatible `gpt-oss-120b` (configurable).

## 3. Data and RAG (B5)

Summary of [`rag/README.md`](../rag/README.md):

- **Chunking:** sentence packing to **128** embedding tokens + title prefix (former fixed-512 left 57% of text unseen). Chosen MRR@10 **0.47**.
- **Retrieval (2026-10-15):** hybrid precision@5 **0.70**, hit@5 **1.00**, MRR **0.94**. LLM rerank lowers quality → off by default.
- **Corpus:** Tunisian Wikipedia + full-text news; knowledge base on the order of thousands of documents / tens of thousands of chunks (see dashboard validation / Supabase counts).

**TODO (RAG owner):** HyDE, statistics down-weight, Tunisia precision note.

## 4. Multimodal (C4)

Vision downloads use a User-Agent (Wikimedia 403 without it). Descriptions are JSON-structured, cached, recorded on the Visual agent `images` event, stored in `documents.metadata.vision_*`, and searchable via a `Vision:` line on chunks ([`multimodal/README.md`](../multimodal/README.md)).

**Measured case:** caption *"Protest in Mexico City"* vs vision: shirtless men in swim trunks — no protest (`caption_mismatch`). The Exposition page shows images and « Ce que l'IA voit ».

## 5. Agents and prompts

| agent | prompt | owner |
|---|---|---|
| historian | (see dashboard validate) | Eya |
| sociologist | | Eya Rachdi |
| technology | v5 | Tasnim |
| culture / art | | Sarah |
| visual | | team |
| reviewer / curator / fact-checker | | shared |

**Technology (Tasnim):** finding budget, cited findings only, few-shot from real failures; v3→v4→v5 measured on Supabase evidence ([`docs/technology/PROMPT_LIBRARY_TECHNOLOGY.md`](technology/PROMPT_LIBRARY_TECHNOLOGY.md)).

**TODO (each owner):** one before/after paragraph.

## 6. Orchestration, web app and n8n

- **API** [`exhibition_api.py`](../exhibition_api.py): start, cancel, poll, list, vision describe; optional Bearer token; one run at a time.
- **Page** `#exhibition`: launch / stop / load / replay curator; gallery + fact-check badges.
- **n8n** [`Exhibition_pipeline_end_to_end.json`](../n8n/workflows/Exhibition_pipeline_end_to_end.json): webhook or schedule → start → poll 60 s → summary. Use `127.0.0.1`, not `localhost`.

## 7. Evaluation

- Retrieval / chunking: §3.
- Saved runs: `python -m evaluation.evaluate_run runs/<run_id>`.
- Offline tests: `pytest` (full suite excluding live sociologist when quota is empty).

**TODO:** faithfulness `--judge` when quota allows; paste metrics from a complete Tunisia run.

## 8. Limits and next steps

- Free-tier TPM can block curator rewrite after fact-check (E1).
- Fact-checker often leaves several sections unsupported (E2).
- Demo script 15 min (D5); optional museum-hall image generation (needs image credits).

## Reproduce

```bash
pip install -r requirements.txt
cp .env.example .env   # own keys
python -m pytest -q --deselect tests/test_sociologist.py::TestSociologistLive
python app.py          # http://127.0.0.1:5000/#exhibition
```
