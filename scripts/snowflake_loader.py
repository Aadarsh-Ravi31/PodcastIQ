"""
PodcastIQ — snowflake_loader.py
Loads extracted podcast data into Snowflake RAW layer.

Flow:
  data/raw/{channel_name}/{video_id}_metadata.json   ─┐
                                                       ├─ merge → PUT → COPY INTO RAW.EPISODES
  data/raw/{channel_name}/{video_id}_transcript.json ─┘
                                                       └─ MERGE INTO RAW.CHANNELS

Usage:
  python scripts/snowflake_loader.py
"""

import json
import os
import re
import tempfile
import logging
from pathlib import Path
from datetime import datetime

import snowflake.connector
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────
Path("logs").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/loader.log", mode="a", encoding="utf-8")
    ]
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────
RAW_DATA_DIR   = Path("data/raw")
STAGE_NAME     = "@PODCASTIQ.RAW.PODCAST_DATA_STAGE"
EPISODES_TABLE = "PODCASTIQ.RAW.EPISODES"
CHANNELS_TABLE = "PODCASTIQ.RAW.CHANNELS"

# Artifact patterns to detect in transcript text
ARTIFACT_PATTERNS = re.compile(
    r'\[Music\]|\[Applause\]|\[Laughter\]|\[Cheering\]|\[Silence\]|\[Inaudible\]',
    re.IGNORECASE
)


# ─────────────────────────────────────────────
# Snowflake connection
# ─────────────────────────────────────────────
def _load_private_key(key_path: str) -> bytes:
    """Load and deserialize a PEM-encoded private key for Snowflake key-pair auth."""
    with open(key_path, "rb") as f:
        private_key = serialization.load_pem_private_key(
            f.read(),
            password=os.environ.get("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE", "").encode() or None,
            backend=default_backend()
        )
    return private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )


def get_connection():
    """Create Snowflake connection using key-pair authentication."""
    key_path = os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH")
    if not key_path:
        raise ValueError("SNOWFLAKE_PRIVATE_KEY_PATH not set in .env")

    return snowflake.connector.connect(
        account    = os.getenv("SNOWFLAKE_ACCOUNT"),
        user       = os.getenv("SNOWFLAKE_USER"),
        private_key = _load_private_key(key_path),
        warehouse  = os.getenv("SNOWFLAKE_WAREHOUSE", "PODCASTIQ_WH"),
        database   = os.getenv("SNOWFLAKE_DATABASE",  "PODCASTIQ"),
        schema     = os.getenv("SNOWFLAKE_SCHEMA",     "RAW"),
        role       = os.getenv("SNOWFLAKE_ROLE",       "TRAINING_ROLE")
    )


# ─────────────────────────────────────────────
# Channel → genre mapping
# ─────────────────────────────────────────────
CHANNEL_GENRE_MAP = {
    "lex_fridman_podcast":           "Technology & AI",
    "all_in_podcast":                "Technology & AI",
    "no_priors":                     "Technology & AI",
    "acquired_podcast":              "Technology & AI",
    "a16z_podcast":                  "Technology & AI",
    "hard_fork__nyt":                "Technology & AI",
    "the_cognitive_revolution":      "Technology & AI",
    "the_tim_ferriss_show":          "Business & Entrepreneurship",
    "my_first_million":              "Business & Entrepreneurship",
    "lenny_s_podcast":               "Business & Entrepreneurship",
    "wondery__how_i_built_this":     "Business & Entrepreneurship",
    "y_combinator":                  "Business & Entrepreneurship",
    "the_knowledge_project":         "Business & Entrepreneurship",
    "huberman_lab":                  "Science & Health",
    "the_peter_attia_drive":         "Science & Health",
    "foundmyfitness":                "Science & Health",
    "startalk":                      "Science & Health",
    "impact_theory":                 "Education & Self-Improvement",
    "deep_dive_with_ali_abdaal":     "Education & Self-Improvement",
    "the_diary_of_a_ceo":            "Education & Self-Improvement",
    "founders_podcast":              "Education & Self-Improvement",
    "modern_wisdom":                 "Education & Self-Improvement",
    "20vc_with_harry_stebbings":     "Startup & VC",
    "masters_of_scale":              "Startup & VC",
    "joe_rogan_experience":          "Cross-Disciplinary",
}


def get_genre(channel_folder: str) -> str:
    """Map channel folder name to genre. Falls back to partial match, then 'Unknown'."""
    key = channel_folder.lower().replace(" ", "_").replace("-", "_")
    if key in CHANNEL_GENRE_MAP:
        return CHANNEL_GENRE_MAP[key]
    for k, v in CHANNEL_GENRE_MAP.items():
        if k in key or key in k:
            return v
    log.warning(f"Genre not found for channel folder: {channel_folder}")
    return "Unknown"


