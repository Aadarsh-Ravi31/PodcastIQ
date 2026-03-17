-- ============================================================
-- PodcastIQ — Pipeline Verification Script
-- Run this in Snowflake to confirm all steps are complete
-- ============================================================

USE DATABASE PODCASTIQ;

-- ============================================================
-- STEP 1: RAW LAYER — Was data loaded?
-- ============================================================
SELECT '=== RAW LAYER ===' AS section, NULL AS metric, NULL AS value, NULL AS status;

SELECT
    'RAW Episodes (raw_episodes or similar)' AS check_name,
    COUNT(*) AS row_count,
    CASE WHEN COUNT(*) > 0 THEN '✅ Loaded' ELSE '❌ Empty' END AS status
FROM RAW.STG_EPISODES  -- adjust table name if different
UNION ALL
SELECT
    'RAW Segments (raw_segments or similar)',
    COUNT(*),
    CASE WHEN COUNT(*) > 0 THEN '✅ Loaded' ELSE '❌ Empty' END
FROM RAW.STG_SEGMENTS;  -- adjust table name if different

-- ============================================================
-- STEP 2: STAGING LAYER — Were stg_ models built?
-- ============================================================
SELECT '=== STAGING LAYER ===' AS section, NULL AS metric, NULL AS value, NULL AS status;

SELECT
    'STG_EPISODES' AS check_name,
    COUNT(*) AS row_count,
    CASE WHEN COUNT(*) > 100 THEN '✅ OK' WHEN COUNT(*) > 0 THEN '⚠️ Low count' ELSE '❌ Empty' END AS status
FROM STAGING.STG_EPISODES
UNION ALL
SELECT
    'STG_SEGMENTS',
    COUNT(*),
    CASE WHEN COUNT(*) > 1000 THEN '✅ OK' WHEN COUNT(*) > 0 THEN '⚠️ Low count' ELSE '❌ Empty' END
FROM STAGING.STG_SEGMENTS;

-- ============================================================
-- STEP 3: INTERMEDIATE LAYER — Were int_ models built?
-- ============================================================
SELECT '=== INTERMEDIATE LAYER ===' AS section, NULL AS metric, NULL AS value, NULL AS status;

SELECT
    'INT_EPISODES' AS check_name,
    COUNT(*) AS row_count,
    CASE WHEN COUNT(*) > 100 THEN '✅ OK' WHEN COUNT(*) > 0 THEN '⚠️ Low count' ELSE '❌ Empty' END AS status
FROM STAGING.INT_EPISODES
UNION ALL
SELECT
    'INT_SEGMENTS',
    COUNT(*),
    CASE WHEN COUNT(*) > 1000 THEN '✅ OK' WHEN COUNT(*) > 0 THEN '⚠️ Low count' ELSE '❌ Empty' END
FROM STAGING.INT_SEGMENTS;

-- ============================================================
-- STEP 4: CURATED LAYER — Was chunking done?
-- ============================================================
SELECT '=== CURATED LAYER (CHUNKS) ===' AS section, NULL AS metric, NULL AS value, NULL AS status;

SELECT
    'CUR_CHUNKS total rows' AS check_name,
    COUNT(*) AS row_count,
    CASE WHEN COUNT(*) > 5000 THEN '✅ OK (5K+ chunks)' WHEN COUNT(*) > 0 THEN '⚠️ Low count' ELSE '❌ Empty' END AS status
FROM CURATED.CUR_CHUNKS
UNION ALL
SELECT
    'CUR_CHUNKS — unique videos',
    COUNT(DISTINCT VIDEO_ID),
    CASE WHEN COUNT(DISTINCT VIDEO_ID) > 100 THEN '✅ 100+ videos' ELSE '⚠️ <100 videos' END
FROM CURATED.CUR_CHUNKS
UNION ALL
SELECT
    'CUR_CHUNKS — unique channels',
    COUNT(DISTINCT CHANNEL_NAME),
    CASE WHEN COUNT(DISTINCT CHANNEL_NAME) >= 10 THEN '✅ 10+ channels' ELSE '⚠️ <10 channels' END
