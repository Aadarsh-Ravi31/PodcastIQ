"""
PodcastIQ — run_pipeline_refresh.py
Runs the incremental pipeline refresh:
  CUR_CHUNKS → SEM_CHUNK_EMBEDDINGS → SEM_CHUNK_TOPICS → SEM_CHUNK_ENTITIES → SEM_EPISODE_SUMMARIES

Safe to re-run — all steps use NOT IN deduplication.
"""

import os
import logging
from pathlib import Path

import snowflake.connector
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from dotenv import load_dotenv

load_dotenv()

Path("logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/pipeline_refresh.log", mode="a", encoding="utf-8")
    ]
)
log = logging.getLogger(__name__)


def _load_private_key(key_path: str) -> bytes:
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


STEP1_CHECK = """
SELECT
    COUNT(*) AS new_episodes_to_process
FROM RAW.EPISODES e
WHERE e.VIDEO_ID NOT IN (SELECT DISTINCT VIDEO_ID FROM CURATED.CUR_CHUNKS)
"""

STEP2_CHUNKS = """
INSERT INTO CURATED.CUR_CHUNKS
WITH new_episodes AS (
    SELECT *
    FROM RAW.EPISODES
    WHERE VIDEO_ID NOT IN (SELECT DISTINCT VIDEO_ID FROM CURATED.CUR_CHUNKS)
),
segments_flat AS (
    SELECT
        ep.VIDEO_ID,
        ep.CHANNEL_ID,
        ep.RAW_DATA:channel_name::VARCHAR                           AS CHANNEL_NAME,
        ep.RAW_DATA:genre::VARCHAR                                  AS GENRE,
        ep.RAW_DATA:title::VARCHAR                                  AS EPISODE_TITLE,
        TRY_TO_TIMESTAMP_NTZ(ep.RAW_DATA:publish_date::VARCHAR)     AS PUBLISH_DATE,
        CASE
            WHEN ep.RAW_DATA:coverage_pct::FLOAT >= 0.85 THEN 'HIGH'
            WHEN ep.RAW_DATA:coverage_pct::FLOAT >= 0.65 THEN 'MEDIUM'
            ELSE 'LOW'
        END                                                         AS TRANSCRIPT_QUALITY,
        seg.value:text::VARCHAR                                     AS SEG_TEXT,
        seg.value:start::FLOAT                                      AS SEG_START,
        seg.value:duration::FLOAT                                   AS SEG_DURATION,
        FLOOR(seg.value:start::FLOAT / 120)                        AS CHUNK_WINDOW
    FROM new_episodes ep,
    LATERAL FLATTEN(input => ep.RAW_DATA:segments) seg
    WHERE seg.value:text::VARCHAR IS NOT NULL
      AND TRIM(seg.value:text::VARCHAR) != ''
),
chunks_agg AS (
    SELECT
        VIDEO_ID,
        CHANNEL_ID,
        CHANNEL_NAME,
        GENRE,
        EPISODE_TITLE,
        PUBLISH_DATE,
        TRANSCRIPT_QUALITY,
        CHUNK_WINDOW,
        LISTAGG(SEG_TEXT, ' ') WITHIN GROUP (ORDER BY SEG_START) AS CHUNK_TEXT,
        MIN(SEG_START)                                            AS CHUNK_START_SEC,
        MAX(SEG_START + SEG_DURATION)                            AS CHUNK_END_SEC,
        MAX(SEG_START + SEG_DURATION) - MIN(SEG_START)           AS CHUNK_DURATION_SEC,
        COUNT(*)                                                  AS SEGMENT_COUNT,
        SUM(ARRAY_SIZE(SPLIT(SEG_TEXT, ' ')))                    AS WORD_COUNT
    FROM segments_flat
    GROUP BY 1, 2, 3, 4, 5, 6, 7, 8
)
SELECT
    VIDEO_ID || '_chunk_' || LPAD(CHUNK_WINDOW::VARCHAR, 4, '0')  AS CHUNK_ID,
    VIDEO_ID,
    CHANNEL_ID,
    CHANNEL_NAME,
    GENRE,
    EPISODE_TITLE,
    PUBLISH_DATE,
    TRANSCRIPT_QUALITY,
    CHUNK_WINDOW,
    CHUNK_TEXT,
    CHUNK_START_SEC,
    CHUNK_END_SEC,
    CHUNK_DURATION_SEC,
    SEGMENT_COUNT,
    WORD_COUNT,
    'https://www.youtube.com/watch?v=' || VIDEO_ID
        || '&t=' || FLOOR(CHUNK_START_SEC)::VARCHAR || 's'        AS YOUTUBE_URL
FROM chunks_agg
WHERE LEN(CHUNK_TEXT) > 50
ORDER BY VIDEO_ID, CHUNK_WINDOW
"""

