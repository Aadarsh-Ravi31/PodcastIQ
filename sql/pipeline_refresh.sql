-- ============================================================
-- PodcastIQ — Incremental Pipeline Refresh
-- Run this after loading new episodes via snowflake_loader.py
--
-- This script is INCREMENTAL — it only processes VIDEO_IDs that
-- are not already present in each downstream table. Safe to re-run.
--
-- Run order:
--   1. python scripts/snowflake_loader.py      (loads new JSON → RAW.EPISODES)
--   2. This script — run each section in order in Snowflake
--   3. Verify with sql/pipeline_verification.sql
-- ============================================================

USE DATABASE PODCASTIQ;
USE WAREHOUSE PODCASTIQ_WH;

-- ============================================================
-- STEP 1: Check what new VIDEO_IDs need processing
-- ============================================================

-- New episodes in RAW not yet chunked in CUR_CHUNKS
SELECT
    e.VIDEO_ID,
    e.RAW_DATA:title::VARCHAR AS title,
    e.RAW_DATA:publish_date::VARCHAR AS publish_date
FROM RAW.EPISODES e
WHERE e.VIDEO_ID NOT IN (SELECT DISTINCT VIDEO_ID FROM CURATED.CUR_CHUNKS)
ORDER BY e.LOADED_AT DESC;

-- ============================================================
-- STEP 2: Chunk new episodes into CUR_CHUNKS (120-second windows)
-- ============================================================
-- Inserts only VIDEO_IDs not already in CUR_CHUNKS.
-- Chunking logic: LATERAL FLATTEN on segments array, group by 120-second windows.

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
WHERE LEN(CHUNK_TEXT) > 50    -- Skip near-empty chunks
ORDER BY VIDEO_ID, CHUNK_WINDOW;

-- Verify chunk insertion
SELECT
    COUNT(*) AS new_chunks_added,
    COUNT(DISTINCT VIDEO_ID) AS new_videos_chunked
FROM CURATED.CUR_CHUNKS
WHERE VIDEO_ID NOT IN (
    SELECT DISTINCT VIDEO_ID FROM SEMANTIC.SEM_CHUNK_EMBEDDINGS
);

-- ============================================================
-- STEP 3: Generate embeddings for new chunks
-- ============================================================
-- Uses Snowflake Arctic Embed M (768-dim). Only processes chunks
-- not already in SEM_CHUNK_EMBEDDINGS.
-- NOTE: This is the most expensive step (~1-2 Snowflake credits per 10K chunks).
--       Estimated ~1,800 new chunks × $0.0001 = low cost.

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
);

-- Verify embedding coverage
SELECT
    COUNT(DISTINCT c.CHUNK_ID)                                      AS total_chunks,
    COUNT(DISTINCT e.CHUNK_ID)                                      AS embedded_chunks,
    ROUND(COUNT(DISTINCT e.CHUNK_ID) * 100.0 /
          NULLIF(COUNT(DISTINCT c.CHUNK_ID), 0), 1)                 AS coverage_pct
FROM CURATED.CUR_CHUNKS c
LEFT JOIN SEMANTIC.SEM_CHUNK_EMBEDDINGS e ON c.CHUNK_ID = e.CHUNK_ID;

-- ============================================================
-- STEP 4: Extract topics for new chunks
-- ============================================================
-- Uses llama3.1-405b to extract 3-5 topics per chunk as a JSON array.
-- Only processes chunks not already in SEM_CHUNK_TOPICS.

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
            'Return ONLY the JSON array, no explanation.\n\n',
            'Transcript: ', LEFT(c.CHUNK_TEXT, 1500)
        )
    ) AS TOPICS_RAW
FROM CURATED.CUR_CHUNKS c
WHERE c.VIDEO_ID NOT IN (
    SELECT DISTINCT VIDEO_ID FROM SEMANTIC.SEM_CHUNK_TOPICS
);

-- ============================================================
-- STEP 5: Extract entities for new chunks
-- ============================================================
-- Uses llama3.1-405b to extract people, organizations, and technologies.
-- Only processes chunks not already in SEM_CHUNK_ENTITIES.

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
            'Return ONLY the JSON object, no explanation.\n\n',
            'Transcript: ', LEFT(c.CHUNK_TEXT, 1500)
        )
    ) AS ENTITIES_RAW
FROM CURATED.CUR_CHUNKS c
WHERE c.VIDEO_ID NOT IN (
    SELECT DISTINCT VIDEO_ID FROM SEMANTIC.SEM_CHUNK_ENTITIES
);

