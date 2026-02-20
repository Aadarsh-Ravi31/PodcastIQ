-- PodcastIQ Snowflake Schema Setup
-- Run this script once to initialize the database, schemas, warehouses, and tables.
-- Prerequisites: Snowflake account with SYSADMIN and SECURITYADMIN roles

-- ============================================================
-- 1. DATABASE & SCHEMAS
-- ============================================================

USE ROLE SYSADMIN;

CREATE DATABASE IF NOT EXISTS PODCASTIQ;

CREATE SCHEMA IF NOT EXISTS PODCASTIQ.RAW;
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
-- 3. RAW LAYER TABLES
-- ============================================================

USE SCHEMA PODCASTIQ.RAW;

CREATE TABLE IF NOT EXISTS raw_youtube_metadata (
    video_id            VARCHAR(20)     NOT NULL,
    channel_id          VARCHAR(30),
    channel_name        VARCHAR(200),
    episode_title       VARCHAR(500)    NOT NULL,
    description         TEXT,
    publish_date        TIMESTAMP_NTZ,
    duration_seconds    INT,
    view_count          INT,
    like_count          INT,
    video_url           VARCHAR(500),
    extracted_at        TIMESTAMP_NTZ   DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_raw_metadata PRIMARY KEY (video_id)
);

CREATE TABLE IF NOT EXISTS raw_transcripts (
    transcript_id       VARCHAR(50)     NOT NULL,
    video_id            VARCHAR(20)     NOT NULL,
    text                TEXT            NOT NULL,
    start_seconds       FLOAT           NOT NULL,
    duration_seconds    FLOAT           NOT NULL,
    language            VARCHAR(10)     DEFAULT 'en',
    is_auto_generated   BOOLEAN         DEFAULT TRUE,
    extracted_at        TIMESTAMP_NTZ   DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_raw_transcripts PRIMARY KEY (transcript_id),
    CONSTRAINT fk_raw_transcripts_video FOREIGN KEY (video_id)
        REFERENCES raw_youtube_metadata(video_id)
);

-- ============================================================
-- 4. CURATED LAYER TABLES (populated by DBT)
-- ============================================================

USE SCHEMA PODCASTIQ.CURATED;

-- These tables will be created/managed by DBT models.
-- Included here for reference only.

-- curated_episodes: Full episodes with cleaned, concatenated transcripts
-- curated_segments: 60-second chunks with 15-second overlap

-- ============================================================
-- 5. SEMANTIC LAYER TABLES (populated by DBT)
-- ============================================================

USE SCHEMA PODCASTIQ.SEMANTIC;

-- These tables will be created/managed by DBT models.
-- embeddings: 768-dim vectors from snowflake-arctic-embed-m
-- topics_entities: Extracted people, orgs, technologies, topics
-- episode_summaries: Multi-level summaries

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
