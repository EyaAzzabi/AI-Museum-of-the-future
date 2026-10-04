"""
YouTube Collector — AI Museum of the Future
============================================
Source      : YouTube Data API v3
Coverage    : Tunisia-related videos, 2020–2026
Languages   : French + English (+ Arabic titles accepted)
Output      : data/raw/youtube/youtube_videos.json
Volume      : ~100 videos (light mode)

Requires: YOUTUBE_API_KEY in .env
API docs: https://developers.google.com/youtube/v3/docs/search/list
Quota cost: ~100 units per run (well within 10,000/day free quota)
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# ── Project root on path ──────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.config import YOUTUBE_API_KEY  # noqa: E402

# ── Output directory ──────────────────────────────────────────────────────────
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "youtube"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── YouTube API ───────────────────────────────────────────────────────────────
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEO_URL  = "https://www.googleapis.com/youtube/v3/videos"

# Period filter (ISO 8601 format required by YouTube API)
PUBLISHED_AFTER  = "2020-01-01T00:00:00Z"
PUBLISHED_BEFORE = "2026-12-31T23:59:59Z"

# ── Search queries by theme ───────────────────────────────────────────────────
QUERIES = [
    # Politics & Society
    {"query": "Tunisie politique 2020 2021 2022 2023",   "theme": "politics_society", "max": 10},
    {"query": "Tunisia Kais Saied constitution",          "theme": "politics_society", "max": 8},
    {"query": "Tunisie société droits femmes",            "theme": "politics_society", "max": 8},

    # Economy
    {"query": "Tunisie économie crise chômage",           "theme": "economy",          "max": 8},
    {"query": "Tunisia economy inflation IMF",            "theme": "economy",          "max": 8},

    # Culture & Arts
    {"query": "Tunisie culture musique cinéma",           "theme": "culture_arts",     "max": 10},
    {"query": "festival Carthage Tunis art",              "theme": "culture_arts",     "max": 8},
    {"query": "Tunisia documentary culture heritage",     "theme": "culture_arts",     "max": 8},

    # Science & Technology
    {"query": "Tunisie technologie startup innovation",   "theme": "science_tech",     "max": 8},
    {"query": "Tunisia artificial intelligence research", "theme": "science_tech",     "max": 8},

    # Environment
    {"query": "Tunisie environnement eau sécheresse",     "theme": "environment",      "max": 8},
    {"query": "Tunisia climate change desert drought",    "theme": "environment",      "max": 8},
]


def search_videos(query: str, max_results: int = 10) -> list[str]:
    """
    Searches YouTube and returns a list of video IDs.
    One search request = 100 quota units.
    """
    if not YOUTUBE_API_KEY:
        raise ValueError("YOUTUBE_API_KEY is not set in .env")

    params = {
        "part":            "id",
        "q":               query,
        "type":            "video",
        "maxResults":      min(max_results, 50),   # API max is 50
        "publishedAfter":  PUBLISHED_AFTER,
        "publishedBefore": PUBLISHED_BEFORE,
        "relevanceLanguage": "fr",                 # prefer French results
        "key":             YOUTUBE_API_KEY,
    }

    try:
        response = requests.get(YOUTUBE_SEARCH_URL, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"  [ERROR] Search request failed: {e}")
        return []

    return [item["id"]["videoId"] for item in data.get("items", []) if "videoId" in item.get("id", {})]


def fetch_video_details(video_ids: list[str]) -> list[dict]:
    """
    Fetches detailed metadata for a list of video IDs.
    One videos.list request = 1 quota unit per video.
    """
    if not video_ids:
        return []

    params = {
        "part":  "snippet,statistics,contentDetails",
        "id":    ",".join(video_ids),
        "key":   YOUTUBE_API_KEY,
    }

    try:
        response = requests.get(YOUTUBE_VIDEO_URL, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"  [ERROR] Video details request failed: {e}")
        return []

    results = []
    for item in data.get("items", []):
        snippet    = item.get("snippet", {})
        stats      = item.get("statistics", {})
        content    = item.get("contentDetails", {})
        video_id   = item.get("id", "")

        published_at = snippet.get("publishedAt", "")

        results.append({
            "source":        "youtube",
            "collected_at":  datetime.utcnow().isoformat(),
            "video_id":      video_id,
            "url":           f"https://www.youtube.com/watch?v={video_id}",
            "title":         snippet.get("title", ""),
            "description":   snippet.get("description", "")[:500],  # truncate long descriptions
            "channel_title": snippet.get("channelTitle", ""),
            "channel_id":    snippet.get("channelId", ""),
            "published_at":  published_at,
            "published_year": published_at[:4] if published_at else "",
            "tags":          snippet.get("tags", [])[:10],           # max 10 tags
            "category_id":   snippet.get("categoryId", ""),
            "language":      snippet.get("defaultLanguage", snippet.get("defaultAudioLanguage", "")),
            "duration":      content.get("duration", ""),            # ISO 8601 duration (e.g. PT5M30S)
            "view_count":    int(stats.get("viewCount", 0) or 0),
            "like_count":    int(stats.get("likeCount", 0) or 0),
            "comment_count": int(stats.get("commentCount", 0) or 0),
            "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
        })

    return results


def run():
    """Main collection loop — searches videos and fetches metadata."""
    print("=" * 60)
    print("YouTube Collector — Tunisia 2020-2026")
    print("=" * 60)

    if not YOUTUBE_API_KEY:
        print("[ERROR] YOUTUBE_API_KEY not found in .env")
        print("  → Add YOUTUBE_API_KEY=your_key to your .env file")
        return

    all_videos: list[dict] = []
    seen_ids: set[str] = set()

    for i, q in enumerate(QUERIES, start=1):
        query  = q["query"]
        theme  = q["theme"]
        max_r  = q["max"]

        print(f"\n[{i}/{len(QUERIES)}] Theme: {theme}")
        print(f"  Query: '{query}' (max {max_r})")

        # Step 1 — search for video IDs
        video_ids = search_videos(query, max_r)
        if not video_ids:
            print(f"  [WARN] No video IDs returned.")
            time.sleep(1)
            continue

        # Deduplicate IDs before fetching details
        new_ids = [vid for vid in video_ids if vid not in seen_ids]
        for vid in new_ids:
            seen_ids.add(vid)

        if not new_ids:
            print(f"  All {len(video_ids)} results already seen (duplicates).")
            continue

        # Step 2 — fetch detailed metadata
        videos = fetch_video_details(new_ids)

        # Attach theme to each video
        for v in videos:
            v["theme"] = theme

        all_videos.extend(videos)
        print(f"  Found: {len(video_ids)} | New: {len(new_ids)} | With details: {len(videos)} | Total: {len(all_videos)}")

        # Show top video
        if videos:
            top = videos[0]
            print(f"  Top: '{top['title'][:60]}' ({top['view_count']:,} views)")

        # Polite delay — YouTube API is sensitive to burst requests
        if i < len(QUERIES):
            time.sleep(1.5)

    # ── Save results ──────────────────────────────────────────────────────────
    output_file = OUTPUT_DIR / "youtube_videos.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_videos, f, ensure_ascii=False, indent=2)

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"✓ Done. {len(all_videos)} videos saved.")
    print(f"✓ Output: {output_file}")

    # Theme breakdown
    from collections import Counter
    themes = Counter(v["theme"] for v in all_videos)
    print("\n  Breakdown by theme:")
    for theme, count in sorted(themes.items()):
        print(f"    {theme:25s} : {count} videos")

    print("=" * 60)


if __name__ == "__main__":
    run()
