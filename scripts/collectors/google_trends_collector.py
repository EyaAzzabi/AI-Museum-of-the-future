"""
Google Trends Collector — AI Museum of the Future
==================================================
Source      : Google Trends via pytrends (unofficial wrapper)
Coverage    : Tunisia search trends, 2020–2026
Languages   : French + English keywords
Output      : data/raw/google_trends/google_trends.json
Volume      : ~50 topic entries (light mode)

No API key required. Uses pytrends (pip install pytrends).

NOTE: Google Trends has rate limits. The script includes automatic
      retries and delays. If blocked (429 error), wait ~1 hour and retry.
"""

import json
import time
import random
from datetime import datetime
from pathlib import Path

try:
    from pytrends.request import TrendReq
    from pytrends.exceptions import ResponseError
except ImportError:
    raise ImportError(
        "pytrends is required. Install it with: pip install pytrends"
    )

# ── Output directory ──────────────────────────────────────────────────────────
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "google_trends"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── pytrends configuration ────────────────────────────────────────────────────
# hl = interface language, tz = timezone offset (Tunisia = UTC+1, so 60 min behind UTC → -60)
PYTRENDS_HL = "fr"
PYTRENDS_TZ = 60        # UTC+1 (Tunisia)
GEO = "TN"              # Tunisia country code
TIMEFRAME = "2020-01-01 2026-12-31"

# ── Topics to query (max 5 keywords per pytrends request) ────────────────────
TOPIC_GROUPS = [
    # Politics & Society
    {
        "theme": "politics_society",
        "keywords": ["Kais Saied", "constitution tunisie", "elections tunisie", "crise politique", "droits humains"],
    },
    {
        "theme": "politics_society",
        "keywords": ["Tunisie politique", "parlement tunisie", "liberté presse tunisie"],
    },
    # Economy
    {
        "theme": "economy",
        "keywords": ["chômage tunisie", "inflation tunisie", "FMI tunisie", "économie tunisie", "migration tunisie"],
    },
    {
        "theme": "economy",
        "keywords": ["tourisme tunisie", "exportations tunisie", "dinar tunisien"],
    },
    # Culture & Arts
    {
        "theme": "culture_arts",
        "keywords": ["cinéma tunisien", "musique tunisie", "festival carthage", "art tunisie", "patrimoine tunisie"],
    },
    {
        "theme": "culture_arts",
        "keywords": ["ramadan tunisie", "mode tunisie", "cuisine tunisienne"],
    },
    # Science & Technology
    {
        "theme": "science_tech",
        "keywords": ["startup tunisie", "numérique tunisie", "intelligence artificielle tunisie", "tech tunisie"],
    },
    {
        "theme": "science_tech",
        "keywords": ["université tunisie", "innovation tunisie", "recherche scientifique tunisie"],
    },
    # Environment
    {
        "theme": "environment",
        "keywords": ["sécheresse tunisie", "eau tunisie", "changement climatique tunisie", "pollution tunisie"],
    },
    {
        "theme": "environment",
        "keywords": ["énergie solaire tunisie", "environnement tunisie"],
    },
]

MAX_RETRIES = 3
RETRY_DELAY = 60    # seconds to wait between retries on rate limit


def fetch_interest_over_time(pytrends: TrendReq, keywords: list[str], theme: str) -> dict | None:
    """
    Fetches interest over time for a list of keywords in Tunisia.
    Returns a structured dict with the trend data.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            pytrends.build_payload(
                kw_list=keywords,
                geo=GEO,
                timeframe=TIMEFRAME,
            )
            df = pytrends.interest_over_time()

            if df is None or df.empty:
                print(f"  [WARN] No data returned for: {keywords}")
                return None

            # Drop the 'isPartial' column if present
            if "isPartial" in df.columns:
                df = df.drop(columns=["isPartial"])

            # Convert to serializable format
            records = []
            for date, row in df.iterrows():
                records.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "values": {kw: int(row[kw]) for kw in keywords if kw in row},
                })

            # Compute average interest per keyword across the period
            averages = {}
            for kw in keywords:
                if kw in df.columns:
                    averages[kw] = round(float(df[kw].mean()), 2)

            return {
                "source":        "google_trends",
                "theme":         theme,
                "keywords":      keywords,
                "geo":           GEO,
                "timeframe":     TIMEFRAME,
                "collected_at":  datetime.utcnow().isoformat(),
                "average_interest": averages,
                "weekly_data":   records,
                "total_weeks":   len(records),
            }

        except ResponseError as e:
            if "429" in str(e) or "Too Many Requests" in str(e):
                if attempt < MAX_RETRIES:
                    wait = RETRY_DELAY * attempt + random.randint(5, 20)
                    print(f"  [RATE LIMIT] Attempt {attempt}/{MAX_RETRIES}. Waiting {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"  [ERROR] Rate limit hit after {MAX_RETRIES} attempts for: {keywords}")
                    return None
            else:
                print(f"  [ERROR] ResponseError for {keywords}: {e}")
                return None
        except Exception as e:
            print(f"  [ERROR] Unexpected error for {keywords}: {e}")
            return None

    return None


def run():
    """Main collection loop — fetches all topic groups and saves to JSON."""
    print("=" * 60)
    print("Google Trends Collector — Tunisia 2020-2026")
    print("=" * 60)

    # Initialize pytrends session
    pytrends = TrendReq(hl=PYTRENDS_HL, tz=PYTRENDS_TZ, timeout=(10, 25), retries=2, backoff_factor=0.5)

    results: list[dict] = []

    for i, group in enumerate(TOPIC_GROUPS, start=1):
        keywords = group["keywords"]
        theme    = group["theme"]

        print(f"\n[{i}/{len(TOPIC_GROUPS)}] Theme: {theme}")
        print(f"  Keywords: {keywords}")

        data = fetch_interest_over_time(pytrends, keywords, theme)

        if data:
            results.append(data)
            print(f"  ✓ {data['total_weeks']} weekly data points collected")
            # Show top keyword
            if data["average_interest"]:
                top_kw = max(data["average_interest"], key=data["average_interest"].get)
                print(f"  Top keyword: '{top_kw}' (avg interest: {data['average_interest'][top_kw]})")
        else:
            print(f"  ✗ Skipped (no data or error)")

        # Polite delay between requests to avoid rate limiting
        if i < len(TOPIC_GROUPS):
            delay = random.uniform(3, 7)
            print(f"  Waiting {delay:.1f}s before next request...")
            time.sleep(delay)

    # ── Save results ──────────────────────────────────────────────────────────
    output_file = OUTPUT_DIR / "google_trends.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print(f"✓ Done. {len(results)}/{len(TOPIC_GROUPS)} topic groups collected.")
    print(f"✓ Output: {output_file}")
    print("=" * 60)
    if len(results) < len(TOPIC_GROUPS):
        print("\n⚠ Some groups failed. If you see 429 errors, wait ~1 hour and re-run.")


if __name__ == "__main__":
    run()
