"""HybridRetriever: fusion, filters, statistics down-weighting and diversity (offline)."""
from __future__ import annotations

from types import SimpleNamespace

from rag.vector_store.hybrid_retriever import (
    HybridRetriever,
    SearchConfig,
    SearchFilters,
    jaccard,
    keyword_query,
    tokens,
)

CHUNKS = {
    "stat-21": ("doc-s21", "Population, total for Tunisia in 2021: 12048622.", "statistics"),
    "stat-22": ("doc-s22", "Population, total for Tunisia in 2022: 12119334.", "statistics"),
    "news-1": ("doc-n1", "Tunisie : cinq ans après les mesures d'exception de Saïed, une crise électorale.", "news"),
    "news-1b": ("doc-n1", "Second chunk of the same Saïed article.", "news"),
    "art-1": ("doc-a1", "Young Tunisian directors at the Carthage Film Festival in Tunis.", "culture"),
    "old-1": ("doc-o1", "Tunisia gained independence from France in 1956.", "history"),
    "ai-1": ("doc-ai", "Large language models changed software work worldwide.", "science"),
}
DOCS = {
    "doc-s21": ("worldbank", "2021-01-01"), "doc-s22": ("worldbank", "2022-01-01"),
    "doc-n1": ("gdelt", "2026-07-25"), "doc-a1": ("wikipedia", None),
    "doc-o1": ("wikipedia", "1956-03-20"), "doc-ai": ("arxiv", "2024-05-01"),
}


def _row(cid):
    doc, content, category = CHUNKS[cid]
    return {"id": cid, "document_id": doc, "content": content, "metadata": {"category": category}}


class _Query:
    def __init__(self, table, calls):
        self.table, self.calls, self.ids = table, calls, None
        self.tsquery = None

    def select(self, *_a, **_k):
        return self

    def filter(self, column, op, value):
        self.tsquery = value
        return self

    def contains(self, *_a):
        return self

    def in_(self, _col, ids):
        self.ids = ids
        return self

    def limit(self, _n):
        return self

    def execute(self):
        if self.table == "documents":
            return SimpleNamespace(data=[
                {"id": d, "source": DOCS[d][0], "category": None, "title": "", "url": "",
                 "published_at": DOCS[d][1], "metadata": {"image_url": None}}
                for d in self.ids
            ])
        self.calls.append(self.tsquery)
        words = {w.strip("()") for w in self.tsquery.replace("<->", " ").split() if w not in {"|"}}
        hits = [cid for cid, (_, content, _) in CHUNKS.items() if words & tokens(content)]
        return SimpleNamespace(data=[_row(c) for c in hits])


class FakeSupabase:
    def __init__(self, vector_order):
        self.vector_order = vector_order
        self.keyword_calls: list[str] = []

    def rpc(self, _name, _args):
        rows = [{**_row(c), "similarity": 0.9 - i * 0.05} for i, c in enumerate(self.vector_order)]
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=rows))

    def table(self, name):
        return _Query(name, self.keyword_calls)


EMBED = SimpleNamespace(embeddings=SimpleNamespace(
    create=lambda input, **_: SimpleNamespace(data=[SimpleNamespace(embedding=[0.0] * 384)])
))


def _retriever(vector_order, **kwargs):
    return HybridRetriever(FakeSupabase(vector_order), EMBED, llm_client=None, config=SearchConfig(), **kwargs)


def test_statistics_rows_are_downweighted_and_capped():
    r = _retriever(["stat-21", "stat-22", "news-1", "art-1"])
    ids = [x.chunk_id for x in r.search("Tunisia society", k=4, rerank=False)]
    assert sum(cid.startswith("stat") for cid in ids) == 1
    assert ids[0] != "stat-21"


def test_keyword_search_finds_exact_names_missed_by_vectors():
    r = _retriever(["ai-1"])
    ids = [x.chunk_id for x in r.search("political crisis", k=5, keywords=["Saïed"], rerank=False)]
    assert "news-1" in ids


def test_one_chunk_per_document():
    r = _retriever(["news-1", "news-1b", "art-1"])
    ids = [x.chunk_id for x in r.search("Saïed", k=5, rerank=False)]
    assert not {"news-1", "news-1b"} <= set(ids)


def test_year_and_country_filters_use_document_metadata():
    r = _retriever(["old-1", "ai-1", "art-1", "news-1"])
    results = r.search("x", k=5, rerank=False, filters=SearchFilters(country="Tunisia", year_from=2020, year_to=2026))
    in_scope = {x.chunk_id for x in results if x.metadata.get("in_scope") is not False}
    assert "old-1" not in {x.chunk_id for x in results}   # 1956: outside the period, never returned
    assert "ai-1" not in in_scope           # does not mention Tunisia: only as a marked top-up
    assert {"art-1", "news-1"} <= in_scope  # undated is kept, "Tunisie" counts as Tunisia
    assert all("year" in x.metadata for x in results)


