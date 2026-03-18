"""
PodcastIQ — Time-Stratified Re-Extraction Script

Re-extracts episodes from 6 priority channels, targeting top N episodes per year
(2022, 2023, 2024) sorted by view count. Fixes the date clustering problem from
the original extraction (which sorted globally by view count, pulling mostly 2025
episodes).

Channels targeted:
  Priority 1 (must fix — <5 month date spans):
    - All-In Podcast    (+3/+3/+2 per 2022/2023/2024)
    - a16z Podcast      (+2/+3/+3)
    - Joe Rogan (JRE)   (+2/+2/+2)
  Priority 2 (high value — 6-7 month spans):
    - My First Million  (+2/+2/+2)
    - The Diary of a CEO (+2/+2/+2)
    - Huberman Lab      (+2/+2/+2)

Usage:
    python scripts/time_stratified_extraction.py              # All 6 channels
    python scripts/time_stratified_extraction.py --channel "All-In Podcast"
    python scripts/time_stratified_extraction.py --year 2022  # Only 2022 for all
    python scripts/time_stratified_extraction.py --dry-run    # Preview only
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("data/time_stratified_extraction.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

BASE_DIR = Path("data/raw")
PROGRESS_FILE = Path("data/extraction_progress.json")
COOKIES_PATH = Path("scripts/www.youtube.com_cookies.txt")

# YouTube API quota: search.list = 100 units, videos.list = 1 unit/video
API_DELAY_SECONDS = 0.5
TRANSCRIPT_DELAY_SECONDS = 0.3

# 6 priority channels with year-based targets
# Keys: year (int) → target episodes to add from that year
CHANNELS_CONFIG = [
    {
        "name": "All-In Podcast",
        "channel_id": "UCESLZhusAkFfsNsApnjF_Cg",
        "slug": "All-In_Podcast",
        "genre": "Technology & AI",
        "year_targets": {2022: 3, 2023: 3, 2024: 2},
    },
    {
        "name": "a16z Podcast",
        "channel_id": "UC9cn0TuPq4dnbTY-CBsm8XA",
        "slug": "a16z_Podcast",
        "genre": "Technology & AI",
        "year_targets": {2022: 2, 2023: 3, 2024: 3},
    },
    {
        "name": "Joe Rogan Experience",
        "channel_id": "UCzQUP1qoWDoEbmsQxvdjxgQ",
        "slug": "Joe_Rogan_Experience",
        "genre": "General / News & Culture",
        "year_targets": {2022: 2, 2023: 2, 2024: 2},
        "min_duration_min": 60,  # JRE full episodes are 2-3hrs; exclude viral clips
        "max_search_pages": 10,  # Full eps buried in viewCount sort — search deeper
    },
    {
        "name": "My First Million",
        "channel_id": "UCyaN6mg5u8Cjy2ZI4ikWaug",
        "slug": "My_First_Million",
        "genre": "Entrepreneurship",
        "year_targets": {2022: 2, 2023: 2, 2024: 2},
    },
    {
        "name": "The Diary of a CEO",
        "channel_id": "UCGq-a57w-aPwyi3pW7XLiHw",
        "slug": "The_Diary_of_a_CEO",
        "genre": "Business / Entrepreneurship",
        "year_targets": {2022: 2, 2023: 2, 2024: 2},
    },
    {
        "name": "Huberman Lab",
        "channel_id": "UC2D2CMWXMOVWx7giW1n3LIg",
        "slug": "Huberman_Lab",
        "genre": "Health & Science",
        "year_targets": {2022: 2, 2023: 2, 2024: 2},
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_youtube_client():
    """Initialize YouTube Data API v3 client."""
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        raise RuntimeError("YOUTUBE_API_KEY not found in .env")
    return build("youtube", "v3", developerKey=api_key)


def save_json(data: dict | list, filepath: Path) -> None:
    """Write data as JSON to filepath, creating parent dirs as needed."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_progress() -> dict:
    """Load global extraction progress (downloaded video IDs per channel)."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"channels": {}, "last_updated": None}


def save_progress(progress: dict) -> None:
    """Persist extraction progress to disk."""
    progress["last_updated"] = datetime.now().isoformat()
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2)


def parse_duration_to_minutes(duration_iso: str) -> float:
    """Convert ISO 8601 duration (PT1H30M15S) to minutes."""
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration_iso)
    if not match:
        return 0.0
    h = int(match.group(1) or 0)
    m = int(match.group(2) or 0)
    s = int(match.group(3) or 0)
    return h * 60 + m + s / 60


def parse_vtt_to_segments(vtt_content: str) -> list[dict]:
    """Parse WebVTT content into transcript segment dicts."""
    segments = []
    blocks = vtt_content.strip().split("\n\n")
    for block in blocks:
        lines = block.strip().split("\n")
        timestamp_line = None
        text_lines = []
        for line in lines:
            if " --> " in line:
                timestamp_line = line
            elif timestamp_line is not None and line.strip():
                text_lines.append(line.strip())
        if not timestamp_line or not text_lines:
            continue
        parts = timestamp_line.split(" --> ")
        start_str = parts[0].strip()
        end_str = parts[1].strip().split(" ")[0]
        start_sec = _vtt_time_to_seconds(start_str)
        end_sec = _vtt_time_to_seconds(end_str)
        text = " ".join(text_lines)
        text = re.sub(r"<[^>]+>", "", text).strip()
        if text and (not segments or text != segments[-1]["text"]):
            segments.append({
                "text": text,
                "start": round(start_sec, 3),
                "duration": round(end_sec - start_sec, 3),
            })
    return segments


def _vtt_time_to_seconds(time_str: str) -> float:
    """Convert VTT timestamp (HH:MM:SS.mmm or MM:SS.mmm) to seconds."""
    parts = time_str.split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return 0.0


def extract_transcript(video_id: str) -> Optional[list[dict]]:
    """
    Download English transcript for a YouTube video using yt-dlp.

    Args:
        video_id: YouTube video ID.

    Returns:
        List of transcript segment dicts, or None if unavailable.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"

    yt_dlp_executable = "yt-dlp"
    python_exe = Path(sys.executable)
    if python_exe.parent.name in ("Scripts", "bin"):
        candidate = python_exe.parent / ("yt-dlp.exe" if os.name == "nt" else "yt-dlp")
        if candidate.exists():
            yt_dlp_executable = str(candidate)

    with tempfile.TemporaryDirectory() as tmp_dir:
        cmd = [
            yt_dlp_executable,
            "--write-auto-sub",
            "--write-sub",
            "--sub-lang", "en",
            "--skip-download",
            "--ignore-no-formats-error",
            "--impersonate", "chrome",
            "--output", os.path.join(tmp_dir, "%(id)s"),
            "--no-warnings",
        ]
        if COOKIES_PATH.exists():
            cmd.extend(["--cookies", str(COOKIES_PATH)])
        cmd.append(url)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                logger.warning(f"yt-dlp failed for {video_id}: {result.stderr.strip()[:100]}")
                return None
            vtt_files = list(Path(tmp_dir).glob("*.vtt"))
            if not vtt_files:
                logger.warning(f"No subtitle file for {video_id}")
                return None
            vtt_content = vtt_files[0].read_text(encoding="utf-8")
            segments = parse_vtt_to_segments(vtt_content)
            total_words = sum(len(s["text"].split()) for s in segments)
            if total_words < 100:
                logger.warning(f"Transcript too short for {video_id}: {total_words} words")
                return None
            return segments
        except subprocess.TimeoutExpired:
            logger.warning(f"yt-dlp timed out for {video_id}")
            return None
        except Exception as e:
            logger.warning(f"Transcript error for {video_id}: {e}")
            return None