STEP3_EMBEDDINGS = """
INSERT INTO SEMANTIC.SEM_CHUNK_EMBEDDINGS
SELECT
    c.CHUNK_ID,
    c.VIDEO_ID,
    c.CHANNEL_NAME,
    c.GENRE,
    c.EPISODE_TITLE,
    c.PUBLISH_DATE,
    c.TRANSCRIPT_QUALITY,
    c.CHUNK_START_SEC,
    c.CHUNK_END_SEC,
    c.WORD_COUNT,
    c.YOUTUBE_URL,
    c.CHUNK_TEXT,
    SNOWFLAKE.CORTEX.EMBED_TEXT_768('snowflake-arctic-embed-m', c.CHUNK_TEXT) AS EMBEDDING
FROM CURATED.CUR_CHUNKS c
WHERE c.VIDEO_ID NOT IN (
    SELECT DISTINCT VIDEO_ID FROM SEMANTIC.SEM_CHUNK_EMBEDDINGS
)
"""

STEP4_TOPICS = """
INSERT INTO SEMANTIC.SEM_CHUNK_TOPICS
SELECT
    c.CHUNK_ID,
    c.VIDEO_ID,
    c.CHANNEL_NAME,
    c.GENRE,
    c.CHUNK_TEXT,
    SNOWFLAKE.CORTEX.COMPLETE(
        'llama3.1-405b',
        CONCAT(
            'Extract 3-5 key topics from this podcast transcript chunk as a JSON array of short strings. ',
            'Topics should be specific (e.g. "machine learning", "venture capital", "intermittent fasting"). ',
            'Return ONLY the JSON array, no explanation.\\n\\n',
            'Transcript: ', LEFT(c.CHUNK_TEXT, 1500)
        )
    ) AS TOPICS_RAW
FROM CURATED.CUR_CHUNKS c
WHERE c.VIDEO_ID NOT IN (
    SELECT DISTINCT VIDEO_ID FROM SEMANTIC.SEM_CHUNK_TOPICS
)
"""

STEP5_ENTITIES = """
INSERT INTO SEMANTIC.SEM_CHUNK_ENTITIES
SELECT
    c.CHUNK_ID,
    c.VIDEO_ID,
    c.CHANNEL_NAME,
    c.GENRE,
    SNOWFLAKE.CORTEX.COMPLETE(
        'llama3.1-405b',
        CONCAT(
            'Extract named entities from this podcast transcript chunk. ',
            'Return a JSON object with three arrays: ',
            '"people" (full names), "organizations" (companies, institutions), "technologies" (tools, platforms, research areas). ',
            'Return ONLY the JSON object, no explanation.\\n\\n',
            'Transcript: ', LEFT(c.CHUNK_TEXT, 1500)
        )
    ) AS ENTITIES_RAW
FROM CURATED.CUR_CHUNKS c
WHERE c.VIDEO_ID NOT IN (
    SELECT DISTINCT VIDEO_ID FROM SEMANTIC.SEM_CHUNK_ENTITIES
)
"""

STEP6_SUMMARIES = """
INSERT INTO SEMANTIC.SEM_EPISODE_SUMMARIES (VIDEO_ID, CHANNEL_NAME, GENRE, TITLE, EPISODE_SUMMARY)
WITH new_video_ids AS (
    SELECT DISTINCT VIDEO_ID
    FROM CURATED.CUR_CHUNKS
    WHERE VIDEO_ID NOT IN (
        SELECT DISTINCT VIDEO_ID FROM SEMANTIC.SEM_EPISODE_SUMMARIES
    )
),
episode_context AS (
    SELECT
        c.VIDEO_ID,
        c.CHANNEL_NAME,
        c.GENRE,
        c.EPISODE_TITLE,
        LISTAGG(c.CHUNK_TEXT, ' ') WITHIN GROUP (ORDER BY c.CHUNK_START_SEC)
            AS FULL_TRANSCRIPT_SAMPLE
    FROM CURATED.CUR_CHUNKS c
    INNER JOIN new_video_ids n ON c.VIDEO_ID = n.VIDEO_ID
    WHERE c.CHUNK_WINDOW <= 4
    GROUP BY 1, 2, 3, 4
)
SELECT
    ep.VIDEO_ID,
    ep.CHANNEL_NAME,
    ep.GENRE,
    ep.EPISODE_TITLE,
    SNOWFLAKE.CORTEX.COMPLETE(
        'llama3.1-405b',
        CONCAT(
            'Write a 2-3 sentence summary of this podcast episode. ',
            'Focus on the main topics discussed, key insights, and notable claims or arguments. ',
            'Be concise and informative.\\n\\n',
            'Episode: "', ep.EPISODE_TITLE, '" on ', ep.CHANNEL_NAME, '\\n',
            'Transcript excerpt: ', LEFT(ep.FULL_TRANSCRIPT_SAMPLE, 3000)
        )
    ) AS EPISODE_SUMMARY
FROM episode_context ep
"""

