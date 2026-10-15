"""Find and delete documents stored twice with the same text.

    python -m rag.dedupe_documents            # preview only
    python -m rag.dedupe_documents --apply    # delete the extra copies (their chunks cascade)

Two documents are duplicates when their first 1,500 characters are equal after
lower-casing and collapsing punctuation. Found on 2026-10-15: 40 duplicates in
the live knowledge base (193 chunks):
- 32 arXiv papers stored once by the Python pipeline and once by the n8n
  workflow, which identifies documents differently (no source_id, external_id
  "arxiv:<id>" without the version), so neither recognised the other's copy;
- 6 news articles published under two URLs or channels;
- 2 archived snapshots of the same page.

In each group the copy kept has a source_id, then the longest text, then the
most chunks. Image sources are skipped: different photos often share one caption,
and each image is a separate artifact for the visual agent.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import os
import re

IMAGE_SOURCES = ("wikimedia", "openverse", "met_museum")


def text_key(text: str) -> str:
    return hashlib.sha1(re.sub(r"\W+", " ", (text or "").lower())[:1500].encode("utf-8")).hexdigest()


def find_duplicates(cursor, min_chars: int = 300) -> list[dict]:
    cursor.execute(
        """select d.id, d.source, d.source_id, d.title, d.raw_text, count(ch.id)
           from documents d left join chunks ch on ch.document_id = d.id
           where length(d.raw_text) > %s and d.source <> all(%s) and coalesce(d.category, '') <> 'image'
           group by d.id""",
        (min_chars, list(IMAGE_SOURCES)),
    )
    groups: dict[str, list[dict]] = collections.defaultdict(list)
    for doc_id, source, source_id, title, text, chunks in cursor.fetchall():
        groups[text_key(text)].append({"id": str(doc_id), "source": source, "source_id": source_id,
                                       "title": title, "length": len(text), "chunks": chunks})
    extra: list[dict] = []
    for docs in groups.values():
        if len(docs) > 1:
            docs.sort(key=lambda d: (d["source_id"] is not None, d["length"], d["chunks"]), reverse=True)
            extra.extend(docs[1:])
    return extra


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="delete the extra copies")
    args = parser.parse_args()

    import psycopg2
    from dotenv import load_dotenv

    load_dotenv()
    connection = psycopg2.connect(os.environ["SUPABASE_DB_URL"])
    cursor = connection.cursor()
    extra = find_duplicates(cursor)
    by_source = dict(collections.Counter(d["source"] for d in extra))
    print(f"{len(extra)} duplicate documents ({sum(d['chunks'] for d in extra)} chunks): {by_source}")
    if args.apply and extra:
        cursor.execute("delete from documents where id = any(%s::uuid[])", ([d["id"] for d in extra],))
        connection.commit()
        print(f"deleted {cursor.rowcount}")
    elif extra:
        print("preview only: rerun with --apply to delete")


if __name__ == "__main__":
    main()
