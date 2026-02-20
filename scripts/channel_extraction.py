"""
PodcastIQ — Batch Channel Extraction Script

Extracts transcripts and metadata for all channels defined in channels.json.
Supports resuming interrupted runs, rate limiting, and per-channel progress tracking.

Usage:
    python scripts/channel_extraction.py                  # Extract all channels
    python scripts/channel_extraction.py --channel "Lex Fridman Podcast"  # Single channel
    python scripts/channel_extraction.py --dry-run        # Preview without downloading
    python scripts/channel_extraction.py --validate-only  # Check transcript availability
"""

import argparse
import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi


class QuotaExhaustedError(Exception):
    """Raised when YouTube API daily quota is exceeded."""
    pass

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("data/extraction.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

BASE_DIR = Path("data/raw")
CHANNELS_CONFIG = Path("scripts/channels.json")
PROGRESS_FILE = Path("data/extraction_progress.json")

# Rate limiting: YouTube API quota is 10,000 units/day
# search.list = 100 units, videos.list = 1 unit, playlistItems.list = 1 unit
API_DELAY_SECONDS = 0.5
TRANSCRIPT_DELAY_SECONDS = 0.3


def load_channels_config() -> dict:
    """Load channel configuration from channels.json."""
    with open(CHANNELS_CONFIG, "r", encoding="utf-8") as f:
        return json.load(f)


def load_progress() -> dict:
    """Load extraction progress from disk (for resume capability)."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"channels": {}, "last_updated": None}


def save_progress(progress: dict) -> None:
    """Persist extraction progress to disk."""
    progress["last_updated"] = datetime.now().isoformat()
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2)


def save_json(data: dict | list, filepath: Path) -> None:
    """Write data to a JSON file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_youtube_client():
    """Initialize YouTube Data API client."""
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        raise RuntimeError("YOUTUBE_API_KEY not found in .env — required for batch extraction")
    return build("youtube", "v3", developerKey=api_key)


def parse_duration_to_minutes(duration_iso: str) -> float:
    """
    Convert ISO 8601 duration (PT1H30M15S) to minutes.

    Args:
        duration_iso: Duration string in ISO 8601 format.

    Returns:
        Duration in minutes as a float.
    """
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration_iso)
    if not match:
        return 0.0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 60 + minutes + seconds / 60


def get_uploads_playlist_id(channel_id: str) -> str:
    """
    Derive the uploads playlist ID from a channel ID.
    YouTube convention: replace leading 'UC' with 'UU'.

    Args:
        channel_id: YouTube channel ID (starts with UC).

    Returns:
        Uploads playlist ID (starts with UU).
    """
    if channel_id.startswith("UC"):
        return "UU" + channel_id[2:]
    return channel_id


def fetch_channel_videos(
    youtube,
    channel_id: str,
    max_results: int = 50,
    min_duration_min: float = 10,
    max_duration_min: float = 240,
    date_after: str = "2022-01-01",
) -> list[dict]:
    """
    Fetch video IDs and metadata from a channel's uploads playlist.

    Args:
        youtube: Authenticated YouTube API client.
        channel_id: YouTube channel ID.
        max_results: Maximum number of videos to fetch.
        min_duration_min: Minimum video duration in minutes.
        max_duration_min: Maximum video duration in minutes.
        date_after: Only include videos published after this date (YYYY-MM-DD).

    Returns:
        List of video metadata dicts, sorted by view count descending.
    """
    playlist_id = get_uploads_playlist_id(channel_id)
    videos = []
    next_page_token = None
    date_cutoff = datetime.strptime(date_after, "%Y-%m-%d")

    logger.info(f"Fetching videos from playlist {playlist_id}")

    while len(videos) < max_results * 3:  # Fetch extra to account for filtering
        try:
            request = youtube.playlistItems().list(
                part="snippet",
                playlistId=playlist_id,
                maxResults=50,
                pageToken=next_page_token,
            )
            response = request.execute()
            time.sleep(API_DELAY_SECONDS)
        except HttpError as e:
            if e.resp.status == 403 and "quotaExceeded" in str(e):
                raise QuotaExhaustedError("YouTube API daily quota exceeded — re-run tomorrow to resume")
            logger.error(f"Error fetching playlist {playlist_id}: {e}")
            break
        except Exception as e:
            logger.error(f"Error fetching playlist {playlist_id}: {e}")
            break

        video_ids = []
        for item in response.get("items", []):
            snippet = item["snippet"]
            published = datetime.strptime(snippet["publishedAt"][:10], "%Y-%m-%d")
            if published >= date_cutoff:
                video_ids.append(snippet["resourceId"]["videoId"])

        # Fetch full video details (duration, stats) in batches of 50
        if video_ids:
            try:
                details_response = youtube.videos().list(
                    part="snippet,contentDetails,statistics",
                    id=",".join(video_ids),
                ).execute()
                time.sleep(API_DELAY_SECONDS)
            except HttpError as e:
                if e.resp.status == 403 and "quotaExceeded" in str(e):
                    raise QuotaExhaustedError("YouTube API daily quota exceeded — re-run tomorrow to resume")
                logger.error(f"Error fetching video details: {e}")
                break
            except Exception as e:
                logger.error(f"Error fetching video details: {e}")
                break

            for item in details_response.get("items", []):
                duration_min = parse_duration_to_minutes(item["contentDetails"]["duration"])
                if min_duration_min <= duration_min <= max_duration_min:
                    snippet = item["snippet"]
                    stats = item.get("statistics", {})
                    videos.append({
                        "video_id": item["id"],
                        "title": snippet["title"],
                        "description": snippet.get("description", ""),
                        "channel_id": snippet["channelId"],
                        "channel_name": snippet["channelTitle"],
                        "publish_date": snippet["publishedAt"],
                        "duration_iso": item["contentDetails"]["duration"],
                        "duration_minutes": round(duration_min, 1),
                        "view_count": int(stats.get("viewCount", 0)),
                        "like_count": int(stats.get("likeCount", 0)),
                        "video_url": f"https://www.youtube.com/watch?v={item['id']}",
                    })

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    # Sort by view count (most popular first) and take top N
    videos.sort(key=lambda v: v["view_count"], reverse=True)
    return videos[:max_results]


