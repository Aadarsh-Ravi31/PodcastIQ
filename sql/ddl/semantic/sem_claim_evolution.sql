-- SEMANTIC.SEM_CLAIM_EVOLUTION — Temporal drift between related claims
-- Populated by: Week 6 temporal analysis pipeline
--
-- Identifies how claims evolve over time:
--   Same speaker + same topic + different dates → speaker drift
--   Different speakers + same topic + different dates → discourse evolution
--
-- DRIFT_TYPE taxonomy:
--   REVISED        — Speaker updated or corrected a prior claim
--   ESCALATED      — Claim strengthened / became more extreme
--   SOFTENED       — Claim weakened / became more hedged
--   CONTRADICTED   — Later claim directly contradicts original
--   CONFIRMED      — Later claim independently validates original
--
-- Detection method:
--   1. Embed all claims (use existing SEM_CHUNK_EMBEDDINGS.EMBEDDING approach)
--   2. Find claim pairs: same topic, time delta > 30 days, cosine similarity > 0.7
--   3. Cortex LLM classifies drift type + writes ANALYSIS
--   4. Insert into this table + create EVOLVED_FROM edges in Neo4j

CREATE TABLE IF NOT EXISTS PODCASTIQ.SEMANTIC.SEM_CLAIM_EVOLUTION (
    -- Identity
    EVOLUTION_ID        VARCHAR(64)     NOT NULL PRIMARY KEY,   -- SHA256(original_claim_id + evolved_claim_id)
    ORIGINAL_CLAIM_ID   VARCHAR(64)     NOT NULL,               -- FK → SEM_CLAIMS.CLAIM_ID (earlier claim)
    EVOLVED_CLAIM_ID    VARCHAR(64)     NOT NULL,               -- FK → SEM_CLAIMS.CLAIM_ID (later claim)

    -- Evolution classification
    DRIFT_TYPE          VARCHAR(20)     NOT NULL,               -- REVISED | ESCALATED | SOFTENED | CONTRADICTED | CONFIRMED
    SAME_SPEAKER        BOOLEAN,                                -- TRUE if both claims attributed to same person
    TIME_DELTA_DAYS     INTEGER,                                -- Days between ORIGINAL and EVOLVED claim dates
    SIMILARITY_SCORE    FLOAT,                                  -- Cosine similarity of claim embeddings (0-1)
    ANALYSIS            VARCHAR(1000),                          -- LLM explanation of the drift

    -- Denormalized context for quick access
    ORIGINAL_SPEAKER    VARCHAR(200),                           -- Speaker of original claim
    EVOLVED_SPEAKER     VARCHAR(200),                           -- Speaker of evolved claim
    TOPIC               VARCHAR(500),                           -- Shared topic between claims
    ORIGINAL_DATE       DATE,                                   -- Date of original claim
    EVOLVED_DATE        DATE,                                   -- Date of evolved claim
    CHANNEL_ORIGINAL    VARCHAR(100),                           -- Channel of original claim
    CHANNEL_EVOLVED     VARCHAR(100),                           -- Channel of evolved claim

    -- Metadata
    DETECTED_AT         TIMESTAMP_NTZ   DEFAULT CURRENT_TIMESTAMP()
);

-- ============================================================
-- Verification queries (run after population in Week 6)
-- ============================================================

-- Evolution pairs by drift type
-- SELECT DRIFT_TYPE, COUNT(*) AS count, AVG(TIME_DELTA_DAYS) AS avg_days_apart
-- FROM SEMANTIC.SEM_CLAIM_EVOLUTION
-- GROUP BY DRIFT_TYPE ORDER BY count DESC;

-- Cross-channel evolutions (same topic discussed across different channels)
-- SELECT CHANNEL_ORIGINAL, CHANNEL_EVOLVED, DRIFT_TYPE, COUNT(*) AS count
-- FROM SEMANTIC.SEM_CLAIM_EVOLUTION
-- WHERE CHANNEL_ORIGINAL != CHANNEL_EVOLVED
-- GROUP BY 1, 2, 3 ORDER BY count DESC;

-- Most-evolved topics (topics with the most evolution pairs)
-- SELECT TOPIC, COUNT(*) AS evolution_count,
--        SUM(CASE WHEN DRIFT_TYPE = 'CONTRADICTED' THEN 1 ELSE 0 END) AS contradictions,
--        SUM(CASE WHEN DRIFT_TYPE = 'CONFIRMED' THEN 1 ELSE 0 END) AS confirmations
-- FROM SEMANTIC.SEM_CLAIM_EVOLUTION
-- GROUP BY TOPIC ORDER BY evolution_count DESC LIMIT 20;

-- Speaker who changes their mind most (REVISED + SOFTENED)
-- SELECT ORIGINAL_SPEAKER,
--        COUNT(*) AS total_evolutions,
--        SUM(CASE WHEN DRIFT_TYPE IN ('REVISED', 'SOFTENED') AND SAME_SPEAKER THEN 1 ELSE 0 END) AS changed_mind_count
-- FROM SEMANTIC.SEM_CLAIM_EVOLUTION
-- WHERE SAME_SPEAKER = TRUE
-- GROUP BY ORIGINAL_SPEAKER ORDER BY changed_mind_count DESC LIMIT 10;
