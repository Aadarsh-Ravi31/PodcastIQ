-- RAW.EPISODES — Landing table for all podcast episode data
-- One row per video. RAW_DATA (VARIANT) stores the full merged payload
-- from channel_extraction.py + snowflake_loader.py
-- Loaded via: PUT to internal stage → COPY INTO

CREATE OR REPLACE TABLE PODCASTIQ.RAW.EPISODES (
    VIDEO_ID        VARCHAR(20)     NOT NULL,
    CHANNEL_ID      VARCHAR(30),
    LOAD_TIMESTAMP  TIMESTAMP_NTZ   DEFAULT CURRENT_TIMESTAMP(),
    SOURCE_FILE     VARCHAR(500),
    RAW_DATA        VARIANT         NOT NULL,
    CONSTRAINT PK_EPISODES PRIMARY KEY (VIDEO_ID)
);