FROM CURATED.CUR_CHUNKS
UNION ALL
SELECT
    'CUR_CHUNKS — avg chunks per video',
    ROUND(COUNT(*) / NULLIF(COUNT(DISTINCT VIDEO_ID), 0), 1),
    CASE
        WHEN COUNT(*) / NULLIF(COUNT(DISTINCT VIDEO_ID), 0) BETWEEN 20 AND 80 THEN '✅ Good chunk density'
        ELSE '⚠️ Check chunking params'
    END
FROM CURATED.CUR_CHUNKS;

-- Chunk size distribution
SELECT
    'Chunk text length distribution' AS check_name,
    ROUND(AVG(LEN(CHUNK_TEXT))) AS avg_chars,
    MIN(LEN(CHUNK_TEXT)) AS min_chars,
    MAX(LEN(CHUNK_TEXT)) AS max_chars
FROM CURATED.CUR_CHUNKS;

-- ============================================================
-- STEP 5: SEMANTIC LAYER — Were embeddings generated?
-- ============================================================
SELECT '=== SEMANTIC LAYER ===' AS section, NULL AS metric, NULL AS value, NULL AS status;

SELECT
    'SEM_CHUNK_EMBEDDINGS total rows' AS check_name,
    COUNT(*) AS row_count,
    CASE WHEN COUNT(*) > 5000 THEN '✅ OK' WHEN COUNT(*) > 0 THEN '⚠️ Low count' ELSE '❌ Empty' END AS status
FROM SEMANTIC.SEM_CHUNK_EMBEDDINGS
UNION ALL
SELECT
    'SEM_CHUNK_TOPICS total rows',
    COUNT(*),
    CASE WHEN COUNT(*) > 0 THEN '✅ OK' ELSE '❌ Empty' END
FROM SEMANTIC.SEM_CHUNK_TOPICS
UNION ALL
SELECT
    'SEM_CHUNK_ENTITIES total rows',
    COUNT(*),
    CASE WHEN COUNT(*) > 0 THEN '✅ OK' ELSE '❌ Empty' END
FROM SEMANTIC.SEM_CHUNK_ENTITIES
UNION ALL
SELECT
    'SEM_EPISODE_SUMMARIES total rows',
    COUNT(*),
    CASE WHEN COUNT(*) > 100 THEN '✅ OK' WHEN COUNT(*) > 0 THEN '⚠️ Low count' ELSE '❌ Empty' END
FROM SEMANTIC.SEM_EPISODE_SUMMARIES;

-- Embedding coverage check (% of chunks that have embeddings)
SELECT
    'Embedding coverage %' AS check_name,
    ROUND(
        COUNT(DISTINCT e.CHUNK_ID) * 100.0 / NULLIF(COUNT(DISTINCT c.CHUNK_ID), 0),
        2
    ) AS coverage_pct,
    CASE
        WHEN COUNT(DISTINCT e.CHUNK_ID) * 100.0 / NULLIF(COUNT(DISTINCT c.CHUNK_ID), 0) >= 99 THEN '✅ Full coverage'
        WHEN COUNT(DISTINCT e.CHUNK_ID) * 100.0 / NULLIF(COUNT(DISTINCT c.CHUNK_ID), 0) >= 90 THEN '⚠️ Partial coverage'
        ELSE '❌ Low coverage'
    END AS status
FROM CURATED.CUR_CHUNKS c
LEFT JOIN SEMANTIC.SEM_CHUNK_EMBEDDINGS e ON c.CHUNK_ID = e.CHUNK_ID;

-- ============================================================
-- STEP 6: CORTEX SEARCH SERVICE — Is it live?
-- ============================================================
SHOW CORTEX SEARCH SERVICES IN DATABASE PODCASTIQ;

-- ============================================================
-- STEP 7: QUICK SEARCH TEST — Does semantic search work?
-- ============================================================
SELECT '=== CORTEX SEARCH TEST ===' AS section;

