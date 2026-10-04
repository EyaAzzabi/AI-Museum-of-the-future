from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from data import fetch_worldbank
from data.process_raw import normalize_worldbank


def test_environmental_indicator_uses_active_world_bank_series():
    assert "EN.GHG.CO2.PC.CE.AR5" in fetch_worldbank.INDICATORS


def test_fetch_indicator_paginates_and_filters_to_covered_countries(monkeypatch):
    pages = [
        [
            {"pages": 2},
            [
                {
                    "country": {"id": "TN", "value": "Tunisia"},
                    "countryiso3code": "TUN",
                    "indicator": {"id": "SP.POP.TOTL", "value": "Population, total"},
                    "date": "2024",
                    "value": 12000000,
                },
                {
                    "country": {"id": "CA", "value": "Canada"},
                    "countryiso3code": "CAN",
                    "indicator": {"id": "SP.POP.TOTL", "value": "Population, total"},
                    "date": "2024",
                    "value": 40000000,
                },
            ],
        ],
        [{"pages": 2}, []],
    ]
    calls = []

    def fake_get(url, params, timeout):
        calls.append(params["page"])
        response = Mock()
        response.json.return_value = pages[params["page"] - 1]
        response.raise_for_status.return_value = None
        return response

    monkeypatch.setattr(fetch_worldbank.requests, "get", fake_get)
    monkeypatch.setattr(fetch_worldbank.time, "sleep", lambda _: None)

    records = fetch_worldbank.fetch_indicator("SP.POP.TOTL")

    assert calls == [1, 2]
    assert [record["country"]["id"] for record in records] == ["TN"]


def test_worldbank_record_normalizes_to_statistics_document():
    record = {
        "country": {"id": "TN", "value": "Tunisia"},
        "countryiso3code": "TUN",
        "indicator": {"id": "SP.POP.TOTL", "value": "Population, total"},
        "date": "2024",
        "value": 12000000,
    }

    normalized = normalize_worldbank(record, "worldbank_global_2026-10-04.json")

    assert normalized["id"] == "TN:SP.POP.TOTL:2024"
    assert normalized["source"] == "worldbank"
    assert normalized["category"] == "statistics"
    assert "Tunisia" in normalized["text"]
    assert "12000000" in normalized["text"]