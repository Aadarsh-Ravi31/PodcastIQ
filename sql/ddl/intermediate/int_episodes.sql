-- STAGING.INT_EPISODES — Enrich episodes with channel data + derived fields
-- Joins STG_EPISODES with RAW.CHANNELS for channel URL
-- Adds: transcript quality score, engagement rate, estimated chunk count

CREATE OR REPLACE VIEW PODCASTIQ.STAGING.INT_EPISODES (
    VIDEO_ID,
    CHANNEL_ID,
    CHANNEL_NAME,
    GENRE,
    TITLE,
    PUBLISH_DATE,
    PUBLISH_YEAR,
    DURATION_MIN,
    VIEW_COUNT,
    LIKE_COUNT,
    TOTAL_WORDS,
    SEGMENT_COUNT,
    COVERAGE_PCT,
    ARTIFACT_COUNT,
    WORDS_PER_MINUTE,
    VIDEO_URL,
    CHANNEL_URL,
    DURATION_SECONDS,
    WORDS_PER_MIN,
    ESTIMATED_CHUNKS,
    TRANSCRIPT_QUALITY,
    ENGAGEMENT_RATE,
    LOAD_TIMESTAMP
) AS (
    WITH episodes AS (
        SELECT * FROM PODCASTIQ.STAGING.STG_EPISODES
    ),

    channels AS (
        SELECT
            channel_id,
            channel_name,
            genre,
            youtube_url
        FROM PODCASTIQ.RAW.CHANNELS
    )

    SELECT
        e.video_id,
        e.channel_id,
        e.channel_name,
        e.genre,
        e.title,
        e.publish_date,
        e.publish_year,
        e.duration_min,
        e.view_count,
        e.like_count,
        e.total_words,
        e.segment_count,
        e.coverage_pct,
        e.artifact_count,
        e.words_per_minute,
        e.video_url,
        c.youtube_url                                           AS channel_url,

        -- Derived fields
        ROUND(e.duration_min * 60)                             AS duration_seconds,
        ROUND(e.total_words / NULLIF(e.duration_min, 0), 1)   AS words_per_min,
        FLOOR(e.duration_min / 120) + 1                        AS estimated_chunks,

        -- Transcript quality tier (based on coverage %)
        CASE
            WHEN e.coverage_pct >= 0.9  THEN 'HIGH'
            WHEN e.coverage_pct >= 0.7  THEN 'MEDIUM'
            ELSE 'LOW'
        END                                                     AS transcript_quality,

        -- Engagement rate: likes / views
        ROUND(e.like_count / NULLIF(e.view_count, 0) * 100, 4) AS engagement_rate,

        e.load_timestamp

    FROM episodes e
    LEFT JOIN channels c ON e.channel_id = c.channel_id
);
