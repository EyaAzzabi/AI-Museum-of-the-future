"""
run_collection.py — AI Museum of the Future
============================================
Master script that runs all data collectors sequentially.
Tunisia 2020-2026 | Light mode (~500-600 items)

Usage:
    # Run all collectors
    python scripts/run_collection.py

    # Run specific collectors only
    python scripts/run_collection.py --only gdelt wikipedia

    # Skip specific collectors
    python scripts/run_collection.py --skip google_trends

    # Dry run (show what would run, without executing)
    python scripts/run_collection.py --dry-run

Output structure:
    data/raw/
    ├── gdelt/
    │   └── gdelt_articles.json          (~200 articles)
    ├── wikipedia/
    │   └── wikipedia_articles.json      (~38 articles)
    ├── google_trends/
    │   └── google_trends.json           (~50 topic entries)
    ├── arxiv/
    │   └── arxiv_papers.json            (~50 papers)
    ├── worldbank/
    │   └── worldbank_indicators.json    (~33 indicators)
    └── wikimedia/
        ├── wikimedia_images_metadata.json (~100 images)
        └── images/                        (downloaded files)
    └── youtube/
        └── youtube_videos.json            (~100 videos)
"""

import argparse
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

# ── Make sure the project root is in the Python path ─────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ── Import all collectors ─────────────────────────────────────────────────────
from scripts.collectors import (  # noqa: E402
    gdelt_collector,
    wikipedia_collector,
    google_trends_collector,
    arxiv_collector,
    worldbank_collector,
    wikimedia_collector,
    youtube_collector,
)

