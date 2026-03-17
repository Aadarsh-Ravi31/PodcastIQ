-- SEMANTIC.SEM_CHUNK_EMBEDDINGS — 768-dimensional vector embeddings per chunk
-- Generated using: SNOWFLAKE.CORTEX.EMBED_TEXT_768('snowflake-arctic-embed-m', CHUNK_TEXT)
-- Powers vector similarity search in PODCASTIQ_SEARCH Cortex Search service
-- EMBEDDING column: VECTOR(FLOAT, 768) — 768-dimensional float vector

CREATE OR REPLACE TRANSIENT TABLE PODCASTIQ.SEMANTIC.SEM_CHUNK_EMBEDDINGS (
    CHUNK_ID            VARCHAR         NOT NULL,   -- FK → CURATED.CUR_CHUNKS.CHUNK_ID
    VIDEO_ID            VARCHAR(20),
    CHANNEL_NAME        VARCHAR(100),
    GENRE               VARCHAR(50),
    EPISODE_TITLE       VARCHAR(500),
    PUBLISH_DATE        TIMESTAMP_NTZ,
    TRANSCRIPT_QUALITY  VARCHAR(6),
    CHUNK_START_SEC     FLOAT,
    CHUNK_END_SEC       FLOAT,
    WORD_COUNT          NUMBER,
    YOUTUBE_URL         VARCHAR,
    CHUNK_TEXT          VARCHAR,
    EMBEDDING           VECTOR(FLOAT, 768)          -- Arctic Embed M embedding vector
);