-- ============================================================
-- STEP 6: Generate episode summaries for new episodes
-- ============================================================
-- Concatenates first 5 chunks (~10 minutes) per episode for context.
-- Uses llama3.1-405b to produce a 2-3 sentence summary.
-- Only processes VIDEO_IDs not already in SEM_EPISODE_SUMMARIES.

INSERT INTO SEMANTIC.SEM_EPISODE_SUMMARIES
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
        c.PUBLISH_DATE,
        LISTAGG(c.CHUNK_TEXT, ' ') WITHIN GROUP (ORDER BY c.CHUNK_START_SEC)
            AS FULL_TRANSCRIPT_SAMPLE
    FROM CURATED.CUR_CHUNKS c
    INNER JOIN new_video_ids n ON c.VIDEO_ID = n.VIDEO_ID
    WHERE c.CHUNK_WINDOW <= 4   -- First 5 chunks ≈ 10 minutes context
    GROUP BY 1, 2, 3, 4, 5
)
SELECT
    ep.VIDEO_ID,
    ep.CHANNEL_NAME,
    ep.GENRE,
    ep.EPISODE_TITLE,
    ep.PUBLISH_DATE,
    SNOWFLAKE.CORTEX.COMPLETE(
        'llama3.1-405b',
        CONCAT(
            'Write a 2-3 sentence summary of this podcast episode. ',
            'Focus on the main topics discussed, key insights, and notable claims or arguments. ',
            'Be concise and informative.\n\n',
            'Episode: "', ep.EPISODE_TITLE, '" on ', ep.CHANNEL_NAME, '\n',
            'Transcript excerpt: ', LEFT(ep.FULL_TRANSCRIPT_SAMPLE, 3000)
        )
    ) AS EPISODE_SUMMARY
FROM episode_context ep;

-- ============================================================
-- STEP 7: Create new semantic tables (if not already created)
-- ============================================================
-- Run DDL for new tables added in Week 4:

-- CREATE TABLE IF NOT EXISTS PODCASTIQ.SEMANTIC.SEM_EPISODE_PARTICIPANTS ...
-- (see sql/ddl/semantic/sem_episode_participants.sql)

-- CREATE TABLE IF NOT EXISTS PODCASTIQ.SEMANTIC.SEM_CLAIMS ...
-- (see sql/ddl/semantic/sem_claims.sql)

-- CREATE TABLE IF NOT EXISTS PODCASTIQ.SEMANTIC.SEM_CLAIM_EVOLUTION ...
-- (see sql/ddl/semantic/sem_claim_evolution.sql)

-- ============================================================
-- STEP 8: Final pipeline health check
-- ============================================================

SELECT
    'RAW.EPISODES'                  AS layer,
    COUNT(*)                        AS row_count,
    COUNT(DISTINCT VIDEO_ID)        AS unique_videos
FROM RAW.EPISODES
UNION ALL SELECT 'CURATED.CUR_CHUNKS',      COUNT(*), COUNT(DISTINCT VIDEO_ID) FROM CURATED.CUR_CHUNKS
UNION ALL SELECT 'SEM_CHUNK_EMBEDDINGS',    COUNT(*), COUNT(DISTINCT VIDEO_ID) FROM SEMANTIC.SEM_CHUNK_EMBEDDINGS
UNION ALL SELECT 'SEM_CHUNK_TOPICS',        COUNT(*), COUNT(DISTINCT VIDEO_ID) FROM SEMANTIC.SEM_CHUNK_TOPICS
UNION ALL SELECT 'SEM_CHUNK_ENTITIES',      COUNT(*), COUNT(DISTINCT VIDEO_ID) FROM SEMANTIC.SEM_CHUNK_ENTITIES
UNION ALL SELECT 'SEM_EPISODE_SUMMARIES',   COUNT(*), COUNT(DISTINCT VIDEO_ID) FROM SEMANTIC.SEM_EPISODE_SUMMARIES
ORDER BY layer;

-- Expected after refresh:
--   RAW.EPISODES:           ~286+ rows (250 original + ~36 new)
--   CUR_CHUNKS:             ~20,000+ rows
--   SEM_CHUNK_EMBEDDINGS:   ~20,000+ rows (coverage = 100%)
--   SEM_CHUNK_TOPICS:       ~20,000+ rows
--   SEM_CHUNK_ENTITIES:     ~20,000+ rows
--   SEM_EPISODE_SUMMARIES:  ~286+ rows

-- Cortex Search (PODCASTIQ_SEARCH) auto-refreshes from SEM_CHUNK_EMBEDDINGS.
-- No manual action needed for search service after inserting new embeddings.
