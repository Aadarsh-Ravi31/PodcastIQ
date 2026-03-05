import json
import os
import re
import pandas as pd
from pathlib import Path
from ydata_profiling import ProfileReport
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_REPORT_PATH = PROJECT_ROOT / "reports" / "transcript_data_profile.html"

def collect_data():
    """Collects metadata and transcript metrics for all processed episodes."""
    rows = []
    
    if not RAW_DATA_DIR.exists():
        logger.error(f"❌ Error: Raw data directory not found at {RAW_DATA_DIR}")
        return None

    # Iterate through channel directories
    for channel_dir in RAW_DATA_DIR.iterdir():
        if not channel_dir.is_dir():
            continue
            
        logger.info(f"Processing channel: {channel_dir.name}")
        
        # Find all metadata files
        metadata_files = list(channel_dir.glob("*_metadata.json"))
        
        for meta_path in metadata_files:
            video_id = meta_path.name.replace("_metadata.json", "")
            transcript_path = channel_dir / f"{video_id}_transcript.json"
            
            try:
                with open(meta_path, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                
                # Default values if transcript is missing
                transcript_metrics = {
                    "segment_count": 0,
                    "total_words": 0,
                    "duration_covered": 0,
                    "has_transcript": False,
                    "artifact_count": 0,
                    "has_timestamp_gaps": False
                }
                
                if transcript_path.exists():
                    with open(transcript_path, 'r', encoding='utf-8') as f:
                        segments = json.load(f)
                    
                    if segments:
                        transcript_metrics["has_transcript"] = True
                        transcript_metrics["segment_count"] = len(segments)
                        transcript_metrics["total_words"] = sum(len(s["text"].split()) for s in segments)
                        transcript_metrics["duration_covered"] = segments[-1]["start"] + segments[-1]["duration"]
                        
                        # Check for gaps > 30s
                        has_gaps = False
                        for i in range(1, len(segments)):
                            gap = segments[i]["start"] - (segments[i-1]["start"] + segments[i-1]["duration"])
                            if gap > 30:
                                has_gaps = True
                                break
                        transcript_metrics["has_timestamp_gaps"] = has_gaps
                        
                        # Count artifacts
                        artifacts = ["[Music]", "[Applause]", "[Laughter]"]
                        transcript_metrics["artifact_count"] = sum(
                            1 for s in segments if any(a in s["text"] for a in artifacts)
                        )

                # Prepare row
                row = {
                    "channel": meta.get("channel_name", str(channel_dir.name)).replace("_", " "),
                    "video_id": meta.get("video_id"),
                    "title": meta.get("title"),
                    "publish_date": meta.get("publish_date"),
                    "duration_min": meta.get("duration_minutes", 0),
                    "view_count": meta.get("view_count", 0),
                    "like_count": meta.get("like_count", 0),
                    **transcript_metrics
                }
                
                # Add calculated fields
                expected_sec = row["duration_min"] * 60
                row["coverage_pct"] = (row["duration_covered"] / expected_sec) if expected_sec > 0 else 0
                row["words_per_minute"] = (row["total_words"] / (row["duration_covered"] / 60)) if row["duration_covered"] > 0 else 0
                row["avg_segment_len_sec"] = (row["duration_covered"] / row["segment_count"]) if row["segment_count"] > 0 else 0
                
                rows.append(row)
                
            except Exception as e:
                logger.error(f"Error processing {meta_path}: {e}")
                
    return pd.DataFrame(rows)

def main():
    logger.info("✅ Starting advanced data profiling with ydata-profiling...")
    
    df = collect_data()
    
    if df is None or df.empty:
        logger.error("❌ No data collected. Check transcript paths.")
        return

    # Basic cleanup for profiling
    df['publish_date'] = pd.to_datetime(df['publish_date'], errors='coerce')
    
    logger.info(f"✅ Loaded {len(df)} episodes. Generating ProfileReport...")
    
    # Generate profile report using ydata-profiling
    profile = ProfileReport(df, title="PodcastIQ Raw Data Profiling Report", explorative=True)

    # Save the report
    profile.to_file(OUTPUT_REPORT_PATH)

    logger.info(f"✅ Advanced Report Generated Successfully! Saved at: {OUTPUT_REPORT_PATH}")

if __name__ == "__main__":
    main()