HEALTH_CHECK = """
SELECT layer, row_count, unique_videos FROM (
    SELECT 'RAW.EPISODES'             AS layer, COUNT(*) AS row_count, COUNT(DISTINCT VIDEO_ID) AS unique_videos FROM RAW.EPISODES
    UNION ALL SELECT 'CUR_CHUNKS',        COUNT(*), COUNT(DISTINCT VIDEO_ID) FROM CURATED.CUR_CHUNKS
    UNION ALL SELECT 'SEM_EMBEDDINGS',   COUNT(*), COUNT(DISTINCT VIDEO_ID) FROM SEMANTIC.SEM_CHUNK_EMBEDDINGS
    UNION ALL SELECT 'SEM_TOPICS',       COUNT(*), COUNT(DISTINCT VIDEO_ID) FROM SEMANTIC.SEM_CHUNK_TOPICS
    UNION ALL SELECT 'SEM_ENTITIES',     COUNT(*), COUNT(DISTINCT VIDEO_ID) FROM SEMANTIC.SEM_CHUNK_ENTITIES
    UNION ALL SELECT 'SEM_SUMMARIES',    COUNT(*), COUNT(DISTINCT VIDEO_ID) FROM SEMANTIC.SEM_EPISODE_SUMMARIES
) ORDER BY layer
"""


def run_step(cursor, name: str, sql: str, is_insert: bool = True):
    log.info(f"\n{'='*60}")
    log.info(f"Running: {name}")
    log.info(f"{'='*60}")
    cursor.execute(sql)
    if is_insert:
        rows = cursor.rowcount
        log.info(f"  ✅ {name} complete — {rows} rows inserted")
        return rows
    else:
        results = cursor.fetchall()
        return results


def main():
    log.info("=" * 60)
    log.info("PodcastIQ Pipeline Refresh — Starting")
    log.info("=" * 60)

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Step 1: Check how many new episodes to process
        cursor.execute(STEP1_CHECK)
        new_eps = cursor.fetchone()[0]
        log.info(f"\n📊 New episodes not yet chunked: {new_eps}")

        # Step 2: Chunk new episodes (skips automatically if nothing new)
        run_step(cursor, "STEP 2: CUR_CHUNKS", STEP2_CHUNKS)

        # Step 3: Generate embeddings (most expensive)
        log.info("\n⏳ STEP 3: Generating embeddings (Cortex arctic-embed-m) — this may take a few minutes...")
        run_step(cursor, "STEP 3: SEM_CHUNK_EMBEDDINGS", STEP3_EMBEDDINGS)

        # Step 4: Extract topics
        log.info("\n⏳ STEP 4: Extracting topics (llama3.1-405b) — LLM calls per chunk...")
        run_step(cursor, "STEP 4: SEM_CHUNK_TOPICS", STEP4_TOPICS)

        # Step 5: Extract entities
        log.info("\n⏳ STEP 5: Extracting entities (llama3.1-405b)...")
        run_step(cursor, "STEP 5: SEM_CHUNK_ENTITIES", STEP5_ENTITIES)

        # Step 6: Generate episode summaries
        run_step(cursor, "STEP 6: SEM_EPISODE_SUMMARIES", STEP6_SUMMARIES)

        conn.commit()

        # Health check
        log.info("\n" + "=" * 60)
        log.info("PIPELINE HEALTH CHECK")
        log.info("=" * 60)
        cursor.execute(HEALTH_CHECK)
        rows = cursor.fetchall()
        log.info(f"{'Layer':<25} {'Rows':>10} {'Videos':>10}")
        log.info("-" * 50)
        for layer, row_count, unique_videos in rows:
            log.info(f"{layer:<25} {row_count:>10,} {unique_videos:>10,}")

        log.info("\n✅ Pipeline refresh complete!")
        log.info("Cortex Search (PODCASTIQ_SEARCH) auto-refreshes from SEM_CHUNK_EMBEDDINGS.")

    except Exception as e:
        log.error(f"Pipeline refresh failed: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
