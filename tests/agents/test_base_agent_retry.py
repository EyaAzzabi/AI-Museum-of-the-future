"""BaseAgent._call_llm retries transient provider errors."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from agents.technology import TechnologyAgent


def test_retries_groq_json_validate_failed() -> None:
    ok = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({"perspective": "p"})))])
    client = MagicMock()
    client.chat.completions.create.side_effect = [
        Exception("Error code: 400 - {'error': {'code': 'json_validate_failed'}}"),
        ok,
    ]
    with patch("time.sleep"):
        payload = TechnologyAgent(client)._call_llm("system", "user")
    assert payload == {"perspective": "p"}
    assert client.chat.completions.create.call_count == 2


def test_retry_wait_follows_the_provider_and_gives_up_on_daily_limits() -> None:
    from agents.base_agent import retry_wait

    assert retry_wait("Error code: 429 ... Please try again in 12.3s.", 0) == 12.8
    assert retry_wait("Error code: 429 ... tokens per day ... Please try again in 24m39.168s.", 0) is None
    assert retry_wait("json_validate_failed", 1) == 4.0
    assert retry_wait("400 invalid model", 0) is None
