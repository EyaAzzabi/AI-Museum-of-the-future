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
