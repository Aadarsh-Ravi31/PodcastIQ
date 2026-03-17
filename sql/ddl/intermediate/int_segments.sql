-- STAGING.INT_SEGMENTS — Add episode context to each transcript segment
-- Joins STG_SEGMENTS with INT_EPISODES
-- Adds: episode title, publish date, quality score, YouTube deep link, word count
-- Filters: excludes artifact segments ([Music], [Applause], etc.)

CREATE OR REPLACE VIEW PODCASTIQ.STAGING.INT_SEGMENTS (
    SEGMENT_ID,
    VIDEO_ID,
    CHANNEL_ID,
    CHANNEL_NAME,
    GENRE,
    SEGMENT_INDEX,
    TEXT_RAW,
    TEXT_CLEAN,
    START_TIME,
    DURATION_SEC,
    END_TIME,
    IS_ARTIFACT,
    EPISODE_TITLE,
    PUBLISH_DATE,
    EPISODE_DURATION_MIN,
    TRANSCRIPT_QUALITY,
    ENGAGEMENT_RATE,
    YOUTUBE_TIMESTAMP_URL,
    WORD_COUNT
) AS (
    WITH segments AS (
        SELECT * FROM PODCASTIQ.STAGING.STG_SEGMENTS
    ),

    episodes AS (
        SELECT
            video_id,
            title,
            publish_date,
            duration_min,
            transcript_quality,
            engagement_rate
        FROM PODCASTIQ.STAGING.INT_EPISODES
    )

    SELECT
        s.segment_id,
        s.video_id,
        s.channel_id,
        s.channel_name,
        s.genre,
        s.segment_index,
        s.text_raw,
        s.text_clean,
        s.start_time,
        s.duration_sec,
        s.end_time,
        s.is_artifact,

        -- Episode context
        e.title                                             AS episode_title,
        e.publish_date,
        e.duration_min                                      AS episode_duration_min,
        e.transcript_quality,
        e.engagement_rate,

        -- YouTube deep link with timestamp (seconds)
        'https://www.youtube.com/watch?v=' || s.video_id ||
        '&t=' || FLOOR(s.start_time)::VARCHAR               AS youtube_timestamp_url,

        -- Word count per segment
        ARRAY_SIZE(SPLIT(s.text_clean, ' '))                AS word_count

    FROM segments s
    LEFT JOIN episodes e ON s.video_id = e.video_id

    WHERE s.is_artifact = FALSE
);