def test_category_filter_and_exclusion():
    r = _retriever(["stat-21", "news-1", "art-1"])
    only_culture = r.search("x", k=5, rerank=False, filters=SearchFilters(categories=("culture",)))
    assert [x.chunk_id for x in only_culture] == ["art-1"]
    no_stats = r.search("x", k=5, rerank=False, filters=SearchFilters(exclude_categories=("statistics",)))
    assert all(x.metadata["category"] != "statistics" for x in no_stats)


def test_explicit_keywords_are_searched_once_for_many_queries():
    sb = FakeSupabase(["ai-1"])
    HybridRetriever(sb, EMBED).search_many(["q1", "q2", "q3"], k=3, keywords=["Startup Act"])
    assert sb.keyword_calls == ["(startup <-> act)"]


def test_rerank_uses_llm_scores():
    import json

    scores = {"scores": [{"chunk_id": "art-1", "score": 9}, {"chunk_id": "news-1", "score": 2}]}
    llm = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=lambda **_: SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(scores)))])
    )))
    r = HybridRetriever(FakeSupabase(["news-1", "art-1"]), EMBED, llm_client=llm)
    assert [x.chunk_id for x in r.search("cinema", k=2)][0] == "art-1"


def test_retrieve_is_retriever_compatible():
    r = _retriever(["news-1", "art-1"], match_count=1)
    assert len(r.retrieve("Saïed")) == 1


def test_helpers():
    assert keyword_query("the economy of Tunisia") == "economy | tunisia"
    assert keyword_query("x", ["Kaïs Saïed", "Startup Act"]) == "(kaïs <-> saïed) | (startup <-> act)"
    assert jaccard(tokens("Population total 2021"), tokens("Population total 2022")) == 0.5


def test_country_filter_tops_up_with_marked_out_of_scope_results():
    r = _retriever(["ai-1", "art-1"])
    results = r.search("x", k=2, rerank=False, filters=SearchFilters(country="Tunisia", year_from=None, year_to=None))
    assert [x.chunk_id for x in results] == ["art-1", "ai-1"]          # in-scope first
    assert results[0].metadata.get("in_scope") is None
    assert results[1].metadata["in_scope"] is False


def test_country_top_up_can_be_disabled():
    r = HybridRetriever(FakeSupabase(["ai-1", "art-1"]), EMBED, config=SearchConfig(relax_country=False))
    results = r.search("x", k=2, rerank=False, filters=SearchFilters(country="Tunisia", year_from=None, year_to=None))
    assert [x.chunk_id for x in results] == ["art-1"]


def test_transient_database_errors_are_retried(monkeypatch):
    import rag.vector_store.hybrid_retriever as hybrid

    monkeypatch.setattr(hybrid.time, "sleep", lambda _s: None)
    sb = FakeSupabase(["art-1"])
    calls = {"n": 0}
    original = sb.rpc

    def flaky(name, args):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionError("Server disconnected")
        return original(name, args)

    sb.rpc = flaky
    assert [x.chunk_id for x in HybridRetriever(sb, EMBED).search("x", k=1, rerank=False)] == ["art-1"]


def test_document_vision_fields_are_surfaced_on_results():
    """Vision metadata stored by multimodal/store_vision.py must reach every agent."""
    class VisionDocs(_Query):
        def execute(self):
            if self.table == "documents":
                return SimpleNamespace(data=[
                    {"id": d, "source": DOCS[d][0], "category": None, "title": "", "url": "",
                     "published_at": DOCS[d][1],
                     "metadata": {
                         "image_url": "https://img/mural.jpg",
                         "vision_description": "A mural of a woman holding an apple.",
                         "vision_tags": ["street-art"],
                         "vision_caption_mismatch": False,
                     }}
                    for d in self.ids
                ])
            return super().execute()

    class VisionSupabase(FakeSupabase):
        def table(self, name):
            return VisionDocs(name, self.keyword_calls)

    results = HybridRetriever(VisionSupabase(["art-1"]), EMBED).search("film", k=1, rerank=False)
    assert results[0].metadata["vision_description"] == "A mural of a woman holding an apple."
    assert results[0].metadata["vision_tags"] == ["street-art"]
    assert results[0].metadata["image_url"] == "https://img/mural.jpg"
