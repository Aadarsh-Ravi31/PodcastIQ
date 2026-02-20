import os
import json
import logging
from pathlib import Path
from youtube_transcript_api import YouTubeTranscriptApi
from dotenv import load_dotenv
from googleapiclient.discovery import build

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("data/poc")


def get_youtube_client():
    """Initialize YouTube Data API client."""
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        logger.warning("YOUTUBE_API_KEY not found in .env — metadata will be limited")
        return None
    return build("youtube", "v3", developerKey=api_key)


def get_video_metadata(youtube, video_id: str) -> dict:
    """
    Fetch metadata for a given video ID via YouTube Data API.

    Args:
        youtube: Authenticated YouTube API client (or None).
        video_id: YouTube video ID.

    Returns:
        Dictionary with video metadata.
    """
    if not youtube:
        return {"video_id": video_id, "title": "Unknown (No API Key)", "channel_name": "Unknown"}

    try:
        response = youtube.videos().list(
            part="snippet,contentDetails,statistics",
            id=video_id,
        ).execute()

        if not response["items"]:
            logger.warning(f"No metadata found for {video_id}")
            return None

        item = response["items"][0]
        snippet = item["snippet"]
        stats = item["statistics"]

        return {
            "video_id": video_id,
            "title": snippet["title"],
            "description": snippet["description"],
            "channel_id": snippet["channelId"],
            "channel_name": snippet["channelTitle"],
            "publish_date": snippet["publishedAt"],
            "view_count": int(stats.get("viewCount", 0)),
            "like_count": int(stats.get("likeCount", 0)),
            "duration": item["contentDetails"]["duration"],
            "video_url": f"https://www.youtube.com/watch?v={video_id}",
        }
    except Exception as e:
        logger.error(f"Error fetching metadata for {video_id}: {e}")
        return None


def extract_transcript(api: YouTubeTranscriptApi, video_id: str) -> list[dict] | None:
    """
    Fetch transcript for a YouTube video.

    Args:
        api: YouTubeTranscriptApi instance.
        video_id: YouTube video ID.

    Returns:
        List of transcript segment dicts with text, start, and duration keys,
        or None if unavailable.
    """
    try:
        transcript = api.fetch(video_id, languages=["en"])
        return [{"text": s.text, "start": s.start, "duration": s.duration} for s in transcript]
    except Exception as e:
        logger.error(f"Failed to get transcript for {video_id}: {e}")
        return None


def save_json(data: dict | list, filepath: Path) -> None:
    """Write data to a JSON file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved {filepath}")


def main() -> None:
    # POC Video IDs (verified: metadata + transcripts available)
    poc_videos = [
        "YFjfBk8HI5o",  # Lex Fridman - OpenClaw: Peter Steinberger
        "tNZnLkRBYA8",  # Lex Fridman #461 - ThePrimeagen
        "wTiHheA40nI",  # All-In Podcast - Epstein Files, SaaS Dead?
        "bhpd4NeTbCI",  # All-In Podcast - Somali Fraud, California Asset Seizure
        "FknTw9bJsXM",  # ThePrimeagen / Boot.dev - From TCP to HTTP
    ]

    youtube = get_youtube_client()
    transcript_api = YouTubeTranscriptApi()
    results = []

    for video_id in poc_videos:
        logger.info(f"Processing {video_id}")

        metadata = get_video_metadata(youtube, video_id)
        transcript = extract_transcript(transcript_api, video_id)

        if metadata:
            save_json(metadata, OUTPUT_DIR / f"{video_id}_metadata.json")

        if transcript:
            save_json(transcript, OUTPUT_DIR / f"{video_id}_transcript.json")
            logger.info(f"  {len(transcript)} transcript segments extracted")

        results.append({
            "video_id": video_id,
            "title": metadata["title"] if metadata else "N/A",
            "channel": metadata.get("channel_name", "N/A") if metadata else "N/A",
            "transcript_segments": len(transcript) if transcript else 0,
            "success": transcript is not None,
        })

    # Save a summary of all extractions
    save_json(results, OUTPUT_DIR / "poc_summary.json")

    logger.info("\n=== POC Extraction Summary ===")
    for r in results:
        status = "OK" if r["success"] else "FAILED"
        logger.info(f"  [{status}] {r['title']} — {r['transcript_segments']} segments")


if __name__ == "__main__":
    main()