# ---------------------------------------------------------------------------
# Year-range video fetching via search.list
# ---------------------------------------------------------------------------

def fetch_videos_for_year(
    youtube,
    channel_id: str,
    year: int,
    candidates_needed: int = 6,
    min_duration_min: float = 30.0,
    max_duration_min: float = 240.0,
    max_search_pages: int = 3,
) -> list[dict]:
    """
    Fetch top-N videos from a channel published within a specific calendar year,
    sorted by view count.

    Uses search.list (100 quota units each call) with publishedAfter/Before.

    Args:
        youtube: YouTube API client.
        channel_id: YouTube channel ID.
        year: Calendar year to fetch videos from.
        candidates_needed: How many passing candidates to return.
        min_duration_min: Minimum episode duration in minutes.
        max_duration_min: Maximum episode duration in minutes.

    Returns:
        List of video metadata dicts sorted by view count descending.
    """
    published_after = f"{year}-01-01T00:00:00Z"
    published_before = f"{year}-12-31T23:59:59Z"

    logger.info(f"  Searching {channel_id} for year {year} (top by views)...")

    # search.list costs 100 units but supports date range + viewCount order
    search_results = []
    next_page_token = None

    # Fetch up to max_search_pages (default 3 = 150 results) to find duration-passing videos
    max_pages = max_search_pages
    pages_fetched = 0

    while pages_fetched < max_pages:
        try:
            req = youtube.search().list(
                part="id",
                channelId=channel_id,
                type="video",
                order="viewCount",
                publishedAfter=published_after,
                publishedBefore=published_before,
                maxResults=50,
                pageToken=next_page_token,
            )
            response = req.execute()
            time.sleep(API_DELAY_SECONDS)
        except HttpError as e:
            if e.resp.status == 403 and "quotaExceeded" in str(e):
                raise RuntimeError("YouTube API quota exceeded — re-run tomorrow")
            logger.error(f"  search.list error for {channel_id} year {year}: {e}")
            break
        except Exception as e:
            logger.error(f"  search.list error: {e}")
            break

        video_ids = [item["id"]["videoId"] for item in response.get("items", [])]

        if not video_ids:
            break

        # Fetch full details (duration, stats) in one batch
        try:
            details = youtube.videos().list(
                part="snippet,contentDetails,statistics",
                id=",".join(video_ids),
            ).execute()
            time.sleep(API_DELAY_SECONDS)
        except Exception as e:
            logger.error(f"  videos.list error: {e}")
            break

        for item in details.get("items", []):
            dur_min = parse_duration_to_minutes(item["contentDetails"]["duration"])
            if not (min_duration_min <= dur_min <= max_duration_min):
                continue
            snippet = item["snippet"]
            # Verify publish date falls within the target year (search can be imprecise)
            pub_year = int(snippet["publishedAt"][:4])
            if pub_year != year:
                continue
            stats = item.get("statistics", {})
            search_results.append({
                "video_id": item["id"],
                "title": snippet["title"],
                "description": snippet.get("description", ""),
                "channel_id": snippet["channelId"],
                "channel_name": snippet["channelTitle"],
                "publish_date": snippet["publishedAt"],
                "duration_iso": item["contentDetails"]["duration"],
                "duration_minutes": round(dur_min, 1),
                "view_count": int(stats.get("viewCount", 0)),
                "like_count": int(stats.get("likeCount", 0)),
                "video_url": f"https://www.youtube.com/watch?v={item['id']}",
            })

        pages_fetched += 1
        next_page_token = response.get("nextPageToken")

        # Stop early if we already have enough candidates
        if len(search_results) >= candidates_needed * 2:
            break
        if not next_page_token:
            break

    # Sort by view count descending, return top candidates
    search_results.sort(key=lambda v: v["view_count"], reverse=True)
    logger.info(f"  Found {len(search_results)} duration-valid candidates for {year}")
    return search_results[:candidates_needed * 2]  # Return generous pool


