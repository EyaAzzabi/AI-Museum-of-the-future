"""Keep tests hermetic: no on-disk LLM/HyDE caches shared with real runs."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolated_caches(tmp_path, monkeypatch):
    monkeypatch.setenv("HYDE_CACHE_DIR", str(tmp_path / "hyde-cache"))
    monkeypatch.delenv("LLM_CACHE_DIR", raising=False)
