-- STAGING.STG_EPISODES — Parse VARIANT JSON → flat typed columns
-- One row per episode. Source: RAW.EPISODES

CREATE OR REPLACE VIEW PODCASTIQ.STAGING.STG_EPISODES (
    VIDEO_ID,
    CHANNEL_ID,
    CHANNEL_NAME,
    GENRE,
    TITLE,
    PUBLISH_DATE,
    DURATION_MIN,
    DURATION_ISO,
    VIDEO_URL,
    VIEW_COUNT,
    LIKE_COUNT,
    SEGMENT_COUNT,
    TOTAL_WORDS,
    COVERAGE_PCT,
    ARTIFACT_COUNT,
    HAS_TIMESTAMP_GAPS,
    WORDS_PER_MINUTE,
    AVG_SEGMENT_LEN_SEC,
    PUBLISH_YEAR,
    YOUTUBE_BASE_URL,
    LOAD_TIMESTAMP,
    SOURCE_FILE
) AS (
    WITH raw AS (
        SELECT
            video_id,
            channel_id,
            load_timestamp,
            source_file,
            raw_data
        FROM PODCASTIQ.RAW.EPISODES
    )

    SELECT
        -- Identity
        raw_data:video_id::VARCHAR(20)           AS video_id,
        raw_data:channel_id::VARCHAR(30)         AS channel_id,
        raw_data:channel_name::VARCHAR(100)      AS channel_name,
        raw_data:genre::VARCHAR(50)              AS genre,

        -- Episode metadata
        raw_data:title::VARCHAR(500)             AS title,
        raw_data:publish_date::TIMESTAMP_NTZ     AS publish_date,
        raw_data:duration_min::FLOAT             AS duration_min,
        raw_data:duration_iso::VARCHAR(20)       AS duration_iso,
        raw_data:video_url::VARCHAR(300)         AS video_url,

        -- Engagement
        raw_data:view_count::NUMBER              AS view_count,
        raw_data:like_count::NUMBER              AS like_count,

        -- Transcript quality metrics
        raw_data:segment_count::NUMBER           AS segment_count,
        raw_data:total_words::NUMBER             AS total_words,
        raw_data:coverage_pct::FLOAT             AS coverage_pct,
        raw_data:artifact_count::NUMBER          AS artifact_count,
        raw_data:has_timestamp_gaps::BOOLEAN     AS has_timestamp_gaps,
        raw_data:words_per_minute::FLOAT         AS words_per_minute,
        raw_data:avg_segment_len_sec::FLOAT      AS avg_segment_len_sec,

        -- Derived
        YEAR(raw_data:publish_date::TIMESTAMP_NTZ)   AS publish_year,
        raw_data:video_url::VARCHAR(300)             AS youtube_base_url,

        -- Load metadata
        load_timestamp,
        source_file

    FROM raw
    WHERE raw_data:video_id IS NOT NULL
);