# ─────────────────────────────────────────────
# Merge metadata + transcript into one payload
# ─────────────────────────────────────────────
def merge_payload(metadata: dict, segments: list, channel_name: str, genre: str) -> dict:
    """
    Merge metadata dict + transcript segments list into single payload.
    Computes basic quality metrics inline.

    Metadata fields (from actual JSON):
      video_id, title, description, channel_id, channel_name,
      publish_date, duration_iso, duration_minutes, view_count,
      like_count, video_url

    Transcript segment fields:
      text, start, duration
    """
    # ── Basic transcript metrics ──────────────────────────
    total_words    = sum(len(s.get("text", "").split()) for s in segments)
    segment_count  = len(segments)
    artifact_count = sum(1 for s in segments if ARTIFACT_PATTERNS.search(s.get("text", "")))

    # Duration covered by transcript
    duration_covered = 0.0
    if segments:
        last = segments[-1]
        duration_covered = round(last.get("start", 0) + last.get("duration", 0), 3)

    # Coverage % — transcript duration vs video duration
    duration_seconds = metadata.get("duration_minutes", 0) * 60
    coverage_pct = round(duration_covered / duration_seconds, 6) if duration_seconds > 0 else 0.0

    # Words per minute
    words_per_minute = round(
        total_words / metadata.get("duration_minutes", 1), 4
    ) if metadata.get("duration_minutes", 0) > 0 else 0.0

    # Avg segment length in seconds
    avg_segment_len_sec = round(
        sum(s.get("duration", 0) for s in segments) / segment_count, 7
    ) if segment_count > 0 else 0.0

    # Timestamp gap detection (gap > 5s between consecutive segments)
    has_timestamp_gaps = False
    for i in range(1, len(segments)):
        prev_end = segments[i-1].get("start", 0) + segments[i-1].get("duration", 0)
        gap = segments[i].get("start", 0) - prev_end
        if gap > 5.0:
            has_timestamp_gaps = True
            break

    # ── Build merged payload ──────────────────────────────
    return {
        # From metadata (matching actual field names in JSON)
        "video_id":         metadata["video_id"],
        "channel_id":       metadata["channel_id"],
        "channel_name":     metadata["channel_name"],
        "genre":            genre,
        "title":            metadata.get("title"),
        "description":      metadata.get("description"),
        "publish_date":     metadata.get("publish_date"),
        "duration_iso":     metadata.get("duration_iso"),
        "duration_min":     metadata.get("duration_minutes"),
        "view_count":       metadata.get("view_count"),
        "like_count":       metadata.get("like_count"),
        "video_url":        metadata.get("video_url"),

        # Full transcript array preserved
        "segments":         segments,

        # Computed quality metrics
        "segment_count":        segment_count,
        "total_words":          total_words,
        "duration_covered":     duration_covered,
        "coverage_pct":         coverage_pct,
        "artifact_count":       artifact_count,
        "has_timestamp_gaps":   has_timestamp_gaps,
        "has_transcript":       True,
        "words_per_minute":     words_per_minute,
        "avg_segment_len_sec":  avg_segment_len_sec,

        # Loader metadata
        "load_source": f"{channel_name}/{metadata['video_id']}",
        "loaded_at":   datetime.utcnow().isoformat()
    }


# ─────────────────────────────────────────────
# Core loading functions
# ─────────────────────────────────────────────
def upsert_channel(cursor, metadata: dict, genre: str):
    """
    MERGE channel record into RAW.CHANNELS.
    Idempotent — safe to run multiple times.
    """
    cursor.execute(f"""
        MERGE INTO {CHANNELS_TABLE} AS target
        USING (
            SELECT
                %s AS channel_id,
                %s AS channel_name,
                %s AS genre,
                %s AS youtube_url
        ) AS source
        ON target.channel_id = source.channel_id
        WHEN NOT MATCHED THEN
            INSERT (channel_id, channel_name, genre, youtube_url)
            VALUES (source.channel_id, source.channel_name, source.genre, source.youtube_url)
    """, (
        metadata["channel_id"],
        metadata["channel_name"],
        genre,
        f"https://www.youtube.com/channel/{metadata['channel_id']}"
    ))


