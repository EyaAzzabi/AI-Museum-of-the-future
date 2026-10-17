# Multimodal processing

Image understanding — the project's mandatory non-textual modality (Week 1 scope).

The system does **not** invent museum images. It downloads real source images, describes what
they show with a vision LLM, and feeds that description into the Visual agent and the RAG
knowledge base so retrieval can use the pixels, not only the caption.

## Flow

```
image_url (document metadata)
    → download with User-Agent (Wikimedia requires it)
    → vision LLM (VISION_MODEL / Groq) → structured JSON
    → disk cache (multimodal/cache/)
    → Visual agent evidence as "vision: …"
    → documents.metadata.vision_* + chunk line "Vision: …" (C3)
    → HybridRetriever surfaces vision_* on every search hit
```

| Piece | Role |
|---|---|
| [`analyze_image.py`](analyze_image.py) | Download, JSON vision parse, cache, text embedding of the description |
| [`store_vision.py`](store_vision.py) | Write `vision_*` into Supabase document metadata and a searchable `Vision:` line on the chunk |
| [`agents/visual.py`](../agents/visual.py) | Looks at up to `VISUAL_MAX_IMAGES` images per run; records `descriptions` on the `images` event |

## Why this matters (measured case)

Caption: **"Protest in Mexico City"**.  
What the vision model sees: shirtless men in swim trunks on a road, cars, billboards — **no protest**.

That contradiction is the multimodal contribution: text RAG alone would trust the caption; vision
exposes the mismatch (`caption_mismatch`). Offline fixture:
`tests/multimodal/test_analyze_image.py::TestAnalyzeImageUnit::test_mexico_caption_mismatch_fixture`.

## Environment

Uses the same LLM key as the agents (`LLM_API_KEY`). No Hugging Face token required.

```bash
# .env
# VISION_MODEL=qwen/qwen3.8-27b   # must be vision-capable
# VISUAL_MAX_IMAGES=3             # images described per Visual-agent run
```

## Constraints

- Only documents the Visual agent actually analyzes are updated in Supabase (no mass re-ingest).
- Do not run `rag/schema.sql` or `data/fetch_all.py` against the group database for this feature.
- `multimodal/cache/` is gitignored; clear it to force re-analysis.

## Demo

```bash
python demo_multimodal.py path/to/image.jpg
# or any URL Wikimedia / Openverse image
```

## Tests

```bash
python -m pytest tests/multimodal tests/rag/test_hybrid_retriever.py -q
```