# ── Collector registry ────────────────────────────────────────────────────────
# Order matters: faster/more reliable collectors run first
COLLECTORS = [
    {
        "id":          "worldbank",
        "name":        "World Bank",
        "description": "Socioeconomic indicators for Tunisia 2020-2026",
        "module":      worldbank_collector,
        "requires_key": False,
    },
    {
        "id":          "wikipedia",
        "name":        "Wikipedia",
        "description": "Tunisia-related articles (EN + FR)",
        "module":      wikipedia_collector,
        "requires_key": False,
    },
    {
        "id":          "arxiv",
        "name":        "arXiv",
        "description": "Scientific papers by/about Tunisia 2020-2026",
        "module":      arxiv_collector,
        "requires_key": False,
    },
    {
        "id":          "gdelt",
        "name":        "GDELT",
        "description": "Tunisia news articles 2020-2026 (EN + FR)",
        "module":      gdelt_collector,
        "requires_key": False,
    },
    {
        "id":          "wikimedia",
        "name":        "Wikimedia Commons",
        "description": "Tunisia images with open licenses",
        "module":      wikimedia_collector,
        "requires_key": False,
    },
    {
        "id":          "youtube",
        "name":        "YouTube",
        "description": "Tunisia-related videos metadata 2020-2026 (requires YOUTUBE_API_KEY)",
        "module":      youtube_collector,
        "requires_key": True,
    },
    {
        "id":          "google_trends",
        "name":        "Google Trends",
        "description": "Tunisia search trends 2020-2026 (may hit rate limits)",
        "module":      google_trends_collector,
        "requires_key": False,
    },
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def print_header():
    print("\n" + "=" * 65)
    print("   AI Museum of the Future — Data Collection Pipeline")
    print("   Tunisia 2020-2026 | Light Mode")
    print(f"   Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)


def print_plan(collectors_to_run: list[dict]):
    print("\n📋 Collection plan:")
    for i, c in enumerate(collectors_to_run, 1):
        key_note = " ⚠ (may need rate-limit patience)" if c["id"] == "google_trends" else ""
        print(f"  {i}. [{c['id']}] {c['name']}{key_note}")
        print(f"     → {c['description']}")
    print()


def run_collector(collector: dict) -> dict:
    """
    Runs a single collector and returns a result summary dict.
    """
    name   = collector["name"]
    cid    = collector["id"]
    module = collector["module"]

    result = {
        "id":         cid,
        "name":       name,
        "status":     "pending",
        "started_at": None,
        "ended_at":   None,
        "duration_s": None,
        "error":      None,
    }

    print(f"\n{'─' * 65}")
    print(f"▶ Running: {name} [{cid}]")
    print(f"{'─' * 65}")

    start = time.time()
    result["started_at"] = datetime.now().isoformat()

    try:
        module.run()
        result["status"] = "success"
        print(f"✓ {name} completed successfully.")
    except KeyboardInterrupt:
        result["status"] = "interrupted"
        result["error"]  = "KeyboardInterrupt"
        print(f"\n⚠ {name} was interrupted by user.")
        raise   # re-raise so the main loop can handle clean exit
    except Exception as e:
        result["status"] = "error"
        result["error"]  = str(e)
        print(f"\n✗ {name} failed with error: {e}")
        print("  Traceback:")
        traceback.print_exc()
        print(f"\n  Continuing with next collector...")

    end = time.time()
    result["ended_at"]   = datetime.now().isoformat()
    result["duration_s"] = round(end - start, 1)

    return result


def print_summary(results: list[dict], total_start: float):
    total_time = round(time.time() - total_start, 1)

    print("\n" + "=" * 65)
    print("   COLLECTION SUMMARY")
    print("=" * 65)

    success_count = sum(1 for r in results if r["status"] == "success")
    error_count   = sum(1 for r in results if r["status"] == "error")
    skipped_count = sum(1 for r in results if r["status"] == "skipped")

    for r in results:
        icon = {"success": "✓", "error": "✗", "skipped": "○", "interrupted": "⚠"}.get(r["status"], "?")
        duration = f"{r['duration_s']}s" if r["duration_s"] else "—"
        error_msg = f" → {r['error']}" if r["error"] else ""
        print(f"  {icon} [{r['id']:15s}] {r['status']:12s} ({duration}){error_msg}")

    print(f"\n  Total: {success_count} succeeded | {error_count} failed | {skipped_count} skipped")
    print(f"  Total time: {total_time}s")
    print("\n  Output directory: data/raw/")
    print("=" * 65)

    if error_count > 0:
        print("\n⚠ Some collectors failed. Check errors above.")
        print("  You can re-run failed collectors individually, e.g.:")
        failed_ids = [r["id"] for r in results if r["status"] == "error"]
        print(f"  python scripts/run_collection.py --only {' '.join(failed_ids)}")

    print()


# ── CLI argument parsing ──────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Run all data collectors for AI Museum of the Future (Tunisia 2020-2026)"
    )
    parser.add_argument(
        "--only",
        nargs="+",
        metavar="COLLECTOR_ID",
        help=f"Run only these collectors. Available: {[c['id'] for c in COLLECTORS]}",
    )
    parser.add_argument(
        "--skip",
        nargs="+",
        metavar="COLLECTOR_ID",
        help="Skip these collectors.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would run without executing anything.",
    )
    return parser.parse_args()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()

    # Filter collectors based on --only / --skip
    collectors_to_run = list(COLLECTORS)

    if args.only:
        valid_ids = {c["id"] for c in COLLECTORS}
        for cid in args.only:
            if cid not in valid_ids:
                print(f"[ERROR] Unknown collector id: '{cid}'. Valid: {sorted(valid_ids)}")
                sys.exit(1)
        collectors_to_run = [c for c in COLLECTORS if c["id"] in args.only]

    if args.skip:
        skip_set = set(args.skip)
        collectors_to_run = [c for c in collectors_to_run if c["id"] not in skip_set]

    print_header()
    print_plan(collectors_to_run)

    if args.dry_run:
        print("🔍 Dry run — no collectors were executed.")
        return

    results: list[dict] = []
    total_start = time.time()

    # Mark skipped collectors in results
    skipped_ids = {c["id"] for c in COLLECTORS} - {c["id"] for c in collectors_to_run}
    for cid in skipped_ids:
        name = next(c["name"] for c in COLLECTORS if c["id"] == cid)
        results.append({
            "id": cid, "name": name, "status": "skipped",
            "started_at": None, "ended_at": None,
            "duration_s": None, "error": None,
        })

    try:
        for collector in collectors_to_run:
            result = run_collector(collector)
            results.append(result)
            # Small pause between collectors
            if collector != collectors_to_run[-1]:
                time.sleep(2)
    except KeyboardInterrupt:
        print("\n\n⚠ Collection interrupted by user.")
        # Add remaining collectors as skipped
        completed_ids = {r["id"] for r in results}
        for c in collectors_to_run:
            if c["id"] not in completed_ids:
                results.append({
                    "id": c["id"], "name": c["name"], "status": "skipped",
                    "started_at": None, "ended_at": None,
                    "duration_s": None, "error": "interrupted",
                })

    # Sort results to match original COLLECTORS order
    order = {c["id"]: i for i, c in enumerate(COLLECTORS)}
    results.sort(key=lambda r: order.get(r["id"], 99))

    print_summary(results, total_start)


if __name__ == "__main__":
    main()
