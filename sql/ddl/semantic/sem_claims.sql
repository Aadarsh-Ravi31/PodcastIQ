-- SEMANTIC.SEM_CLAIMS — Extracted claims from podcast chunks
-- Populated by: scripts/claim_extractor.py using Cortex LLM (llama3.1-405b)
--
-- Extraction uses a two-tier speaker attribution approach:
--   Tier 1: Host/guest names from SEM_EPISODE_PARTICIPANTS (pre-populated)
--   Tier 2: LLM infers speaker per claim from context clues within chunk text
--
-- CLAIM_TYPE taxonomy:
--   VERIFIABLE_FACT  — Can be checked against factual sources
--   PREDICTION       — Forward-looking forecast or projection
--   OPINION          — Personal view or subjective assessment
--   STATISTICAL      — Numerical claim or data point
--
-- VERIFICATION_STATUS lifecycle:
--   PENDING → (Stage 1 Cortex LLM) → VERIFIED | FALSE | OUTDATED | DISPUTED
--   PENDING → (Stage 2 MCP Web Search) → VERIFIED | FALSE | OUTDATED | DISPUTED | UNVERIFIED

CREATE TABLE IF NOT EXISTS PODCASTIQ.SEMANTIC.SEM_CLAIMS (
    -- Identity
    CLAIM_ID                VARCHAR(64)     NOT NULL PRIMARY KEY,   -- SHA256 hash of chunk_id + claim_text
    CHUNK_ID                VARCHAR         NOT NULL,               -- FK → CURATED.CUR_CHUNKS.CHUNK_ID
    VIDEO_ID                VARCHAR(20)     NOT NULL,               -- FK → RAW.EPISODES.VIDEO_ID

    -- Claim content
    CLAIM_TEXT              VARCHAR(2000)   NOT NULL,               -- The extracted claim statement
    TOPIC                   VARCHAR(500),                           -- Primary topic of the claim
    CLAIM_TYPE              VARCHAR(20),                            -- VERIFIABLE_FACT | PREDICTION | OPINION | STATISTICAL
    SENTIMENT               VARCHAR(10),                            -- POSITIVE | NEGATIVE | NEUTRAL

    -- Speaker attribution (Two-Tier)
    SPEAKER                 VARCHAR(200),                           -- Inferred speaker name
    SPEAKER_ROLE            VARCHAR(10),                            -- HOST | GUEST | UNKNOWN
    ATTRIBUTION_CONFIDENCE  VARCHAR(10),                            -- HIGH | MEDIUM | LOW | UNKNOWN
    ATTRIBUTION_SOURCE      VARCHAR(20),                            -- METADATA | LLM_INFERRED | EPISODE_LEVEL

    -- Temporal context
    CLAIM_DATE              DATE,                                   -- Episode publish date (for temporal analysis)
    CHANNEL_NAME            VARCHAR(100),                           -- Denormalized for query performance
    YOUTUBE_URL             VARCHAR(500),                           -- Deep link to exact timestamp

    -- Fact-checking (populated by scripts/fact_checker.py)
    VERIFICATION_STATUS     VARCHAR(20)     DEFAULT 'PENDING',      -- PENDING | VERIFIED | OUTDATED | DISPUTED | UNVERIFIED | FALSE
    VERIFICATION_SOURCE     VARCHAR(20),                            -- LLM_ONLY | LLM_PLUS_WEB | PENDING
    LAST_VERIFIED           TIMESTAMP_NTZ,
    EVIDENCE_SUMMARY        VARCHAR(2000),                          -- LLM-generated explanation of verdict
    EVIDENCE_URLS           ARRAY,                                  -- Source URLs from web search

    -- Metadata
    EXTRACTED_AT            TIMESTAMP_NTZ   DEFAULT CURRENT_TIMESTAMP(),
    EXTRACTION_MODEL        VARCHAR(50)     DEFAULT 'llama3.1-405b'
);

-- ============================================================
-- Useful views and verification queries
-- ============================================================

-- Claim type distribution
-- SELECT CLAIM_TYPE, COUNT(*) AS count, ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct
-- FROM SEMANTIC.SEM_CLAIMS
-- GROUP BY CLAIM_TYPE ORDER BY count DESC;

-- Speaker attribution confidence distribution
-- SELECT ATTRIBUTION_CONFIDENCE, COUNT(*) AS count
-- FROM SEMANTIC.SEM_CLAIMS
-- GROUP BY ATTRIBUTION_CONFIDENCE ORDER BY count DESC;

-- Claims ready for fact-checking (VERIFIABLE_FACT + STATISTICAL, still PENDING)
-- SELECT COUNT(*) AS pending_fact_check_count
-- FROM SEMANTIC.SEM_CLAIMS
-- WHERE CLAIM_TYPE IN ('VERIFIABLE_FACT', 'STATISTICAL')
--   AND VERIFICATION_STATUS = 'PENDING';

-- Verification status breakdown
-- SELECT VERIFICATION_STATUS, COUNT(*) AS count
-- FROM SEMANTIC.SEM_CLAIMS
-- GROUP BY VERIFICATION_STATUS ORDER BY count DESC;

-- Claims per channel (quality check)
-- SELECT CHANNEL_NAME, COUNT(*) AS claim_count, COUNT(DISTINCT VIDEO_ID) AS episode_count,
--        ROUND(COUNT(*) * 1.0 / COUNT(DISTINCT VIDEO_ID), 1) AS avg_claims_per_episode
-- FROM SEMANTIC.SEM_CLAIMS
-- GROUP BY CHANNEL_NAME ORDER BY claim_count DESC;
