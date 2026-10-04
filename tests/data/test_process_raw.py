"""
Property-based and unit tests for data/process_raw.py

Tasks:
  13.1 — Property 1: Processed_Record schema completeness
  13.2 — Property 2: Normalizer deduplication
  13.3 — Unit tests for normalizers

Requirements: 1.8, 1.9, 1.10
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from data.process_raw import (
    dedup,
    normalize_arxiv,
    normalize_gdelt,
    normalize_wikidata,
    normalize_wikimedia,
    normalize_wikipedia_pageviews,
    normalize_wikipedia_summary,
    process_file,
)

# ─────────────────────────────────────────────────────────────────────────────
# Shared constants
# ─────────────────────────────────────────────────────────────────────────────

_SOURCE_FILE = "test_source.json"
_SCHEMA_KEYS = {
    "id", "source", "category", "title", "text",
    "url", "image_url", "date", "lang", "tags",
    "raw_source", "processed_on",
}


# ─────────────────────────────────────────────────────────────────────────────
# Task 13.1 — Property 1: Processed_Record schema completeness
# ─────────────────────────────────────────────────────────────────────────────

# --- Composite strategies for each source type ---

# Strategy for non-whitespace text (survives clean_text stripping)
_printable_text = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters=" .,:-"),
    min_size=1,
    max_size=120,
).filter(lambda s: s.strip() != "")


@st.composite
def gdelt_record(draw):
    """Minimal but valid raw GDELT dict. Title uses printable chars to survive clean_text()."""
    title = draw(_printable_text)
    url = draw(st.text(min_size=1, max_size=40, alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_"
    )).map(lambda s: f"https://example.com/{s}"))
    seendate = draw(st.just("20240101120000"))
    return {
        "title": title,
        "url": url,
        "seendate": seendate,
        "language": draw(st.sampled_from(["English", "Arabic", "French"])),
        "domain": "example.com",
        "sourcecountry": "US",
        "socialimage": None,
    }


@st.composite
def wikimedia_record(draw):
    """Minimal but valid raw Wikimedia dict. Title/description use printable chars."""
    title = draw(_printable_text)
    url = draw(st.text(min_size=1, max_size=40, alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_"
    )).map(lambda s: f"https://commons.wikimedia.org/{s}"))
    return {
        "title": title,
        "url": url,
        "description": draw(_printable_text),
        "license": draw(st.just("CC BY-SA 4.0")),
        "query": "test query",
        "thumb_url": None,
        "date_created": None,
    }


@st.composite
def arxiv_record(draw):
    """Minimal but valid raw arXiv dict. Title/summary use printable chars."""
    record_id = f"2401.{draw(st.integers(min_value=10000, max_value=99999))}"
    return {
        "id": record_id,
        "title": draw(_printable_text),
        "summary": draw(_printable_text),
        "url": f"https://arxiv.org/abs/{record_id}",
        "published": "2024-01-15",
        "categories": ["cs.AI"],
    }


@st.composite
def wikipedia_record(draw):
    """Minimal but valid raw Wikipedia dict — covers both pageviews and summary flavours."""
    kind = draw(st.sampled_from(["pageviews", "summary"]))
    if kind == "pageviews":
        # pageviews records have empty text — but title is non-empty (article name)
        article = draw(_printable_text.map(lambda s: s.replace(" ", "_")))
        return {
            "_wikipedia_kind": "pageviews",
            "article": article,
            "lang": draw(st.sampled_from(["en", "ar", "fr"])),
            "date": "2024-01-01",
            "rank": draw(st.integers(min_value=1, max_value=100)),
            "views": draw(st.integers(min_value=1, max_value=1_000_000)),
        }
    else:
        return {
            "_wikipedia_kind": "summary",
            "page_id": draw(st.integers(min_value=1, max_value=9_999_999)),
            "title": draw(_printable_text),
            "extract": draw(_printable_text),
            "content_urls": "https://en.wikipedia.org/wiki/Article",
            "thumbnail_url": None,
            "lang": "en",
            "description": "A concise description.",
        }


def _normalize_wikipedia_dispatch(raw: dict, source_file: str) -> dict:
    """Helper: dispatch to the correct Wikipedia normalizer based on the internal tag."""
    kind = raw.pop("_wikipedia_kind", "summary")
    if kind == "pageviews":
        return normalize_wikipedia_pageviews(raw, source_file)
    return normalize_wikipedia_summary(raw, source_file)


def _apply_normalizer(raw: dict, source_file: str) -> dict:
    """
    Choose the right normalizer for the raw record.
    The composite strategies embed a discriminator key `_wikipedia_kind`
    for Wikipedia records; all other sources are identified by the presence of
    distinguishing fields.
    """
    if "_wikipedia_kind" in raw:
        return _normalize_wikipedia_dispatch(raw, source_file)
    if "summary" in raw:
        return normalize_arxiv(raw, source_file)
    if "socialimage" in raw or "seendate" in raw:
        return normalize_gdelt(raw, source_file)
    if "license" in raw:
        return normalize_wikimedia(raw, source_file)
    return normalize_gdelt(raw, source_file)


# Feature: museum-week2-pipeline, Property 1: Processed_Record schema completeness
@given(
    raw=st.one_of(
        gdelt_record(),
        wikimedia_record(),
        arxiv_record(),
        wikipedia_record(),
    )
)
@settings(max_examples=100)
def test_processed_record_schema_completeness(raw: dict) -> None:
    """
    **Validates: Requirements 1.8**

    For any raw JSON record from any supported source, when the corresponding
    normalizer processes it successfully, the resulting Processed_Record SHALL have:
    - a non-empty `id`
    - a non-empty `source`
    - a non-empty `category`
    - at least one of `title` or `text` that is non-empty
    """
    record = _apply_normalizer(raw, _SOURCE_FILE)

    # All required schema keys must be present
    assert _SCHEMA_KEYS.issubset(record.keys()), (
        f"Missing keys: {_SCHEMA_KEYS - record.keys()}"
    )

    assert record["id"], f"id must be non-empty, got: {record['id']!r}"
    assert record["source"], f"source must be non-empty, got: {record['source']!r}"
    assert record["category"], f"category must be non-empty, got: {record['category']!r}"
    assert record["title"] or record["text"], (
        "At least one of title/text must be non-empty; "
        f"title={record['title']!r}, text={record['text']!r}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Task 13.2 — Property 2: Normalizer deduplication
# ─────────────────────────────────────────────────────────────────────────────

@st.composite
def raw_records_with_duplicate_ids(draw):
    """
    Generate a list of record dicts where some `id` values are deliberately repeated.
    Records with duplicate ids simulate the scenario that arises when fetch_all.py
    is run twice on the same day.
    """
    # Start with a pool of distinct ids
    pool_size = draw(st.integers(min_value=1, max_value=10))
    id_pool = [f"rec-{i}" for i in range(pool_size)]

    # Pick list length allowing repetitions
    list_size = draw(st.integers(min_value=pool_size, max_value=pool_size * 3))

    records = []
    for _ in range(list_size):
        rec_id = draw(st.sampled_from(id_pool))
        records.append({
            "id": rec_id,
            "source": "gdelt",
            "category": "news",
            "title": draw(st.text(min_size=1, max_size=50)),
            "text": draw(st.text(min_size=1, max_size=50)),
            "url": f"https://example.com/{rec_id}",
            "image_url": None,
            "date": None,
            "lang": "en",
            "tags": [],
            "raw_source": _SOURCE_FILE,
            "processed_on": "2024-01-01",
        })
    return records


# Feature: museum-week2-pipeline, Property 2: Normalizer deduplication
@given(records=st.lists(raw_records_with_duplicate_ids(), min_size=1, max_size=5).map(
    lambda lists: [item for sublist in lists for item in sublist]
))
@settings(max_examples=100)
def test_normalizer_deduplication(records: list[dict]) -> None:
    """
    **Validates: Requirements 1.10**

    For any list of raw records that contains duplicated `id` values within a
    single source, after dedup() is applied the resulting list SHALL contain no
    two records sharing the same `id`.
    """
    result = dedup(records)

    seen_ids: set[str] = set()
    for rec in result:
        rec_id = rec.get("id", "")
        if rec_id:
            assert rec_id not in seen_ids, (
                f"Duplicate id found after dedup: {rec_id!r}"
            )
            seen_ids.add(rec_id)


# ─────────────────────────────────────────────────────────────────────────────
# Task 13.3 — Unit tests for normalizers
# ─────────────────────────────────────────────────────────────────────────────

class TestNormalizeGdelt:
    """Unit tests for normalize_gdelt()."""

    def test_known_raw_dict_produces_expected_fields(self) -> None:
        raw = {
            "title": "AI Breakthrough in 2024",
            "url": "https://news.example.com/ai-2024",
            "seendate": "20240115120000",
            "language": "English",
            "domain": "news.example.com",
            "sourcecountry": "US",
            "socialimage": "https://img.example.com/ai.jpg",
        }
        record = normalize_gdelt(raw, "gdelt_test.json")

        assert record["id"] == "https://news.example.com/ai-2024"
        assert record["source"] == "gdelt"
        assert record["category"] == "news"
        assert record["title"] == "AI Breakthrough in 2024"
        assert record["text"] == "AI Breakthrough in 2024"  # GDELT uses title as text
        assert record["url"] == "https://news.example.com/ai-2024"
        assert record["image_url"] == "https://img.example.com/ai.jpg"
        assert record["date"] == "20240115"
        assert record["lang"] == "English"
        assert "news.example.com" in record["tags"]
        assert "US" in record["tags"]
        assert record["raw_source"] == "gdelt_test.json"
        assert record["processed_on"]  # non-empty date string

    def test_missing_url_generates_stable_id(self) -> None:
        raw = {
            "title": "Some Headline",
            "url": "",
            "seendate": "20240115120000",
            "language": "English",
            "domain": "example.com",
            "sourcecountry": "TN",
        }
        record = normalize_gdelt(raw, _SOURCE_FILE)

        assert record["id"]  # stable hash-based id
        assert len(record["id"]) == 16  # stable_id returns 16-char hex

    def test_html_in_title_is_stripped(self) -> None:
        raw = {
            "title": "<b>Bold</b> headline <br/>here",
            "url": "https://example.com/1",
            "seendate": "20240101000000",
            "language": "en",
            "domain": "example.com",
            "sourcecountry": "US",
        }
        record = normalize_gdelt(raw, _SOURCE_FILE)

        assert "<b>" not in record["title"]
        assert "Bold" in record["title"]


class TestNormalizeWikimedia:
    """Unit tests for normalize_wikimedia()."""

    def test_known_raw_dict_produces_expected_fields(self) -> None:
        raw = {
            "title": "Portrait of a Woman",
            "url": "https://commons.wikimedia.org/wiki/File:Portrait.jpg",
            "description": "An oil painting from the 17th century.",
            "license": "CC BY-SA 4.0",
            "query": "portrait painting",
            "thumb_url": "https://commons.wikimedia.org/thumb/Portrait.jpg",
            "date_created": "2023-05-01",
        }
        record = normalize_wikimedia(raw, "wikimedia_test.json")

        assert record["id"] == "https://commons.wikimedia.org/wiki/File:Portrait.jpg"
        assert record["source"] == "wikimedia"
        assert record["category"] == "image"
        assert record["title"] == "Portrait of a Woman"
        assert record["text"] == "An oil painting from the 17th century."
        assert record["image_url"] == "https://commons.wikimedia.org/thumb/Portrait.jpg"
        assert record["date"] == "2023-05-01"
        assert "CC BY-SA 4.0" in record["tags"]
        assert "portrait painting" in record["tags"]
        assert record["raw_source"] == "wikimedia_test.json"

    def test_missing_url_generates_stable_id(self) -> None:
        raw = {
            "title": "No URL Image",
            "url": "",
            "description": "Some description",
            "license": "CC0",
            "query": "test",
        }
        record = normalize_wikimedia(raw, _SOURCE_FILE)

        assert record["id"]  # stable hash-based id

    def test_thumb_url_used_as_image_url_when_present(self) -> None:
        raw = {
            "title": "Test",
            "url": "https://commons.example.com/file.jpg",
            "description": "desc",
            "license": "CC0",
            "query": "test",
            "thumb_url": "https://commons.example.com/thumb/file.jpg",
        }
        record = normalize_wikimedia(raw, _SOURCE_FILE)

        assert record["image_url"] == "https://commons.example.com/thumb/file.jpg"


class TestNormalizeArxiv:
    """Unit tests for normalize_arxiv()."""

    def test_known_raw_dict_produces_expected_fields(self) -> None:
        raw = {
            "id": "2401.12345",
            "title": "Large Language Models in Science",
            "summary": "We present an overview of LLMs applied to scientific research.",
            "url": "https://arxiv.org/abs/2401.12345",
            "published": "2024-01-15",
            "categories": ["cs.AI", "cs.LG"],
        }
        record = normalize_arxiv(raw, "arxiv_test.json")

        assert record["id"] == "2401.12345"
        assert record["source"] == "arxiv"
        assert record["category"] == "science"
        assert record["title"] == "Large Language Models in Science"
        assert "LLMs" in record["text"]
        assert record["url"] == "https://arxiv.org/abs/2401.12345"
        assert record["date"] == "2024-01-15"
        assert record["lang"] == "en"
        assert "cs.AI" in record["tags"]
        assert record["raw_source"] == "arxiv_test.json"

    def test_date_truncated_to_10_chars(self) -> None:
        raw = {
            "id": "2401.00001",
            "title": "Test Paper",
            "summary": "Abstract.",
            "url": "https://arxiv.org/abs/2401.00001",
            "published": "2024-01-15T12:00:00Z",  # longer datetime string
            "categories": [],
        }
        record = normalize_arxiv(raw, _SOURCE_FILE)

        assert record["date"] == "2024-01-15"


class TestNormalizeWikipediaPageviews:
    """Unit tests for normalize_wikipedia_pageviews()."""

    def test_known_raw_dict_produces_expected_fields(self) -> None:
        raw = {
            "article": "Artificial_intelligence",
            "lang": "en",
            "date": "2024-01-01",
            "rank": 5,
            "views": 123456,
        }
        record = normalize_wikipedia_pageviews(raw, "wikipedia_pageviews_test.json")

        assert record["source"] == "wikipedia"
        assert record["category"] == "culture"
        assert record["title"] == "Artificial intelligence"  # underscores replaced
        assert record["url"] == "https://en.wikipedia.org/wiki/Artificial_intelligence"
        assert record["lang"] == "en"
        assert record["text"] == ""  # pageviews only, no summary text
        assert record["date"] == "2024-01-01"
        assert any("rank:5" in tag for tag in record["tags"])
        assert any("views:123456" in tag for tag in record["tags"])
        assert record["raw_source"] == "wikipedia_pageviews_test.json"

    def test_id_is_stable_hash(self) -> None:
        raw = {
            "article": "Climate_change",
            "lang": "fr",
            "date": "2024-02-01",
            "rank": 10,
            "views": 5000,
        }
        record1 = normalize_wikipedia_pageviews(raw.copy(), _SOURCE_FILE)
        record2 = normalize_wikipedia_pageviews(raw.copy(), _SOURCE_FILE)

        assert record1["id"] == record2["id"]  # deterministic / stable


class TestNormalizeWikipediaSummary:
    """Unit tests for normalize_wikipedia_summary()."""

    def test_known_raw_dict_produces_expected_fields(self) -> None:
        raw = {
            "page_id": 12345,
            "title": "Museum",
            "extract": "A museum is an institution that cares for collections of artifacts.",
            "content_urls": "https://en.wikipedia.org/wiki/Museum",
            "thumbnail_url": "https://upload.wikimedia.org/museum.jpg",
            "lang": "en",
            "description": "Cultural institution",
        }
        record = normalize_wikipedia_summary(raw, "wikipedia_summaries_test.json")

        assert record["id"] == "12345"
        assert record["source"] == "wikipedia"
        assert record["category"] == "history"
        assert record["title"] == "Museum"
        assert "artifacts" in record["text"]
        assert record["url"] == "https://en.wikipedia.org/wiki/Museum"
        assert record["image_url"] == "https://upload.wikimedia.org/museum.jpg"
        assert record["lang"] == "en"
        assert record["raw_source"] == "wikipedia_summaries_test.json"

    def test_missing_page_id_falls_back_to_stable_id(self) -> None:
        raw = {
            "title": "Unknown Article",
            "extract": "Some text.",
            "content_urls": "",
            "lang": "en",
            "description": "",
        }
        record = normalize_wikipedia_summary(raw, _SOURCE_FILE)

        assert record["id"]  # non-empty fallback id


class TestNormalizeWikidata:
    """Unit tests for normalize_wikidata()."""

    def test_known_raw_dict_with_person_produces_expected_fields(self) -> None:
        raw = {
            "person": "http://www.wikidata.org/entity/Q937",
            "personLabel": "Albert Einstein",
            "fieldLabel": "theoretical physics",
            "countryLabel": "Germany",
        }
        record = normalize_wikidata(raw, "wikidata_test.json")

        assert record["id"] == "http://www.wikidata.org/entity/Q937"
        assert record["source"] == "wikidata"
        assert record["category"] == "history"
        assert record["title"] == "Albert Einstein"
        assert record["url"] == "http://www.wikidata.org/entity/Q937"
        assert record["raw_source"] == "wikidata_test.json"

    def test_wikidata_tags_exclude_http_values(self) -> None:
        """Tags should only include non-URL string values."""
        raw = {
            "person": "http://www.wikidata.org/entity/Q937",
            "personLabel": "Marie Curie",
            "fieldLabel": "chemistry",
        }
        record = normalize_wikidata(raw, _SOURCE_FILE)

        for tag in record["tags"]:
            assert not tag.startswith("http"), (
                f"Unexpected URL in tags: {tag}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Task 13.3 — process_file edge cases (empty/malformed input)
# ─────────────────────────────────────────────────────────────────────────────

class TestProcessFileFiltering:
    """
    Tests for process_file() — verifies that records where both title and text
    are empty are dropped, and that malformed input is handled gracefully.

    Requirements: 1.8, 1.9
    """

    def test_gdelt_record_with_empty_title_and_text_is_dropped(
        self, tmp_path: Path
    ) -> None:
        """
        A GDELT record whose title (and therefore text) is empty should be
        filtered out by process_file, which drops records where both title
        and text are empty.
        """
        raw = [
            {
                "title": "",
                "url": "https://example.com/empty",
                "seendate": "20240101000000",
                "language": "English",
                "domain": "example.com",
                "sourcecountry": "US",
            }
        ]
        f = tmp_path / "gdelt_test_20240101.json"
        f.write_text(json.dumps(raw), encoding="utf-8")

        result = process_file(f)
        assert result == [], (
            "Expected empty list when both title and text are empty"
        )

    def test_arxiv_record_with_empty_title_and_summary_is_dropped(
        self, tmp_path: Path
    ) -> None:
        raw = [
            {
                "id": "2401.99999",
                "title": "",
                "summary": "",
                "url": "https://arxiv.org/abs/2401.99999",
                "published": "2024-01-01",
                "categories": [],
            }
        ]
        f = tmp_path / "arxiv_empty_20240101.json"
        f.write_text(json.dumps(raw), encoding="utf-8")

        result = process_file(f)
        assert result == []

    def test_malformed_json_returns_empty_list(self, tmp_path: Path) -> None:
        """process_file should return [] on a JSON parse error (req 1.9)."""
        f = tmp_path / "gdelt_malformed_20240101.json"
        f.write_text("this is not JSON {{{", encoding="utf-8")

        result = process_file(f)
        assert result == []

    def test_unknown_source_prefix_returns_empty_list(self, tmp_path: Path) -> None:
        """process_file returns [] for files with no matching normalizer."""
        f = tmp_path / "unknown_source_20240101.json"
        f.write_text(json.dumps([{"id": "x", "title": "Test"}]), encoding="utf-8")

        result = process_file(f)
        assert result == []

    def test_valid_arxiv_record_is_returned(self, tmp_path: Path) -> None:
        """Sanity-check: a properly-formed arxiv record survives process_file."""
        raw = [
            {
                "id": "2401.55555",
                "title": "Valid Paper Title",
                "summary": "This paper discusses important topics in AI research.",
                "url": "https://arxiv.org/abs/2401.55555",
                "published": "2024-01-10",
                "categories": ["cs.AI"],
            }
        ]
        f = tmp_path / "arxiv_valid_20240101.json"
        f.write_text(json.dumps(raw), encoding="utf-8")

        result = process_file(f)
        assert len(result) == 1
        assert result[0]["id"] == "2401.55555"
        assert result[0]["source"] == "arxiv"

    def test_duplicate_ids_are_deduplicated_by_process_file(
        self, tmp_path: Path
    ) -> None:
        """process_file must deduplicate by id (requirement 1.10)."""
        raw = [
            {
                "id": "2401.11111",
                "title": "Duplicate Paper",
                "summary": "Abstract text here.",
                "url": "https://arxiv.org/abs/2401.11111",
                "published": "2024-01-01",
                "categories": [],
            },
            {
                "id": "2401.11111",
                "title": "Duplicate Paper (copy)",
                "summary": "Abstract text here again.",
                "url": "https://arxiv.org/abs/2401.11111",
                "published": "2024-01-01",
                "categories": [],
            },
        ]
        f = tmp_path / "arxiv_dupes_20240101.json"
        f.write_text(json.dumps(raw), encoding="utf-8")

        result = process_file(f)
        assert len(result) == 1

    def test_non_dict_items_in_list_are_skipped(self, tmp_path: Path) -> None:
        """process_file should skip non-dict entries in the JSON array."""
        raw = [
            "just a string",
            42,
            {
                "id": "2401.22222",
                "title": "Good Record",
                "summary": "Abstract.",
                "url": "https://arxiv.org/abs/2401.22222",
                "published": "2024-01-01",
                "categories": [],
            },
        ]
        f = tmp_path / "arxiv_mixed_20240101.json"
        f.write_text(json.dumps(raw), encoding="utf-8")

        result = process_file(f)
        assert len(result) == 1
        assert result[0]["id"] == "2401.22222"
