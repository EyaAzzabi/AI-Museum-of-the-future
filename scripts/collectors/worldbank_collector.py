"""
World Bank Collector — AI Museum of the Future
===============================================
Source      : World Bank Open Data API v2 (https://api.worldbank.org/v2/)
Coverage    : Tunisia socioeconomic indicators, 2020–2026
Languages   : English (API returns English metadata)
Output      : data/raw/worldbank/worldbank_indicators.json
Volume      : ~50 indicator series (light mode)

No API key required. Free & public.
Official docs: https://datahelpdesk.worldbank.org/knowledgebase/articles/889392
"""

import json
import time
from datetime import datetime
from pathlib import Path

import requests

# ── Output directory ──────────────────────────────────────────────────────────
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "worldbank"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── World Bank API config ─────────────────────────────────────────────────────
WB_API_BASE = "https://api.worldbank.org/v2"
COUNTRY     = "TN"          # Tunisia ISO2 code
DATE_RANGE  = "2020:2026"   # World Bank uses YYYY:YYYY format
PER_PAGE    = 100           # max results per page

# ── Indicators to collect (by theme) ─────────────────────────────────────────
# Format: { "code": "WB_INDICATOR_CODE", "name": "Human readable name", "theme": "..." }
INDICATORS = [
    # --- Economy ---
    {"code": "NY.GDP.MKTP.CD",      "name": "GDP (current US$)",                           "theme": "economy"},
    {"code": "NY.GDP.PCAP.CD",      "name": "GDP per capita (current US$)",                "theme": "economy"},
    {"code": "NY.GDP.MKTP.KD.ZG",   "name": "GDP growth (annual %)",                       "theme": "economy"},
    {"code": "FP.CPI.TOTL.ZG",      "name": "Inflation, consumer prices (annual %)",       "theme": "economy"},
    {"code": "SL.UEM.TOTL.ZS",      "name": "Unemployment, total (% of labor force)",      "theme": "economy"},
    {"code": "SL.UEM.1524.ZS",      "name": "Youth unemployment (% ages 15-24)",           "theme": "economy"},
    {"code": "BX.KLT.DINV.WD.GD.ZS","name": "Foreign direct investment, net inflows (% GDP)", "theme": "economy"},
    {"code": "BM.KLT.DINV.WD.GD.ZS","name": "Foreign direct investment, net outflows (% GDP)","theme": "economy"},
    {"code": "GC.DOD.TOTL.GD.ZS",   "name": "Central government debt (% of GDP)",          "theme": "economy"},
    {"code": "NE.TRD.GNFS.ZS",      "name": "Trade (% of GDP)",                            "theme": "economy"},
    {"code": "ST.INT.ARVL",         "name": "International tourism, number of arrivals",   "theme": "economy"},

    # --- Society & Demographics ---
    {"code": "SP.POP.TOTL",         "name": "Population, total",                           "theme": "politics_society"},
    {"code": "SP.URB.TOTL.IN.ZS",   "name": "Urban population (% of total)",               "theme": "politics_society"},
    {"code": "SP.POP.GROW",         "name": "Population growth (annual %)",                "theme": "politics_society"},
    {"code": "SM.POP.NETM",         "name": "Net migration",                               "theme": "politics_society"},
    {"code": "SI.POV.NAHC",         "name": "Poverty headcount ratio at national poverty lines (% of population)", "theme": "politics_society"},
    {"code": "SI.DST.FRST.20",      "name": "Income share held by lowest 20%",             "theme": "politics_society"},
    {"code": "IQ.CPA.PUBS.XQ",      "name": "CPIA public sector management index",         "theme": "politics_society"},

    # --- Science & Technology ---
    {"code": "IT.NET.USER.ZS",      "name": "Individuals using the Internet (% of population)", "theme": "science_tech"},
    {"code": "IT.CEL.SETS.P2",      "name": "Mobile cellular subscriptions (per 100 people)",   "theme": "science_tech"},
    {"code": "GB.XPD.RSDV.GD.ZS",  "name": "Research and development expenditure (% of GDP)",  "theme": "science_tech"},
    {"code": "IP.PAT.RESD",         "name": "Patent applications, residents",              "theme": "science_tech"},
    {"code": "SE.TER.ENRR",         "name": "School enrollment, tertiary (% gross)",       "theme": "science_tech"},
    {"code": "SE.ADT.LITR.ZS",      "name": "Literacy rate, adult total (% ages 15+)",     "theme": "science_tech"},

    # --- Environment ---
    {"code": "EN.ATM.CO2E.PC",      "name": "CO2 emissions (metric tons per capita)",      "theme": "environment"},
    {"code": "EN.ATM.CO2E.KT",      "name": "CO2 emissions (kt)",                          "theme": "environment"},
    {"code": "ER.H2O.FWTL.ZS",      "name": "Annual freshwater withdrawals (% of internal resources)", "theme": "environment"},
    {"code": "AG.LND.FRST.ZS",      "name": "Forest area (% of land area)",                "theme": "environment"},
    {"code": "EG.ELC.RNWX.ZS",      "name": "Renewable electricity output (% of total)",  "theme": "environment"},
    {"code": "EG.USE.PCAP.KG.OE",   "name": "Energy use (kg of oil equivalent per capita)","theme": "environment"},

    # --- Health (relevant for 2020-2026 — COVID era) ---
    {"code": "SH.XPD.CHEX.GD.ZS",  "name": "Current health expenditure (% of GDP)",       "theme": "politics_society"},
    {"code": "SP.DYN.LE00.IN",      "name": "Life expectancy at birth, total (years)",     "theme": "politics_society"},
    {"code": "SH.MED.BEDS.ZS",      "name": "Hospital beds (per 1,000 people)",            "theme": "politics_society"},
]


