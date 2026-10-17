"""Replay the n8n workflow's chunk -> embed -> store path without n8n.

    python n8n/replay_embedding_path.py

n8n is not needed: the workflow's own JavaScript nodes ("chunk", "format
embedding") are read from workflows/My workflow.json and run with Node.js, the
"embed (local MiniLM)" HTTP request is sent to the Flask app's /api/embed (test
client, same handler as `python app.py`), and the two SQL nodes run their exact
queries on Supabase inside a transaction that is rolled back, so nothing stays
in the database. It checks what the n8n runtime would do with real data:
request and response shapes, the vector literal, the vector(384) column and
the SQL. Needs Node.js and SUPABASE_DB_DIRECT_URL (or SUPABASE_DB_URL).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "n8n" / "workflows" / "My workflow.json"

SAMPLE_DOC = {
    "external_id": "replay-test:tunisia-0001",
    "title": "Replay test document",
    "content": ("Tunisia held a constitutional referendum on 25 July 2022. " * 20
                + "تونس أجرت استفتاء دستوريا في 25 جويلية 2022. " * 10
                + "La Tunisie a organisé un référendum constitutionnel le 25 juillet 2022. " * 10).strip(),
    "source": "replay_test",
    "source_type": "news_events",
    "category": "news",
    "url": "https://example.org/replay-test",
    "metadata": {"published_at": "2026-10-15T00:00:00Z"},
}


def node(workflow: dict, name: str) -> dict:
    return next(n for n in workflow["nodes"] if n["name"] == name)


def run_js(code: str, items_by_node: dict[str, list[dict]], input_items: list[dict]) -> list[dict]:
    """Run an n8n Code node: $('<node>').all(), $input.all() and items are provided."""
    harness = (
        "const DATA = " + json.dumps(items_by_node) + ";\n"
        "const INPUT = " + json.dumps(input_items) + ";\n"
        "const $ = (name) => ({ all: () => DATA[name] });\n"
        "const $input = { all: () => INPUT };\n"
        "const items = INPUT;\n"
        "const result = (() => {\n" + code + "\n})();\n"
        "process.stdout.write(JSON.stringify(result));\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
        fh.write(harness)
        path = fh.name
    try:
        out = subprocess.run(["node", path], capture_output=True, text=True, check=True, encoding="utf-8")
    finally:
        os.unlink(path)
    return json.loads(out.stdout)


def to_psycopg(query: str) -> str:
    """n8n's Postgres node uses $1..$n placeholders; psycopg2 uses %s."""
    return re.sub(r"\$\d+", "%s", query.replace("%", "%%"))


def main() -> None:
    sys.path.insert(0, str(ROOT))
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    workflow = json.loads(WORKFLOW.read_text(encoding="utf-8"))

    # 1. "chunk" node (its own JavaScript)
    chunks = run_js(node(workflow, "chunk")["parameters"]["jsCode"], {"dedup docs": [{"json": SAMPLE_DOC}]}, [])
    from rag.chunking.chunker import _embedding_token_counter

    count = _embedding_token_counter()
    tokens = [count(c["json"]["content"]) for c in chunks]
    print(f"1. chunk node: {len(chunks)} chunks, model tokens {tokens}")
    assert max(tokens) <= 128, "a chunk exceeds the embedding model's 128-token window"

    # 2. "embed (local MiniLM)" node: POST {"text": content} to /api/embed
    embed_node = node(workflow, "embed (local MiniLM)")["parameters"]
    assert embed_node["url"].endswith("/api/embed") and '"text": $json.content' in embed_node["jsonBody"]
    from app import create_app

    client = create_app().test_client()
    responses = []
    for chunk in chunks:
        reply = client.post("/api/embed", json={"text": chunk["json"]["content"]})
        assert reply.status_code == 200, reply.get_data(as_text=True)
        responses.append({"json": reply.get_json()})
    print(f"2. /api/embed: {len(responses)} responses, dimension {len(responses[0]['json']['embedding']['values'])}")

    # 3. "format embedding" node (its own JavaScript)
    rows = run_js(node(workflow, "format embedding")["parameters"]["jsCode"], {"chunk": chunks}, responses)
    print(f"3. format embedding: {len(rows)} rows, vector literal starts {rows[0]['json']['embedding'][:40]}...")

    # 4. the two SQL nodes, exact queries, rolled back
    import psycopg2

    doc_sql = node(workflow, "Execute a SQL query")["parameters"]["query"]
    chunk_sql = node(workflow, "Execute a SQL query1")["parameters"]["query"]
    conn = psycopg2.connect(os.environ.get("SUPABASE_DB_DIRECT_URL") or os.environ["SUPABASE_DB_URL"])
    try:
        cur = conn.cursor()
        cur.execute(to_psycopg(doc_sql), (
            SAMPLE_DOC["source"], SAMPLE_DOC["category"], SAMPLE_DOC["title"], SAMPLE_DOC["url"],
            SAMPLE_DOC["metadata"]["published_at"], SAMPLE_DOC["content"],
            json.dumps({"external_id": SAMPLE_DOC["external_id"], "type": None, "language": None}),
        ))
        stored = 0
        for row in rows:
            r = row["json"]
            cur.execute(to_psycopg(chunk_sql), (r["external_id"], r["chunk_index"], r["content"], r["embedding"], r["metadata_json"]))
            stored += cur.rowcount
        cur.execute("""select count(*), min(vector_dims(c.embedding)) from chunks c join documents d on d.id = c.document_id
                       where d.metadata->>'external_id' = %s""", (SAMPLE_DOC["external_id"],))
        count, dims = cur.fetchone()
        print(f"4. SQL nodes: document + {stored} chunks inserted, read back {count} chunks of dimension {dims}")
        assert count == len(rows) and dims == 384
    finally:
        conn.rollback()
        conn.close()
    print("OK: the workflow's embedding path works end to end (transaction rolled back, database unchanged).")


if __name__ == "__main__":
    main()
