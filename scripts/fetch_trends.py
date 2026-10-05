"""Pull topic volume-over-time from the GDELT DOC API into data/raw/trends/.

Fills the "Social & Cultural Trends" slot that Wikipedia Pageviews would
have covered, had Wikimedia not been blocked on this network. Reuses the
same keyless GDELT infrastructure already proven reliable for news, via
mode=timelinevol: article-volume-over-time per topic acts as a coverage
trend line (rising/falling attention), which is the same kind of signal
Wikipedia Pageviews would give (what's getting more attention over time),
just derived from news volume instead of article views.
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
from topics import ALL_TOPICS, DEDICATED_EVENT_TOPICS  # noqa: E402

RAW_DIR = REPO_ROOT / "data" / "raw" / "trends"

TOPICS = ALL_TOPICS + DEDICATED_EVENT_TOPICS + ["Palestine"]


def fetch_timeline(topic: str, retries: int = 5) -> dict:
    params = urllib.parse.urlencode({
        "query": topic,
        "mode": "timelinevol",
        "format": "json",
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
            print(f"[trends] topic={topic!r} attempt {attempt + 1}/{retries} HTTP {e.code}, backing off {wait}s")
            time.sleep(wait)
        except Exception as e:
            last_err = e
            print(f"[trends] topic={topic!r} attempt {attempt + 1}/{retries} error: {e}, backing off 20s")
            time.sleep(20)
    raise last_err


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []
    pending = [t for t in TOPICS if not (RAW_DIR / f"{t.replace(' ', '_').lower()}.json").exists()]
    print(f"[trends] {len(TOPICS) - len(pending)} topics already fetched, {len(pending)} pending")

    for i, topic in enumerate(pending):
        try:
            data = fetch_timeline(topic)
        except Exception as e:
            print(f"[trends] FAILED topic={topic!r}: {e}")
            continue

        timeline = data.get("timeline", [])
        fname = f"{topic.replace(' ', '_').lower()}.json"
        out_path = RAW_DIR / fname
        out_path.write_text(json.dumps(timeline, indent=2, ensure_ascii=False), encoding="utf-8")
        points = sum(len(series.get("data", [])) for series in timeline)
        print(f"[trends] topic={topic!r} -> {points} data points -> {out_path}")
        manifest.append({"topic": topic, "points": points, "file": fname})

        if i < len(pending) - 1:
            time.sleep(30)

    manifest_path = RAW_DIR / "_manifest.json"
    existing = []
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8")).get("topics", [])
    seen = {t["topic"] for t in manifest}
    merged = manifest + [t for t in existing if t["topic"] not in seen]

    manifest_path.write_text(
        json.dumps({"fetched_at": datetime.now(timezone.utc).isoformat(), "topics": merged}, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
