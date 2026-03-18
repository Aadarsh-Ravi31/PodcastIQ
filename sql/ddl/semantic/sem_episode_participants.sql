-- SEMANTIC.SEM_EPISODE_PARTICIPANTS — Host and guest per episode
-- Populated by: scripts/guest_extractor.py (Two-Tier Speaker Attribution)
--
-- Tier 1 (EXTRACTION_METHOD = 'TITLE_PARSE'):
--   Host = hardcoded per channel (always known)
--   Guest = parsed from episode title via channel-specific regex patterns
--   Expected coverage: ~70-80% of episodes get a named guest
--
-- Tier 2 (EXTRACTION_METHOD = 'LLM_INFERRED'):
--   Fallback for titles that don't match regex patterns
--   Uses Cortex LLM to infer guest name from title + description

CREATE TABLE IF NOT EXISTS PODCASTIQ.SEMANTIC.SEM_EPISODE_PARTICIPANTS (
    VIDEO_ID            VARCHAR(20)     NOT NULL,   -- FK → RAW.EPISODES.VIDEO_ID
    PARTICIPANT_NAME    VARCHAR(200)    NOT NULL,   -- Full name as extracted
    PARTICIPANT_ROLE    VARCHAR(10)     NOT NULL,   -- HOST | GUEST
    EXTRACTION_METHOD   VARCHAR(20)     NOT NULL,   -- TITLE_PARSE | MANUAL | LLM_INFERRED
    CONFIDENCE          VARCHAR(10)     NOT NULL,   -- HIGH | MEDIUM | LOW
    CHANNEL_NAME        VARCHAR(100),               -- Denormalized for query convenience
    EPISODE_TITLE       VARCHAR(500),               -- For debugging / audit
    EXTRACTED_AT        TIMESTAMP_NTZ   DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (VIDEO_ID, PARTICIPANT_NAME)
);

-- Index for lookups by participant name (used by Knowledge Graph Agent)
-- CREATE INDEX IF NOT EXISTS idx_sep_participant ON SEM_EPISODE_PARTICIPANTS (PARTICIPANT_NAME);
-- Note: Snowflake does not use explicit indexes — clustering keys used instead if needed.

-- ============================================================
-- Verification queries (run after population)
-- ============================================================

-- Coverage check: what % of episodes have at least one guest?
-- SELECT
--     COUNT(DISTINCT VIDEO_ID) AS total_episodes_in_db,
--     COUNT(DISTINCT CASE WHEN PARTICIPANT_ROLE = 'GUEST' THEN VIDEO_ID END) AS episodes_with_guest,
--     ROUND(
--         COUNT(DISTINCT CASE WHEN PARTICIPANT_ROLE = 'GUEST' THEN VIDEO_ID END) * 100.0
--         / NULLIF(COUNT(DISTINCT VIDEO_ID), 0), 1
--     ) AS guest_coverage_pct
-- FROM SEMANTIC.SEM_EPISODE_PARTICIPANTS;

-- Top participants by episode count (validates extraction quality)
-- SELECT PARTICIPANT_NAME, PARTICIPANT_ROLE, COUNT(*) AS episode_count
-- FROM SEMANTIC.SEM_EPISODE_PARTICIPANTS
-- GROUP BY 1, 2
-- ORDER BY 3 DESC
-- LIMIT 20;
