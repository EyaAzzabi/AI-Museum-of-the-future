"""The n8n workflow's chunk node fits the embedding model's window (offline; needs Node.js)."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "n8n"))


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js not installed")
def test_chunk_node_packs_sentences_within_the_embedding_window() -> None:
    from replay_embedding_path import WORKFLOW, node, run_js

    from rag.chunking.chunker import _embedding_token_counter

    workflow = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    doc = {"external_id": "x:1", "title": "Tunisia", "category": "news", "source": "test", "metadata": {},
           "content": "The referendum took place on 25 July 2022. " * 25 + "استفتاء دستوري في تونس. " * 15}
    chunks = run_js(node(workflow, "chunk")["parameters"]["jsCode"], {"dedup docs": [{"json": doc}]}, [])
    count = _embedding_token_counter()
    assert len(chunks) > 1
    assert all(count(c["json"]["content"]) <= 128 for c in chunks)
    assert all(c["json"]["content"].startswith("Tunisia — ") for c in chunks)
    assert [c["json"]["chunk_index"] for c in chunks] == list(range(len(chunks)))


def test_embed_node_posts_chunk_text_to_the_local_endpoint() -> None:
    workflow = json.loads((ROOT / "n8n" / "workflows" / "My workflow.json").read_text(encoding="utf-8"))
    params = next(n for n in workflow["nodes"] if n["name"] == "embed (local MiniLM)")["parameters"]
    assert params["url"].endswith("/api/embed") and '"text": $json.content' in params["jsonBody"]
