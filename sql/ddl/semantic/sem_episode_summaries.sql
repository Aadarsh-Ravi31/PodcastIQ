-- SEMANTIC.SEM_EPISODE_SUMMARIES — LLM-generated episode-level summaries
-- Generated using: SNOWFLAKE.CORTEX.COMPLETE('llama3.1-405b', summarization_prompt)
-- One row per episode. EPISODE_SUMMARY: multi-sentence natural language summary.

CREATE OR REPLACE TRANSIENT TABLE PODCASTIQ.SEMANTIC.SEM_EPISODE_SUMMARIES (
    VIDEO_ID        VARCHAR(20)     NOT NULL,   -- FK → RAW.EPISODES.VIDEO_ID
    CHANNEL_NAME    VARCHAR(100),
    GENRE           VARCHAR(50),
    TITLE           VARCHAR(500),
    DURATION_MIN    FLOAT,
    EPISODE_SUMMARY VARCHAR                     -- LLM-generated summary of full episode
);