def load_episode(cursor, payload: dict, source_file: str) -> bool:
    """
    Load one episode via PUT + COPY INTO.
    Uses COPY INTO with ON_ERROR=SKIP_FILE for robustness.

    Returns True if loaded, False if skipped (already exists or error).
    """
    video_id = payload["video_id"]

    # Write merged payload to a temp file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", prefix=f"{video_id}_",
        delete=False, encoding="utf-8"
    ) as f:
        json.dump(payload, f, ensure_ascii=False)
        tmp_path = f.name

    try:
        # Normalize path separators for Snowflake PUT on Windows
        tmp_path_normalized = Path(tmp_path).as_posix()

        # PUT file to internal stage
        put_cmd = (
            f"PUT 'file://{tmp_path_normalized}' {STAGE_NAME} "
            f"AUTO_COMPRESS=TRUE OVERWRITE=TRUE"
        )
        cursor.execute(put_cmd)

        staged_filename = os.path.basename(tmp_path) + ".gz"

        # COPY INTO RAW.EPISODES
        cursor.execute(f"""
            COPY INTO {EPISODES_TABLE} (video_id, channel_id, source_file, raw_data)
            FROM (
                SELECT
                    $1:video_id::VARCHAR(20),
                    $1:channel_id::VARCHAR(30),
                    '{source_file}',
                    $1
                FROM {STAGE_NAME}/{staged_filename}
            )
            FILE_FORMAT = (FORMAT_NAME = 'PODCASTIQ.RAW.JSON_FORMAT')
            ON_ERROR = 'SKIP_FILE'
            PURGE = TRUE
        """)

        result = cursor.fetchone()
        status = result[1] if result else "unknown"

        if status == "LOADED":
            log.info(f"  ✅ Loaded:   {video_id} | {payload.get('title', '')[:60]}")
            return True
        else:
            log.warning(f"  ⚠️  Skipped  {video_id}: status={status}")
            return False

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# ─────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────
def run_loader():
    """
    Main loader: iterates all channel folders in data/raw/ and loads episodes.
    Idempotent — safe to re-run. Already loaded episodes are skipped.
    """
    log.info("=" * 60)
    log.info("PodcastIQ Snowflake Loader — Starting")
    log.info(f"  Source dir : {RAW_DATA_DIR.resolve()}")
    log.info(f"  Stage      : {STAGE_NAME}")
    log.info(f"  Episodes   : {EPISODES_TABLE}")
    log.info(f"  Channels   : {CHANNELS_TABLE}")
    log.info("=" * 60)

    conn   = get_connection()
    cursor = conn.cursor()

    stats = {
        "total":    0,
        "loaded":   0,
        "skipped":  0,
        "failed":   0,
        "channels": 0
    }

    try:
        for channel_dir in sorted(RAW_DATA_DIR.iterdir()):
            if not channel_dir.is_dir():
                continue

            channel_name  = channel_dir.name
            genre         = get_genre(channel_name)
            episode_files = sorted(channel_dir.glob("*_metadata.json"))

            if not episode_files:
                log.warning(f"No metadata files in: {channel_name}")
                continue

            log.info(f"\n📂 {channel_name} ({genre}) — {len(episode_files)} episode(s)")
            stats["channels"] += 1

            for meta_file in episode_files:
                video_id        = meta_file.stem.replace("_metadata", "")
                transcript_file = channel_dir / f"{video_id}_transcript.json"
                stats["total"] += 1

                if not transcript_file.exists():
                    log.warning(f"  ⚠️  No transcript for {video_id} — skipping")
                    stats["skipped"] += 1
                    continue

                try:
                    metadata = json.loads(meta_file.read_text(encoding="utf-8"))
                    segments = json.loads(transcript_file.read_text(encoding="utf-8"))

                    if not isinstance(segments, list):
                        log.warning(f"  ⚠️  Bad transcript format for {video_id}")
                        stats["skipped"] += 1
                        continue

                    payload     = merge_payload(metadata, segments, channel_name, genre)
                    source_file = f"{channel_name}/{video_id}"

                    upsert_channel(cursor, metadata, genre)

                    loaded = load_episode(cursor, payload, source_file)
                    if loaded:
                        stats["loaded"] += 1
                    else:
                        stats["skipped"] += 1

                except Exception as e:
                    log.error(f"  ❌ Failed {video_id}: {e}")
                    stats["failed"] += 1

        conn.commit()

    except Exception as e:
        log.error(f"Loader pipeline failed: {e}")
        conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()

    # ── Final summary ──────────────────────────────────────
    log.info("\n" + "=" * 60)
    log.info("LOAD COMPLETE")
    log.info(f"  Channels processed : {stats['channels']}")
    log.info(f"  Total episodes     : {stats['total']}")
    log.info(f"  Loaded             : {stats['loaded']}")
    log.info(f"  Skipped            : {stats['skipped']}")
    log.info(f"  Failed             : {stats['failed']}")
    log.info("=" * 60)
    log.info("\nVerify in Snowflake:")
    log.info("  SELECT COUNT(*) FROM PODCASTIQ.RAW.EPISODES;")
    log.info("  SELECT COUNT(*) FROM PODCASTIQ.RAW.CHANNELS;")
    log.info("  SELECT * FROM PODCASTIQ.UTILS.CHANNEL_COVERAGE;")


if __name__ == "__main__":
    run_loader()
