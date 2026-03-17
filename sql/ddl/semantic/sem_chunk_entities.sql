-- SEMANTIC.SEM_CHUNK_ENTITIES — LLM-extracted named entities per chunk
-- Generated using: SNOWFLAKE.CORTEX.COMPLETE('llama3.1-405b', ner_prompt)
-- ENTITIES_RAW: raw LLM JSON output with people, orgs, technologies, etc.

CREATE OR REPLACE TRANSIENT TABLE PODCASTIQ.SEMANTIC.SEM_CHUNK_ENTITIES (
    CHUNK_ID        VARCHAR         NOT NULL,   -- FK → CURATED.CUR_CHUNKS.CHUNK_ID
    VIDEO_ID        VARCHAR(20),
    CHANNEL_NAME    VARCHAR(100),
    GENRE           VARCHAR(50),
    ENTITIES_RAW    VARCHAR                     -- Raw LLM output (JSON: people, orgs, tech)
);