def extract_transcript(
    transcript_api: YouTubeTranscriptApi, video_id: str
) -> Optional[list[dict]]:
    """
    Fetch English transcript for a YouTube video.

    Args:
        transcript_api: YouTubeTranscriptApi instance.
        video_id: YouTube video ID.

    Returns:
        List of transcript segment dicts, or None if unavailable.
    """
    try:
        transcript = transcript_api.fetch(video_id, languages=["en"])
        segments = [
            {"text": s.text, "start": s.start, "duration": s.duration}
            for s in transcript
        ]
        # Quality check: reject very short transcripts
        total_words = sum(len(s["text"].split()) for s in segments)
        if total_words < 100:
            logger.warning(f"Transcript too short for {video_id}: {total_words} words")
            return None
        return segments
    except Exception as e:
        logger.warning(f"No transcript for {video_id}: {e}")
        return None


def extract_channel(
    youtube,
    transcript_api: YouTubeTranscriptApi,
    channel_config: dict,
    config_metadata: dict,
    progress: dict,
    dry_run: bool = False,
    validate_only: bool = False,
) -> dict:
    """
    Extract transcripts and metadata for a single channel.

    Args:
        youtube: YouTube API client.
        transcript_api: YouTubeTranscriptApi instance.
        channel_config: Channel entry from channels.json.
        config_metadata: Global config metadata (date range, duration limits).
        progress: Progress tracking dict.
        dry_run: If True, only list videos without downloading.
        validate_only: If True, only check transcript availability.

    Returns:
        Channel extraction summary dict.
    """
    channel_name = channel_config["name"]
    channel_id = channel_config["channel_id"]
    target_eps = channel_config["target_episodes"]
    channel_slug = re.sub(r"[^\w\-]", "_", channel_name).strip("_")
    channel_dir = BASE_DIR / channel_slug

    # Check what's already downloaded (resume support)
    channel_progress = progress.get("channels", {}).get(channel_name, {})
    downloaded_ids = set(channel_progress.get("downloaded_ids", []))

    logger.info(f"\n{'='*60}")
    logger.info(f"Channel: {channel_name} ({channel_config['handle']})")
    logger.info(f"Target: {target_eps} episodes | Already downloaded: {len(downloaded_ids)}")

    remaining = target_eps - len(downloaded_ids)
    if remaining <= 0:
        logger.info(f"Already complete — skipping")
        return {"channel": channel_name, "status": "already_complete", "downloaded": len(downloaded_ids)}

    # Fetch candidate videos
    date_range = config_metadata.get("date_range", "2022-01-01 to 2026-12-31")
    date_after = date_range.split(" to ")[0]
    min_dur = config_metadata.get("min_duration_minutes", 10)
    max_dur = config_metadata.get("max_duration_minutes", 240)

    candidates = fetch_channel_videos(
        youtube, channel_id,
        max_results=target_eps * 2,  # Fetch extra in case some lack transcripts
        min_duration_min=min_dur,
        max_duration_min=max_dur,
        date_after=date_after,
    )

    logger.info(f"Found {len(candidates)} candidate videos (after duration/date filter)")

    if dry_run:
        for v in candidates[:target_eps]:
            logger.info(f"  [DRY RUN] {v['title']} ({v['duration_minutes']} min, {v['view_count']:,} views)")
        return {"channel": channel_name, "status": "dry_run", "candidates": len(candidates)}

    # Extract transcripts
    summary = {
        "channel": channel_name,
        "channel_id": channel_id,
        "genre": channel_config["genre"],
        "attempted": 0,
        "succeeded": 0,
        "failed": 0,
        "skipped_already_downloaded": 0,
        "episodes": [],
    }

    for video in candidates:
        if summary["succeeded"] >= target_eps:
            break

        vid = video["video_id"]

        if vid in downloaded_ids:
            summary["skipped_already_downloaded"] += 1
            continue

        summary["attempted"] += 1
        logger.info(f"  [{summary['succeeded']+1}/{target_eps}] {video['title'][:60]}...")

        if validate_only:
            transcript = extract_transcript(transcript_api, vid)
            status = "available" if transcript else "unavailable"
            logger.info(f"    Transcript: {status}")
            if transcript:
                summary["succeeded"] += 1
            else:
                summary["failed"] += 1
            time.sleep(TRANSCRIPT_DELAY_SECONDS)
            continue

        # Extract transcript
        transcript = extract_transcript(transcript_api, vid)
        time.sleep(TRANSCRIPT_DELAY_SECONDS)

        if not transcript:
            summary["failed"] += 1
            summary["episodes"].append({
                "video_id": vid, "title": video["title"], "status": "no_transcript"
            })
            continue

        # Save metadata and transcript
        save_json(video, channel_dir / f"{vid}_metadata.json")
        save_json(transcript, channel_dir / f"{vid}_transcript.json")

        total_words = sum(len(s["text"].split()) for s in transcript)
        total_duration = sum(s["duration"] for s in transcript)

        summary["succeeded"] += 1
        summary["episodes"].append({
            "video_id": vid,
            "title": video["title"],
            "status": "success",
            "transcript_segments": len(transcript),
            "word_count": total_words,
            "duration_seconds": round(total_duration, 1),
        })

        # Update progress after each successful download
        downloaded_ids.add(vid)
        if channel_name not in progress.get("channels", {}):
            progress.setdefault("channels", {})[channel_name] = {}
        progress["channels"][channel_name]["downloaded_ids"] = list(downloaded_ids)
        progress["channels"][channel_name]["last_downloaded"] = datetime.now().isoformat()
        save_progress(progress)

        logger.info(f"    Saved: {len(transcript)} segments, {total_words} words")

    # Save channel summary
    save_json(summary, channel_dir / "_channel_summary.json")

    logger.info(f"  Result: {summary['succeeded']}/{target_eps} episodes extracted "
                f"({summary['failed']} failed, {summary['skipped_already_downloaded']} skipped)")

    return summary


