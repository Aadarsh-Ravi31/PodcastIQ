-- SEMANTIC.SEM_CHUNK_TOPICS — LLM-extracted topics per chunk
-- Generated using: SNOWFLAKE.CORTEX.COMPLETE('llama3.1-405b', topic_extraction_prompt)
-- TOPICS_RAW: raw LLM JSON output (e.g. ["machine learning", "neural networks", "PyTorch"])

CREATE OR REPLACE TRANSIENT TABLE PODCASTIQ.SEMANTIC.SEM_CHUNK_TOPICS (
    CHUNK_ID        VARCHAR         NOT NULL,   -- FK → CURATED.CUR_CHUNKS.CHUNK_ID
    VIDEO_ID        VARCHAR(20),
    CHANNEL_NAME    VARCHAR(100),
    GENRE           VARCHAR(50),
    CHUNK_TEXT      VARCHAR,
    TOPICS_RAW      VARCHAR                     -- Raw LLM output (JSON array of topics)
);
