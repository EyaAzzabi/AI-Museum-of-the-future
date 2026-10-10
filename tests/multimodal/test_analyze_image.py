"""Tests for multimodal/analyze_image.py.

Covers:
- Property 12: VisualDescription structure completeness (task 12.3)
- Property 13: Vision graceful degradation (task 12.4)
- Unit tests for vision component (task 12.5)
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings, strategies as st

from multimodal.analyze_image import VisualDescription, analyze_image


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

VALID_URLS = [
    "https://upload.wikimedia.org/wikipedia/commons/3/3f/Biharwe_entrance.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/Camponotus_flavomarginatus_ant.jpg/320px-Camponotus_flavomarginatus_ant.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/4/47/PNG_transparency_demonstration_1.png",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b9/Above_Gotham.jpg/320px-Above_Gotham.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/2/21/Simple_Coffee_Latte.jpg/320px-Simple_Coffee_Latte.jpg",
]

# A structured mock response from GPT-4o-mini (vision).
# NOTE: keys must be lowercase so the case-sensitive split in analyze_image.py works.
MOCK_VISION_RESPONSE = (
    "objects: person, computer\n"
    "scene: office\n"
    "description: A person working at a computer.\n"
    "tags: technology, work, indoor"
)

MOCK_VISION_RESPONSE_2 = (
    "objects: tree, sky, building\n"
    "scene: outdoor city\n"
    "description: A city street with trees and buildings under a blue sky.\n"
    "tags: urban, nature, architecture"
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fake_embedding_client() -> MagicMock:
    client = MagicMock()
    client.embeddings.create.return_value.data = [MagicMock(embedding=[0.1] * 384)]
    return client


@pytest.fixture(autouse=True)
def _no_real_embedding_model():
    """analyze_image embeds locally; never load the real model in unit tests."""
    with patch("multimodal.analyze_image.build_embedding_client", side_effect=_fake_embedding_client):
        yield


def _make_openai_client(response_text: str = MOCK_VISION_RESPONSE) -> MagicMock:
    """Return a mock OpenAI client for vision + embeddings calls."""
    client = MagicMock()

    # chat.completions.create → vision response
    msg = MagicMock()
    msg.content = response_text
    choice = MagicMock()
    choice.message = msg
    completion = MagicMock()
    completion.choices = [choice]
    client.chat.completions.create.return_value = completion

    # embeddings.create → dummy embedding
    emb_data = MagicMock()
    emb_data.embedding = [0.1] * 384
    emb_response = MagicMock()
    emb_response.data = [emb_data]
    client.embeddings.create.return_value = emb_response

    return client


def _make_requests_get_ok(content: bytes = b"\xff\xd8\xff\xe0fake_jpeg_bytes") -> MagicMock:
    """Return a mock requests.get that returns a 200 response with *content*."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = content
    return MagicMock(return_value=mock_response)


# ─────────────────────────────────────────────────────────────────────────────
# Task 12.3 — Property 12: VisualDescription structure completeness
# Feature: museum-week2-pipeline, Property 12: VisualDescription structure completeness
# Validates: Requirements 6.1
# ─────────────────────────────────────────────────────────────────────────────

@given(source=st.sampled_from(VALID_URLS))
@settings(max_examples=100)
def test_property12_visual_description_structure_completeness(source):
    """Property 12: analyze_image always returns a VisualDescription with the correct field types.

    **Validates: Requirements 6.1**
    """
    # Feature: museum-week2-pipeline, Property 12: VisualDescription structure completeness
    client = _make_openai_client()

    with patch("multimodal.analyze_image.requests.get", _make_requests_get_ok()):
        result = analyze_image(source, openai_client=client)

    assert isinstance(result, VisualDescription), "Result must be a VisualDescription instance"
    assert isinstance(result.objects, list), f"objects must be a list, got {type(result.objects)}"
    assert isinstance(result.scene, str) and result.scene != "", (
        f"scene must be a non-empty string, got {result.scene!r}"
    )
    assert isinstance(result.description, str) and result.description != "", (
        f"description must be a non-empty string, got {result.description!r}"
    )
    assert isinstance(result.tags, list), f"tags must be a list, got {type(result.tags)}"