def print_final_report(results: list[dict]) -> None:
    """Print a formatted extraction report."""
    logger.info(f"\n{'='*60}")
    logger.info("EXTRACTION REPORT")
    logger.info(f"{'='*60}")

    total_succeeded = 0
    total_failed = 0
    total_attempted = 0

    for r in results:
        succeeded = r.get("succeeded", 0)
        failed = r.get("failed", 0)
        attempted = r.get("attempted", 0)
        total_succeeded += succeeded
        total_failed += failed
        total_attempted += attempted

        status_icon = "OK" if r.get("status") != "error" else "ERR"
        logger.info(f"  [{status_icon}] {r['channel']}: {succeeded} episodes")

    logger.info(f"\nTotal: {total_succeeded} episodes extracted "
                f"({total_failed} failed out of {total_attempted} attempted)")


def main() -> None:
    parser = argparse.ArgumentParser(description="PodcastIQ batch channel extraction")
    parser.add_argument("--channel", type=str, help="Extract a single channel by name")
    parser.add_argument("--dry-run", action="store_true", help="Preview without downloading")
    parser.add_argument("--validate-only", action="store_true", help="Check transcript availability only")
    args = parser.parse_args()

    # Ensure data directory exists for log file
    Path("data").mkdir(parents=True, exist_ok=True)

    config = load_channels_config()
    progress = load_progress()
    youtube = get_youtube_client()
    transcript_api = YouTubeTranscriptApi()

    channels = config["channels"]
    if args.channel:
        channels = [c for c in channels if c["name"].lower() == args.channel.lower()]
        if not channels:
            logger.error(f"Channel '{args.channel}' not found in channels.json")
            return

    logger.info(f"PodcastIQ Extraction — {len(channels)} channels queued")
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'VALIDATE' if args.validate_only else 'FULL EXTRACTION'}")

    results = []
    for channel_config in channels:
        try:
            result = extract_channel(
                youtube, transcript_api, channel_config,
                config["metadata"], progress,
                dry_run=args.dry_run,
                validate_only=args.validate_only,
            )
            results.append(result)
        except QuotaExhaustedError as e:
            logger.error(f"\n{'!'*60}")
            logger.error(f"QUOTA EXHAUSTED: {e}")
            logger.error(f"Progress saved — re-run this script tomorrow to resume.")
            logger.error(f"{'!'*60}")
            results.append({"channel": channel_config["name"], "status": "quota_exhausted"})
            break  # Stop processing all remaining channels
        except Exception as e:
            logger.error(f"Error processing {channel_config['name']}: {e}")
            results.append({"channel": channel_config["name"], "status": "error", "error": str(e)})

    # Save overall summary
    save_json(results, BASE_DIR / "_extraction_summary.json")
    print_final_report(results)


if __name__ == "__main__":
    main()
