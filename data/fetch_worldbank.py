"""Fetch selected World Bank indicators for the project's covered countries."""

import json
import sys
import time
from datetime import date
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.regions import ALL_COUNTRIES

RAW_DIR = Path(__file__).parent / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://api.worldbank.org/v2/country/all/indicator"
COUNTRY_CODES = frozenset(ALL_COUNTRIES)
START_YEAR = 2015
END_YEAR = date.today().year
PAGE_SIZE = 1000
DELAY_SECONDS = 0.5

INDICATORS = {
    "SP.POP.TOTL": "Population, total",
    "NY.GDP.PCAP.CD": "GDP per capita (current US$)",
    "IT.NET.USER.ZS": "Individuals using the Internet (% of population)",
    "EN.GHG.CO2.PC.CE.AR5": "CO2 emissions excluding LULUCF per capita (t CO2e/capita)",
}


def fetch_indicator(indicator_id: str) -> list[dict]:
    """Fetch one indicator and retain covered countries with actual values."""
    records: list[dict] = []
    page = 1

    while True:
        try:
            response = requests.get(
                f"{BASE_URL}/{indicator_id}",
                params={
                    "format": "json",
                    "date": f"{START_YEAR}:{END_YEAR}",
                    "per_page": PAGE_SIZE,
                    "page": page,
                },
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            print(f"  [World Bank] request error for {indicator_id}: {exc}")
            break

        if not isinstance(payload, list) or len(payload) < 2:
            print(f"  [World Bank] unexpected response for {indicator_id}")
            break

        metadata, page_records = payload[0], payload[1]
        if isinstance(page_records, list):
            for record in page_records:
                country = record.get("country") or {}
                country_code = country.get("iso2Code") or country.get("id")
                if (
                    country_code in COUNTRY_CODES
                    and record.get("value") is not None
                ):
                    records.append(record)

        pages = int(metadata.get("pages") or 1)
        if page >= pages:
            break
        page += 1
        time.sleep(DELAY_SECONDS)

    return records


def main() -> None:
    print("=== World Bank fetch started ===")
    records: list[dict] = []

    for indicator_id, label in INDICATORS.items():
        indicator_records = fetch_indicator(indicator_id)
        records.extend(indicator_records)
        print(f"  {label}: {len(indicator_records)} observations")
        time.sleep(DELAY_SECONDS)

    if records:
        out_file = RAW_DIR / f"worldbank_global_{date.today().isoformat()}.json"
        with open(out_file, "w", encoding="utf-8") as output:
            json.dump(records, output, ensure_ascii=False, indent=2)
        print(f"  -> saved {len(records)} observations to {out_file.name}")
    else:
        print("  No observations returned; no raw file written.")

    print("=== World Bank fetch complete ===")


if __name__ == "__main__":
    main()