# ─────────────────────────────────────────────────────────────────────────────
# Task 12.4 — Property 13: Vision graceful degradation
# Feature: museum-week2-pipeline, Property 13: Vision graceful degradation
# Validates: Requirements 6.5
# ─────────────────────────────────────────────────────────────────────────────

@given(source=st.text())
@settings(max_examples=100)
def test_property13_vision_graceful_degradation(source):
    """Property 13: analyze_image never raises and always degrades gracefully for invalid inputs.

    For arbitrary text as source, requests.get is mocked to raise RequestException so that
    analyze_image must always return the degradation sentinel — no exception raised.

    **Validates: Requirements 6.5**
    """
    # Feature: museum-week2-pipeline, Property 13: Vision graceful degradation
    import requests as _requests

    with patch(
        "multimodal.analyze_image.requests.get",
        side_effect=_requests.RequestException("mocked network failure"),
    ):
        try:
            result = analyze_image(source, openai_client=MagicMock())
        except Exception as exc:  # pragma: no cover
            pytest.fail(f"analyze_image raised {type(exc).__name__} for source={source!r}: {exc}")

    # Must be a valid VisualDescription in all cases
    assert isinstance(result, VisualDescription)
    assert result.description == "Image unavailable.", (
        f"Expected 'Image unavailable.' for source={source!r}, got {result.description!r}"
    )
    assert result.scene == "", (
        f"Expected empty scene for degradation, got {result.scene!r}"
    )
    assert result.objects == [], (
        f"Expected empty objects list for degradation, got {result.objects!r}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Task 12.5 — Unit tests for vision component
# Validates: Requirements 6.3, 6.4, 6.7
# ─────────────────────────────────────────────────────────────────────────────

class TestAnalyzeImageUnit:
    """Unit tests for analyze_image() with at least 5 Wikimedia Commons URLs.

    Requirements: 6.3, 6.4, 6.7
    """

    # ── URL 1 ─────────────────────────────────────────────────────────────────

    def test_wikimedia_url_1_description_non_empty(self):
        """analyze_image with Biharwe entrance photo returns non-empty description.

        image URL   : VALID_URLS[0]
        description : non-empty, not 'Image unavailable.'
        verdict     : PASS
        """
        url = VALID_URLS[0]
        client = _make_openai_client()

        with patch("multimodal.analyze_image.requests.get", _make_requests_get_ok()):
            result = analyze_image(url, openai_client=client)

        assert result.description != "", "description must be non-empty"
        assert result.description != "Image unavailable.", (
            "description must not be the degradation sentinel"
        )

    # ── URL 2 ─────────────────────────────────────────────────────────────────

    def test_wikimedia_url_2_description_non_empty(self):
        """analyze_image with ant macro photo returns non-empty description.

        image URL   : VALID_URLS[1]
        description : non-empty, not 'Image unavailable.'
        verdict     : PASS
        """
        url = VALID_URLS[1]
        client = _make_openai_client(MOCK_VISION_RESPONSE_2)

        with patch("multimodal.analyze_image.requests.get", _make_requests_get_ok()):
            result = analyze_image(url, openai_client=client)

        assert result.description != "", "description must be non-empty"
        assert result.description != "Image unavailable.", (
            "description must not be the degradation sentinel"
        )

    # ── URL 3 ─────────────────────────────────────────────────────────────────

    def test_wikimedia_url_3_description_non_empty(self):
        """analyze_image with PNG transparency demo returns non-empty description.

        image URL   : VALID_URLS[2]
        description : non-empty, not 'Image unavailable.'
        verdict     : PASS
        """
        url = VALID_URLS[2]
        client = _make_openai_client()

        with patch("multimodal.analyze_image.requests.get", _make_requests_get_ok()):
            result = analyze_image(url, openai_client=client)

        assert result.description != ""
        assert result.description != "Image unavailable."

    # ── URL 4 ─────────────────────────────────────────────────────────────────

    def test_wikimedia_url_4_description_non_empty(self):
        """analyze_image with Above Gotham photo returns non-empty description.

        image URL   : VALID_URLS[3]
        description : non-empty, not 'Image unavailable.'
        verdict     : PASS
        """
        url = VALID_URLS[3]
        client = _make_openai_client(MOCK_VISION_RESPONSE_2)

        with patch("multimodal.analyze_image.requests.get", _make_requests_get_ok()):
            result = analyze_image(url, openai_client=client)

        assert result.description != ""
        assert result.description != "Image unavailable."

    # ── URL 5 ─────────────────────────────────────────────────────────────────

    def test_wikimedia_url_5_description_non_empty(self):
        """analyze_image with coffee latte photo returns non-empty description.

        image URL   : VALID_URLS[4]
        description : non-empty, not 'Image unavailable.'
        verdict     : PASS
        """
        url = VALID_URLS[4]
        client = _make_openai_client()

        with patch("multimodal.analyze_image.requests.get", _make_requests_get_ok()):
            result = analyze_image(url, openai_client=client)

        assert result.description != ""
        assert result.description != "Image unavailable."

    # ── Timing requirement (Req 6.4) ─────────────────────────────────────────

    def test_returns_within_10_seconds(self):
        """analyze_image must complete within 10 seconds (Req 6.4).

        Uses time.time() assertions — no real network calls are made.
        """
        url = VALID_URLS[0]
        client = _make_openai_client()

        with patch("multimodal.analyze_image.requests.get", _make_requests_get_ok()):
            start = time.time()
            result = analyze_image(url, openai_client=client)
            elapsed = time.time() - start

        assert elapsed < 10.0, (
            f"analyze_image took {elapsed:.2f}s which exceeds the 10 s limit (Req 6.4)"
        )
        assert isinstance(result, VisualDescription)

    # ── Graceful degradation — non-200 HTTP (Req 6.5) ─────────────────────────

    def test_non_200_response_returns_degradation(self):
        """A non-200 HTTP status must return the degradation VisualDescription."""
        url = VALID_URLS[0]
        client = _make_openai_client()

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.content = b""

        with patch("multimodal.analyze_image.requests.get", return_value=mock_response):
            result = analyze_image(url, openai_client=client)

        assert result.description == "Image unavailable."
        assert result.scene == ""
        assert result.objects == []
        assert result.tags == []
        assert result.clip_embedding is None

    # ── Graceful degradation — file not found (Req 6.5) ──────────────────────

    def test_nonexistent_file_path_returns_degradation(self):
        """A non-existent local file path must return the degradation VisualDescription."""
        path = "/tmp/this_file_does_not_exist_museum_test_xyz123.jpg"
        client = _make_openai_client()

        result = analyze_image(path, openai_client=client)

        assert result.description == "Image unavailable."
        assert result.scene == ""
        assert result.objects == []
        assert result.tags == []

    # ── Return type is always VisualDescription ────────────────────────────────

    def test_return_type_is_visual_description(self):
        """analyze_image must always return a VisualDescription instance."""
        url = VALID_URLS[0]
        client = _make_openai_client()

        with patch("multimodal.analyze_image.requests.get", _make_requests_get_ok()):
            result = analyze_image(url, openai_client=client)

        assert isinstance(result, VisualDescription)
        assert isinstance(result.objects, list)
        assert isinstance(result.scene, str)
        assert isinstance(result.description, str)
        assert isinstance(result.tags, list)

    # ── No API key falls back to degradation ─────────────────────────────────

    def test_no_api_key_and_no_client_returns_degradation(self):
        """When openai_client is None and LLM_API_KEY is unset, return degradation."""
        url = VALID_URLS[0]

        with patch("multimodal.analyze_image.requests.get", _make_requests_get_ok()):
            with patch.dict("os.environ", {}, clear=True):
                # Remove LLM_API_KEY if present
                import os
                os.environ.pop("LLM_API_KEY", None)
                result = analyze_image(url, openai_client=None)

        assert result.description == "Image unavailable."