# ---------------------------------------------------------------------------
# Per-channel extraction
# ---------------------------------------------------------------------------

def extract_channel_year(
    youtube,
    channel_config: dict,
    year: int,
    target: int,
    already_downloaded: set[str],
    dry_run: bool = False,
) -> list[dict]:
    """
    Extract up to `target` new episodes from a channel for a given year.

    Args:
        youtube: YouTube API client.
        channel_config: Channel config dict (name, channel_id, slug, genre).
        year: Target year.
        target: Number of new episodes to download.
        already_downloaded: Set of video IDs already on disk.
        dry_run: If True, preview without downloading.

    Returns:
        List of result dicts for each episode attempted.
    """
    channel_name = channel_config["name"]
    channel_slug = channel_config["slug"]
    channel_dir = BASE_DIR / channel_slug

    min_dur = channel_config.get("min_duration_min", 30.0)
    max_pages = channel_config.get("max_search_pages", 3)
    logger.info(f"  Year {year}: target={target} new episodes (min duration: {min_dur} min)")

    candidates = fetch_videos_for_year(
        youtube,
        channel_config["channel_id"],
        year,
        candidates_needed=target + 3,
        min_duration_min=min_dur,
        max_search_pages=max_pages,
    )

    if not candidates:
        logger.warning(f"  No candidates found for {channel_name} year {year}")
        return []

    if dry_run:
        new_candidates = [v for v in candidates if v["video_id"] not in already_downloaded]
        for v in new_candidates[:target]:
            logger.info(
                f"    [DRY RUN] {v['title'][:70]} "
                f"({v['duration_minutes']}min, {v['view_count']:,} views, {v['publish_date'][:10]})"
            )
        return []

    results = []
    succeeded = 0

    for video in candidates:
        if succeeded >= target:
            break

        vid = video["video_id"]

        if vid in already_downloaded:
            logger.info(f"    Skipping {vid} (already downloaded)")
            continue

        logger.info(
            f"    [{succeeded + 1}/{target}] {video['title'][:65]}... "
            f"({video['publish_date'][:10]}, {video['view_count']:,} views)"
        )

        transcript = extract_transcript(vid)
        time.sleep(TRANSCRIPT_DELAY_SECONDS)

        if not transcript:
            results.append({"video_id": vid, "title": video["title"], "year": year, "status": "no_transcript"})
            continue

        # Save to same directory structure as original extraction
        save_json(video, channel_dir / f"{vid}_metadata.json")
        save_json(transcript, channel_dir / f"{vid}_transcript.json")

        total_words = sum(len(s["text"].split()) for s in transcript)
        total_duration = sum(s["duration"] for s in transcript)

        succeeded += 1
        already_downloaded.add(vid)

        results.append({
            "video_id": vid,
            "title": video["title"],
            "year": year,
            "publish_date": video["publish_date"][:10],
            "status": "success",
            "transcript_segments": len(transcript),
            "word_count": total_words,
            "duration_seconds": round(total_duration, 1),
        })

        logger.info(f"    Saved: {len(transcript)} segments, {total_words} words")

    logger.info(f"  Year {year}: {succeeded}/{target} extracted")
    return results