def fetch_indicator(indicator_code: str, indicator_name: str, theme: str) -> dict | None:
    """
    Fetches yearly values for a single World Bank indicator for Tunisia.
    Returns a structured dict or None on failure.
    """
    url = f"{WB_API_BASE}/country/{COUNTRY}/indicator/{indicator_code}"
    params = {
        "date":     DATE_RANGE,
        "format":   "json",
        "per_page": PER_PAGE,
    }

    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"  [ERROR] Request failed for {indicator_code}: {e}")
        return None
    except (json.JSONDecodeError, ValueError):
        print(f"  [ERROR] JSON decode failed for {indicator_code}")
        return None

    # World Bank API returns [metadata, data] list
    if not isinstance(data, list) or len(data) < 2:
        print(f"  [WARN] Unexpected response format for {indicator_code}")
        return None

    records_raw = data[1]
    if not records_raw:
        print(f"  [WARN] No data for {indicator_code} (Tunisia, {DATE_RANGE})")
        return None

    # Build clean yearly series — skip null values
    yearly_values = {}
    for record in records_raw:
        year  = record.get("date", "")
        value = record.get("value")
        if year and value is not None:
            yearly_values[year] = value

    if not yearly_values:
        print(f"  [WARN] All values null for {indicator_code}")
        return None

    # Latest non-null value
    latest_year  = max(yearly_values.keys())
    latest_value = yearly_values[latest_year]

    return {
        "source":         "worldbank",
        "theme":          theme,
        "collected_at":   datetime.utcnow().isoformat(),
        "country":        "Tunisia",
        "country_code":   COUNTRY,
        "indicator_code": indicator_code,
        "indicator_name": indicator_name,
        "date_range":     DATE_RANGE,
        "latest_year":    latest_year,
        "latest_value":   latest_value,
        "yearly_values":  dict(sorted(yearly_values.items())),  # sorted by year
        "data_points":    len(yearly_values),
    }


def run():
    """Main collection loop — fetches all indicators and saves to JSON."""
    print("=" * 60)
    print("World Bank Collector — Tunisia 2020-2026")
    print("=" * 60)

    results: list[dict] = []
    failed:  list[str]  = []

    for i, ind in enumerate(INDICATORS, start=1):
        code  = ind["code"]
        name  = ind["name"]
        theme = ind["theme"]

        print(f"\n[{i}/{len(INDICATORS)}] [{theme}] {code}")
        print(f"  {name}")

        result = fetch_indicator(code, name, theme)

        if result:
            results.append(result)
            print(f"  ✓ {result['data_points']} data points | Latest: {result['latest_year']} = {result['latest_value']}")
        else:
            failed.append(code)

        # Polite delay between requests
        if i < len(INDICATORS):
            time.sleep(0.5)

    # ── Save results ──────────────────────────────────────────────────────────
    output_file = OUTPUT_DIR / "worldbank_indicators.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"✓ Done. {len(results)} indicators saved, {len(failed)} failed.")
    if failed:
        print(f"  Failed: {failed}")
    print(f"✓ Output: {output_file}")
    print("=" * 60)


if __name__ == "__main__":
    run()
