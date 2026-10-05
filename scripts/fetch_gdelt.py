"""Pull recent news articles from the GDELT 2.0 DOC API into data/raw/gdelt/.

GDELT is keyless. To get Arab-world + global coverage without firing many
back-to-back requests (GDELT's free API rate-limits aggressively and
sequential calls 429/timeout unpredictably), this issues ONE combined query
per topic: (sourcelang:X OR sourcelang:Y OR ...) plus the topic keyword,
covering multiple languages/regions in a single request.
"""

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "data"))
from regions import LANGUAGES  # noqa: E402
from topics import ALL_TOPICS, DEDICATED_EVENT_TOPICS  # noqa: E402

RAW_DIR = REPO_ROOT / "data" / "raw" / "gdelt"

# Museum-relevant topics, spanning science/tech, culture/media and
# social/economic angles (see data/topics.py), plus specific major current
# events a generic topic wouldn't reliably surface. "Palestine" is fetched
# separately as a dedicated regional topic, not part of this list.
TOPICS = ALL_TOPICS + DEDICATED_EVENT_TOPICS

MAX_RECORDS = 100


def build_query(topic: str, languages: list[str]) -> str:
    lang_clause = " OR ".join(f"sourcelang:{lang}" for lang in languages)
    return f"{topic} ({lang_clause})"


def fetch_topic(topic: str, languages: list[str], retries: int = 5) -> dict:
    query = build_query(topic, languages)
    params = urllib.parse.urlencode({
        "query": query,
        "mode": "artlist",
        "maxrecords": MAX_RECORDS,
        "format": "json",
        "sort": "hybridrel",
    })
    url = f"https://api.gdeltproject.org/api/v2/doc/doc?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "ai-museum-of-the-future/0.1"})

    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            last_err = e
            wait = 60 if e.code == 429 else 20
            print(f"[gdelt] topic={topic!r} attempt {attempt + 1}/{retries} HTTP {e.code}, backing off {wait}s")
            time.sleep(wait)
        except Exception as e:
            last_err = e
            print(f"[gdelt] topic={topic!r} attempt {attempt + 1}/{retries} error: {e}, backing off 20s")
            time.sleep(20)
    raise last_err


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    languages = list(LANGUAGES.values())  # English, Arabic, French, Spanish, Chinese, Hindi, Portuguese, Russian
    manifest = []

    pending = [t for t in TOPICS if not (RAW_DIR / f"{t.replace(' ', '_')}.json").exists()]
    print(f"[gdelt] {len(TOPICS) - len(pending)} topics already fetched, {len(pending)} pending")

    for i, topic in enumerate(pending):
        try:
            data = fetch_topic(topic, languages)
        except Exception as e:
            print(f"[gdelt] FAILED topic={topic!r}: {e}")
            continue

        articles = data.get("articles", [])
        fname = f"{topic.replace(' ', '_')}.json"
        out_path = RAW_DIR / fname
        out_path.write_text(json.dumps(articles, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[gdelt] topic={topic!r} -> {len(articles)} articles -> {out_path}")
        manifest.append({"topic": topic, "count": len(articles), "file": fname})

        if i < len(pending) - 1:
            time.sleep(30)  # space out requests between topics

    manifest_path = RAW_DIR / "_manifest.json"
    existing_topics = []
    if manifest_path.exists():
        existing_topics = json.loads(manifest_path.read_text(encoding="utf-8")).get("topics", [])
    seen = {t["topic"] for t in manifest}
    merged = manifest + [t for t in existing_topics if t["topic"] not in seen]

    manifest_path.write_text(
        json.dumps({
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "languages_queried": languages,
            "topics": merged,
        }, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
