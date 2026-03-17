-- CURATED.CUR_CHUNKS — 120-second chunked transcript windows
-- Core table for semantic search. Each row = one searchable chunk.
-- CHUNK_ID format: {video_id}_chunk_{####}
-- YOUTUBE_URL deep links to exact timestamp in episode

CREATE OR REPLACE TRANSIENT TABLE PODCASTIQ.CURATED.CUR_CHUNKS (
    CHUNK_ID            VARCHAR         NOT NULL,   -- e.g. pRiP6O-c_KI_chunk_0000
    VIDEO_ID            VARCHAR(20),
    CHANNEL_ID          VARCHAR(30),
    CHANNEL_NAME        VARCHAR(100),
    GENRE               VARCHAR(50),
    EPISODE_TITLE       VARCHAR(500),
    PUBLISH_DATE        TIMESTAMP_NTZ,
    TRANSCRIPT_QUALITY  VARCHAR(6),                 -- HIGH / MEDIUM / LOW
    CHUNK_WINDOW        FLOAT,                      -- Chunk window number
    CHUNK_TEXT          VARCHAR,                    -- Full text of the chunk
    CHUNK_START_SEC     FLOAT,                      -- Start timestamp (seconds)
    CHUNK_END_SEC       FLOAT,                      -- End timestamp (seconds)
    CHUNK_DURATION_SEC  FLOAT,                      -- Duration of chunk
    SEGMENT_COUNT       NUMBER,                     -- Number of raw segments in chunk
    WORD_COUNT          NUMBER,                     -- Word count of chunk text
    YOUTUBE_URL         VARCHAR                     -- Deep link: youtube.com/watch?v=...&t=Xs
);