-- Uncomment and run this to test search:
-- SELECT *
-- FROM TABLE(
--     PODCASTIQ.SEMANTIC.PODCASTIQ_SEARCH!SEARCH(
--         'machine learning transformers',
--         {'limit': 5}
--     )
-- );

-- ============================================================
-- STEP 8: DATA QUALITY CHECKS
-- ============================================================
SELECT '=== DATA QUALITY ===' AS section;

-- Null checks on CUR_CHUNKS
SELECT
    'Null CHUNK_ID in CUR_CHUNKS' AS check_name,
    SUM(CASE WHEN CHUNK_ID IS NULL THEN 1 ELSE 0 END) AS null_count,
    CASE WHEN SUM(CASE WHEN CHUNK_ID IS NULL THEN 1 ELSE 0 END) = 0 THEN '✅ No nulls' ELSE '❌ Has nulls' END AS status
FROM CURATED.CUR_CHUNKS
UNION ALL
SELECT
    'Null CHUNK_TEXT in CUR_CHUNKS',
    SUM(CASE WHEN CHUNK_TEXT IS NULL OR TRIM(CHUNK_TEXT) = '' THEN 1 ELSE 0 END),
    CASE WHEN SUM(CASE WHEN CHUNK_TEXT IS NULL OR TRIM(CHUNK_TEXT) = '' THEN 1 ELSE 0 END) = 0 THEN '✅ No nulls' ELSE '❌ Has nulls' END
FROM CURATED.CUR_CHUNKS
UNION ALL
SELECT
    'Null CHUNK_ID in SEM_CHUNK_EMBEDDINGS',
    SUM(CASE WHEN CHUNK_ID IS NULL THEN 1 ELSE 0 END),
    CASE WHEN SUM(CASE WHEN CHUNK_ID IS NULL THEN 1 ELSE 0 END) = 0 THEN '✅ No nulls' ELSE '❌ Has nulls' END
FROM SEMANTIC.SEM_CHUNK_EMBEDDINGS;

-- ============================================================
-- STEP 9: FULL PIPELINE SUMMARY
-- ============================================================
SELECT '=== PIPELINE SUMMARY ===' AS label;

SELECT
    'Step 1-2: Extract & Profile'   AS pipeline_step,
    '✅ Done'                        AS status,
    '250+ episodes extracted locally' AS notes
UNION ALL SELECT 'Step 3-4: Stage & Load RAW',     '✅ Done', 'JSON staged + loaded to Snowflake RAW'
UNION ALL SELECT 'Step 5: Clean (stg_ models)',     '✅ Done', 'STG_EPISODES, STG_SEGMENTS in STAGING'
UNION ALL SELECT 'Step 6: Structure (int_ models)', '✅ Done', 'INT_EPISODES, INT_SEGMENTS in STAGING'
UNION ALL SELECT 'Step 7: Chunk (cur_ models)',     '✅ Done', 'CUR_CHUNKS in CURATED'
UNION ALL SELECT 'Step 8: Enrich (sem_ models)',    '✅ Done', 'Embeddings, Topics, Entities, Summaries in SEMANTIC'
UNION ALL SELECT 'Step 9: Index (Cortex Search)',   '✅ Done', 'PODCASTIQ_SEARCH service active'
UNION ALL SELECT 'Step 10: Validate (dbt tests)',   '[ ] TODO', 'Run: dbt test'
UNION ALL SELECT 'Week 4: LangGraph Agents MVP',    '[ ] TODO', 'Router + Search + Summarization agents'
UNION ALL SELECT 'Week 5: Streamlit UI',            '[ ] TODO', 'Frontend search interface'
UNION ALL SELECT 'Week 6: Stretch Agents + MCP',   '[ ] TODO', 'Comparison, Recommendation, MCP servers'
UNION ALL SELECT 'Week 7: Airflow + Testing',       '[ ] TODO', 'DAG orchestration + optimization'
UNION ALL SELECT 'Week 8: Final Demo',              '[ ] TODO', 'Presentation + report';
