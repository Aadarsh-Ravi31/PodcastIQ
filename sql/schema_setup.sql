-- PodcastIQ Snowflake Schema Setup
-- Run this script once to initialize the database, schemas, warehouses, and tables.
-- Prerequisites: Snowflake account with SYSADMIN and SECURITYADMIN roles

-- ============================================================
-- 1. DATABASE & SCHEMAS (6-layer architecture)
-- ============================================================

USE ROLE SYSADMIN;

CREATE DATABASE IF NOT EXISTS PODCASTIQ;

CREATE SCHEMA IF NOT EXISTS PODCASTIQ.RAW;
CREATE SCHEMA IF NOT EXISTS PODCASTIQ.STAGING;
CREATE SCHEMA IF NOT EXISTS PODCASTIQ.INTERMEDIATE;
CREATE SCHEMA IF NOT EXISTS PODCASTIQ.CURATED;
CREATE SCHEMA IF NOT EXISTS PODCASTIQ.SEMANTIC;
CREATE SCHEMA IF NOT EXISTS PODCASTIQ.APP;

-- ============================================================
-- 2. WAREHOUSES (right-sized for cost optimization)
-- ============================================================

CREATE WAREHOUSE IF NOT EXISTS LOADING_WH
    WAREHOUSE_SIZE = 'X-SMALL'
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE
    COMMENT = 'Used for data ingestion from YouTube transcripts';

CREATE WAREHOUSE IF NOT EXISTS TRANSFORM_WH
    WAREHOUSE_SIZE = 'SMALL'
    AUTO_SUSPEND = 300
    AUTO_RESUME = TRUE
    COMMENT = 'Used for DBT transformations and Cortex AI operations';

CREATE WAREHOUSE IF NOT EXISTS SEARCH_WH
    WAREHOUSE_SIZE = 'X-SMALL'
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE
    COMMENT = 'Used for Cortex Search queries from Streamlit app';

-- ============================================================
-- 3. FILE FORMAT & INTERNAL STAGE
-- ============================================================

USE SCHEMA PODCASTIQ.RAW;

CREATE FILE FORMAT IF NOT EXISTS JSON_FORMAT
    TYPE = 'JSON'
    STRIP_OUTER_ARRAY = TRUE
    IGNORE_UTF8_ERRORS = TRUE;

CREATE STAGE IF NOT EXISTS JSON_STAGE
    FILE_FORMAT = JSON_FORMAT
    COMMENT = 'Internal stage for loading extracted JSON files';

-- ============================================================
-- 4. RAW LAYER TABLES (VARIANT for JSON loading)
-- ============================================================

-- Metadata: one JSON object per video, loaded via COPY INTO
CREATE TABLE IF NOT EXISTS raw_youtube_metadata (
    raw_data            VARIANT         NOT NULL,
    source_file         VARCHAR(500),
    loaded_at           TIMESTAMP_NTZ   DEFAULT CURRENT_TIMESTAMP()
);

-- Transcripts: array of segments per video, loaded via COPY INTO
CREATE TABLE IF NOT EXISTS raw_transcripts (
    raw_data            VARIANT         NOT NULL,
    source_file         VARCHAR(500),
    loaded_at           TIMESTAMP_NTZ   DEFAULT CURRENT_TIMESTAMP()
);

-- ============================================================
-- 5. STAGING, INTERMEDIATE, CURATED, SEMANTIC layers
--    All managed by dbt models — do NOT create tables manually.
--
--    STAGING:      stg_youtube_metadata, stg_transcripts
--    INTERMEDIATE: int_episodes, int_transcript_lines
--    CURATED:      cur_episodes, cur_segments (120s sentence-aligned chunks)
--    SEMANTIC:     sem_embeddings, sem_topics_entities, sem_episode_summaries
-- ============================================================

-- ============================================================
-- 6. APP LAYER TABLES
-- ============================================================

USE SCHEMA PODCASTIQ.APP;

CREATE TABLE IF NOT EXISTS search_history (
    search_id           VARCHAR(50)     NOT NULL,
    session_id          VARCHAR(50),
    query_text          TEXT            NOT NULL,
    query_type          VARCHAR(20),
    result_count        INT,
    latency_ms          INT,
    created_at          TIMESTAMP_NTZ   DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_search_history PRIMARY KEY (search_id)
);

CREATE TABLE IF NOT EXISTS user_preferences (
    preference_id       VARCHAR(50)     NOT NULL,
    session_id          VARCHAR(50),
    saved_episode_id    VARCHAR(20),
    favorite_topic      VARCHAR(100),
    created_at          TIMESTAMP_NTZ   DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_user_preferences PRIMARY KEY (preference_id)
);

-- ============================================================
-- 7. RESOURCE MONITOR (cost control)
-- ============================================================

USE ROLE ACCOUNTADMIN;

CREATE RESOURCE MONITOR IF NOT EXISTS podcastiq_monitor
    WITH CREDIT_QUOTA = 150
    FREQUENCY = MONTHLY
    START_TIMESTAMP = IMMEDIATELY
    TRIGGERS
        ON 75 PERCENT DO NOTIFY
        ON 90 PERCENT DO NOTIFY
        ON 100 PERCENT DO SUSPEND;

-- Apply monitor to all warehouses
ALTER WAREHOUSE LOADING_WH SET RESOURCE_MONITOR = podcastiq_monitor;
ALTER WAREHOUSE TRANSFORM_WH SET RESOURCE_MONITOR = podcastiq_monitor;
ALTER WAREHOUSE SEARCH_WH SET RESOURCE_MONITOR = podcastiq_monitor;

-- ============================================================
-- Done! Verify setup:
-- ============================================================
-- SHOW DATABASES LIKE 'PODCASTIQ';
-- SHOW SCHEMAS IN DATABASE PODCASTIQ;
-- SHOW WAREHOUSES;
-- SHOW TABLES IN SCHEMA PODCASTIQ.RAW;
-- LIST @PODCASTIQ.RAW.JSON_STAGE;