def extract_channel(
    youtube,
    channel_config: dict,
    progress: dict,
    years_filter: Optional[list[int]] = None,
    dry_run: bool = False,
) -> dict:
    """
    Run time-stratified extraction for a single channel.

    Args:
        youtube: YouTube API client.
        channel_config: Channel config entry from CHANNELS_CONFIG.
        progress: Global extraction progress dict (will be mutated + saved).
        years_filter: If provided, only process these years.
        dry_run: Preview mode.

    Returns:
        Channel summary dict.
    """
    channel_name = channel_config["name"]
    year_targets = channel_config["year_targets"]

    logger.info(f"\n{'='*60}")
    logger.info(f"Channel: {channel_name}")

    # Load already-downloaded IDs from progress + scan existing directory
    downloaded_ids: set[str] = set(
        progress.get("channels", {}).get(channel_name, {}).get("downloaded_ids", [])
    )
    # Also scan disk in case progress is out of sync
    channel_dir = BASE_DIR / channel_config["slug"]
    if channel_dir.exists():
        for meta_file in channel_dir.glob("*_metadata.json"):
            vid = meta_file.stem.replace("_metadata", "")
            downloaded_ids.add(vid)

    logger.info(f"Already downloaded: {len(downloaded_ids)} episodes")

    summary = {
        "channel": channel_name,
        "channel_id": channel_config["channel_id"],
        "total_added": 0,
        "by_year": {},
    }

    years_to_process = years_filter if years_filter else sorted(year_targets.keys())

    for year in years_to_process:
        target = year_targets.get(year, 0)
        if target == 0:
            continue

        year_results = extract_channel_year(
            youtube,
            channel_config,
            year,
            target,
            downloaded_ids,
            dry_run=dry_run,
        )

        succeeded = [r for r in year_results if r["status"] == "success"]
        summary["by_year"][year] = {
            "target": target,
            "added": len(succeeded),
            "episodes": year_results,
        }
        summary["total_added"] += len(succeeded)

        # Persist progress after each year
        if not dry_run:
            progress.setdefault("channels", {}).setdefault(channel_name, {})
            progress["channels"][channel_name]["downloaded_ids"] = list(downloaded_ids)
            progress["channels"][channel_name]["last_stratified_extraction"] = datetime.now().isoformat()
            save_progress(progress)

    year_parts = [str(y) + ":" + str(v["added"]) for y, v in summary["by_year"].items()]
    logger.info(
        f"Channel total: {summary['total_added']} new episodes added "
        f"({', '.join(year_parts)})"
    )
    return summary


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="PodcastIQ time-stratified re-extraction for 6 priority channels"
    )
    parser.add_argument(
        "--channel",
        type=str,
        help="Extract a single channel by name (e.g. 'All-In Podcast')",
    )
    parser.add_argument(
        "--year",
        type=int,
        choices=[2022, 2023, 2024],
        help="Only extract from this specific year",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview candidates without downloading",
    )
    args = parser.parse_args()

    Path("data").mkdir(parents=True, exist_ok=True)

    youtube = get_youtube_client()
    progress = load_progress()

    channels = CHANNELS_CONFIG
    if args.channel:
        channels = [c for c in channels if c["name"].lower() == args.channel.lower()]
        if not channels:
            logger.error(f"Channel '{args.channel}' not found. Valid options:")
            for c in CHANNELS_CONFIG:
                logger.error(f"  - {c['name']}")
            return

    years_filter = [args.year] if args.year else None

    mode = "DRY RUN" if args.dry_run else "EXTRACTION"
    logger.info(f"PodcastIQ Time-Stratified Re-Extraction — {mode}")
    logger.info(f"Channels: {len(channels)} | Years: {years_filter or [2022, 2023, 2024]}")

    all_summaries = []
    total_added = 0

    for channel_config in channels:
        try:
            summary = extract_channel(
                youtube,
                channel_config,
                progress,
                years_filter=years_filter,
                dry_run=args.dry_run,
            )
            all_summaries.append(summary)
            total_added += summary["total_added"]
        except RuntimeError as e:
            logger.error(f"\nFATAL: {e}")
            logger.error("Progress saved. Re-run tomorrow to resume.")
            break
        except Exception as e:
            logger.error(f"Error processing {channel_config['name']}: {e}", exc_info=True)
            all_summaries.append({"channel": channel_config["name"], "error": str(e)})

    # Save overall report
    report_path = BASE_DIR / "_time_stratified_summary.json"
    save_json(all_summaries, report_path)

    logger.info(f"\n{'='*60}")
    logger.info(f"COMPLETE — {total_added} new episodes added across {len(all_summaries)} channels")
    for s in all_summaries:
        if "error" in s:
            logger.info(f"  [ERR] {s['channel']}: {s['error']}")
        else:
            parts = [f"{y}: +{v['added']}/{v['target']}" for y, v in s.get("by_year", {}).items()]
            by_year_str = " | ".join(parts)
            logger.info(f"  [OK]  {s['channel']}: {by_year_str} = +{s['total_added']} total")
    logger.info(f"\nReport saved to: {report_path}")
    logger.info(
        "Next steps: run snowflake_loader.py, then re-run CUR_CHUNKS and embeddings "
        "for the new episodes."
    )


if __name__ == "__main__":
    main()
